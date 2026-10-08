"""OSINT tool implementations. Passive, public-source only. Each returns (summary, data)."""
import hashlib, ipaddress, json, re, socket
from html.parser import HTMLParser
import dns.resolver, dns.reversename, dns.exception
import httpx
from .netguard import fetch, check_host, TargetBlocked

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
DOMAIN_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,24})\b", re.I)
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
HANDLE_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_.]{3,30})\b")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

class ToolError(Exception): pass

def clean_domain(v: str) -> str:
    v = (v or "").strip().lower().rstrip(".")
    v = re.sub(r"^https?://", "", v).split("/")[0].split(":")[0]
    if not DOMAIN_RE.fullmatch(v) or len(v) > 253: raise ToolError("Enter a valid domain name, e.g. example.com")
    return v

def clean_url(v: str) -> str:
    v = (v or "").strip()
    if not re.match(r"^https?://", v): v = "https://" + v
    if not URL_RE.fullmatch(v): raise ToolError("Enter a valid http(s) URL")
    return v

def _res():
    r = dns.resolver.Resolver(); r.lifetime = 6; r.timeout = 3
    return r

def _q(domain, rtype):
    try:
        return [a.to_text() for a in _res().resolve(domain, rtype)]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return []
    except dns.exception.DNSException as e:
        raise ToolError(f"DNS query failed: {e.__class__.__name__}")

def dns_lookup(i, ctx):
    d = clean_domain(i["domain"])
    rec = {t: _q(d, t) for t in ("A", "AAAA", "CNAME", "NS", "SOA")}
    n = sum(len(v) for v in rec.values())
    return f"{d}: {n} records", {"domain": d, "records": rec, "source": "DNS query (system resolver)"}

def mx_records(i, ctx):
    d = clean_domain(i["domain"]); mx = _q(d, "MX")
    return f"{d}: {len(mx)} MX", {"domain": d, "mx": mx, "source": "DNS query"}

def txt_records(i, ctx):
    d = clean_domain(i["domain"]); t = _q(d, "TXT")
    flags = {"spf": [x for x in t if "v=spf1" in x], "dmarc": _q("_dmarc." + d, "TXT"),
             "verification_tokens": [x for x in t if "verification" in x.lower() or "site-verification" in x.lower()]}
    return f"{d}: {len(t)} TXT", {"domain": d, "txt": t, **flags, "source": "DNS query"}

def reverse_dns(i, ctx):
    ip = str(ipaddress.ip_address(i["ip"].strip()))
    try:
        ptr = [a.to_text() for a in _res().resolve(dns.reversename.from_address(ip), "PTR")]
    except dns.exception.DNSException:
        ptr = []
    return f"{ip}: {len(ptr)} PTR", {"ip": ip, "ptr": ptr, "source": "DNS PTR query"}

def asn_lookup(i, ctx):
    ip = ipaddress.ip_address(i["ip"].strip())
    if ip.version != 4: raise ToolError("ASN lookup supports IPv4 in this build")
    if ip.is_private: raise ToolError("Private address - no public ASN")
    rev = ".".join(reversed(str(ip).split(".")))
    t = _q(f"{rev}.origin.asn.cymru.com", "TXT")
    if not t: return f"{ip}: no ASN data", {"ip": str(ip), "asn": None, "source": "Team Cymru DNS"}
    asn, prefix, cc, reg, alloc = [x.strip() for x in t[0].strip('"').split("|")[:5]]
    first = asn.split()[0]
    name = _q(f"AS{first}.asn.cymru.com", "TXT")
    return f"{ip}: AS{first}", {"ip": str(ip), "asn": f"AS{first}", "prefix": prefix, "country": cc, "registry": reg, "allocated": alloc,
                                "as_name": name[0].strip('"').split("|")[-1].strip() if name else "", "source": "Team Cymru IP-to-ASN (DNS)"}

def ip_info(i, ctx):
    ip = str(ipaddress.ip_address(i["ip"].strip()))
    _, rd = reverse_dns({"ip": ip}, ctx)
    try: _, asn = asn_lookup({"ip": ip}, ctx)
    except ToolError as e: asn = {"error": str(e)}
    return f"{ip} info", {"ip": ip, "reverse_dns": rd["ptr"], "asn": asn, "source": "DNS PTR + Team Cymru"}

def whois_lookup(i, ctx):
    d = clean_domain(i["domain"])
    def q(server, query):
        with socket.create_connection((server, 43), timeout=8) as s:
            s.sendall((query + "\r\n").encode()); buf = b""
            while len(buf) < 200_000:
                c = s.recv(4096)
                if not c: break
                buf += c
        return buf.decode("utf-8", "replace")
    try:
        ref = q("whois.iana.org", d.split(".")[-1])
        m = re.search(r"^whois:\s*(\S+)", ref, re.M)
        server = m.group(1) if m else "whois.iana.org"
        raw = q(server, d)
    except OSError as e:
        raise ToolError(f"WHOIS connection failed ({e.__class__.__name__}); port 43 may be blocked on this network")
    def f(k):
        m = re.search(rf"^{k}:\s*(.+)$", raw, re.M | re.I); return m.group(1).strip() if m else ""
    parsed = {"registrar": f("Registrar"), "created": f("Creation Date"), "updated": f("Updated Date"), "expires": f("Registry Expiry Date") or f("Expiration Date"),
              "name_servers": sorted({x.strip().lower() for x in re.findall(r"^Name Server:\s*(\S+)", raw, re.M | re.I)}), "status": re.findall(r"^Domain Status:\s*(\S+)", raw, re.M | re.I)}
    return f"{d}: registrar {parsed['registrar'] or 'n/a'}", {"domain": d, "whois_server": server, "parsed": parsed, "raw": raw[:20000], "source": f"WHOIS ({server})"}

def ct_lookup(i, ctx):
    d = clean_domain(i["domain"])
    try:
        r = httpx.get("https://crt.sh/", params={"q": f"%.{d}", "output": "json"}, timeout=20, headers={"User-Agent": "OSINTBook/1.0"})
        r.raise_for_status(); rows = r.json()
    except Exception as e:
        raise ToolError(f"Certificate transparency query failed: {e.__class__.__name__}")
    names = sorted({n.strip().lower() for row in rows for n in row.get("name_value", "").split("\n") if not n.startswith("*")})
    certs = [{"id": x["id"], "issuer": x.get("issuer_name"), "not_before": x.get("not_before"), "common_name": x.get("common_name")} for x in rows[:50]]
    return f"{d}: {len(names)} names in {len(rows)} certs", {"domain": d, "hostnames": names[:500], "certificates_sample": certs, "total_certificates": len(rows), "source": "crt.sh (public CT logs)"}

class _Meta(HTMLParser):
    def __init__(s): super().__init__(); s.title = ""; s.meta = {}; s.links = []; s.scripts = []; s._t = False; s.gen = ""
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag == "title": s._t = True
        elif tag == "meta":
            k = a.get("name") or a.get("property") or a.get("http-equiv")
            if k and a.get("content"): s.meta[k.lower()] = a["content"][:500]
        elif tag == "link" and a.get("rel") in ("canonical", "alternate", "icon"): s.links.append({"rel": a["rel"], "href": a.get("href", "")[:300]})
        elif tag == "script" and a.get("src"): s.scripts.append(a["src"][:300])
    def handle_endtag(s, tag):
        if tag == "title": s._t = False
    def handle_data(s, d):
        if s._t: s.title += d.strip()[:300]

def _get(i, ctx, method="GET", url=None):
    try: return fetch(url or clean_url(i["url"]), ctx["allow_private"], method)
    except TargetBlocked as e: raise ToolError(str(e))
    except httpx.HTTPError as e: raise ToolError(f"Request failed: {e.__class__.__name__}")

def http_headers(i, ctx):
    url, h, st, _, chain = _get(i, ctx, "GET")
    sec = {k: h.get(k, "MISSING") for k in ("strict-transport-security", "content-security-policy", "x-frame-options", "x-content-type-options", "referrer-policy")}
    return f"{url}: HTTP {st}", {"final_url": url, "status": st, "redirect_chain": chain, "headers": h, "security_headers": sec, "source": "HTTP GET"}

def page_metadata(i, ctx):
    url, h, st, body, chain = _get(i, ctx)
    p = _Meta(); p.feed(body.decode("utf-8", "replace"))
    return f"{p.title or url}", {"final_url": url, "status": st, "title": p.title, "meta": p.meta, "links": p.links[:30], "script_hosts": sorted({re.sub(r"^https?://([^/]+).*", r"\1", s) for s in p.scripts if s.startswith("http")}),
                                 "content_sha256": hashlib.sha256(body).hexdigest(), "source": "HTTP GET (HTML parsed, not rendered)"}

url_metadata = page_metadata

def robots_viewer(i, ctx):
    u = clean_url(i["url"]); base = re.match(r"https?://[^/]+", u).group(0)
    url, h, st, body, _ = _get(i, ctx, url=base + "/robots.txt")
    txt = body.decode("utf-8", "replace")
    return f"robots.txt HTTP {st}", {"url": url, "status": st, "sitemaps": re.findall(r"(?im)^sitemap:\s*(\S+)", txt), "disallow": re.findall(r"(?im)^disallow:\s*(\S+)", txt)[:100], "raw": txt[:20000], "source": "HTTP GET"}

def sitemap_viewer(i, ctx):
    u = clean_url(i["url"]); base = re.match(r"https?://[^/]+", u).group(0)
    url, h, st, body, _ = _get(i, ctx, url=u if u.endswith(".xml") else base + "/sitemap.xml")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace"))
    return f"sitemap: {len(locs)} URLs", {"url": url, "status": st, "urls": locs[:500], "total": len(locs), "source": "HTTP GET"}

TECH = [("WordPress", r"wp-content|wp-includes"), ("Cloudflare", r"cf-ray|cloudflare"), ("nginx", r"nginx"), ("Apache", r"apache"), ("React", r"react"), ("jQuery", r"jquery"),
        ("Shopify", r"cdn\.shopify|shopify"), ("Google Analytics", r"googletagmanager|google-analytics"), ("Bootstrap", r"bootstrap"), ("Wix", r"wixstatic|wix\.com")]
def tech_id(i, ctx):
    url, h, st, body, _ = _get(i, ctx)
    blob = (json.dumps(h) + body.decode("utf-8", "replace")[:200000]).lower()
    found = [{"technology": n, "basis": "string match in headers/HTML"} for n, rx in TECH if re.search(rx, blob)]
    return f"{len(found)} technologies (heuristic)", {"final_url": url, "detected": found, "server_header": h.get("server", ""), "note": "Heuristic string matching; verify before relying on it.", "source": "HTTP GET"}

PLATFORMS = {"GitHub": "https://github.com/{u}", "GitLab": "https://gitlab.com/{u}", "Reddit": "https://www.reddit.com/user/{u}", "X/Twitter": "https://x.com/{u}",
             "Instagram": "https://www.instagram.com/{u}/", "Mastodon.social": "https://mastodon.social/@{u}", "Keybase": "https://keybase.io/{u}", "Medium": "https://medium.com/@{u}",
             "Dev.to": "https://dev.to/{u}", "HackerNews": "https://news.ycombinator.com/user?id={u}", "LinkedIn": "https://www.linkedin.com/in/{u}", "YouTube": "https://www.youtube.com/@{u}"}
def username_search(i, ctx):
    u = i["username"].strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{2,40}", u): raise ToolError("Username: 2-40 letters, digits, . _ -")
    cands = [{"platform": p, "candidate_url": t.format(u=u), "status": "UNVERIFIED CANDIDATE"} for p, t in PLATFORMS.items()]
    return f"{len(cands)} candidate URLs (not checked)", {"username": u, "candidates": cands, "note": "Candidate URLs only. Open each manually, confirm the profile is public and relevant, and record it as an Account with a source. A matching username is not evidence of the same person.", "source": "Pattern list"}

def email_check(i, ctx):
    e = i["email"].strip()
    if not EMAIL_RE.fullmatch(e): raise ToolError("Not a valid email syntax")
    d = e.split("@")[1].lower(); mx = _q(d, "MX")
    return f"{d}: {'MX present' if mx else 'no MX'}", {"email_masked": e[:2] + "***@" + d, "domain": d, "syntax_valid": True, "domain_has_mx": bool(mx), "mx": mx, "note": "Domain-level checks only; no mailbox probing is performed.", "source": "DNS query"}

def _words(s): return set(re.findall(r"[a-z0-9]{3,}", (s or "").lower()))
def _lev(a, b):
    if len(a) < len(b): a, b = b, a
    prev = list(range(len(b) + 1))
    for x, ca in enumerate(a, 1):
        cur = [x]
        for y, cb in enumerate(b, 1): cur.append(min(prev[y] + 1, cur[-1] + 1, prev[y - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def profile_correlate(i, ctx):
    from .models import Account
    db = ctx["db"]; a, b = db.get(Account, i["account_a"]), db.get(Account, i["account_b"])
    if not a or not b: raise ToolError("Select two account records")
    ua, ub = a.username.lower(), b.username.lower()
    sig = [("Identical username", ua == ub, 30), ("Similar username", ua != ub and 1 - _lev(ua, ub) / max(len(ua), len(ub)) >= .75, 15),
           ("Same public website", bool(a.public_website) and a.public_website.rstrip("/") == b.public_website.rstrip("/"), 30),
           ("Display name match", bool(a.display_name) and a.display_name.lower() == b.display_name.lower(), 15)]
    ov = _words(a.bio) & _words(b.bio); sig.append((f"Shared bio terms: {', '.join(sorted(ov)[:8])}", len(ov) >= 3, 15))
    score = min(sum(w for _, ok, w in sig if ok), 90)
    return f"{a.username} vs {b.username}: indicative {score}%", {"account_a": a.ref, "account_b": b.ref, "signals": [{"signal": s, "present": ok} for s, ok, _ in sig], "indicative_score": score,
        "assessment": "POSSIBLE" if score < 50 else "LIKELY", "caution": "Indicative only. Record as an INFERENCE or HYPOTHESIS with reasoning; shared attributes do not confirm identity.", "source": "Local comparison of recorded accounts"}

def _ev_path(i, ctx):
    from .models import Evidence
    from .routers.evidence import abs_path
    ev = ctx["db"].get(Evidence, i["evidence_id"])
    if not ev or ev.deleted_at: raise ToolError("Select an evidence item")
    return ev, abs_path(ev.storage_path)

def file_type(i, ctx):
    ev, p = _ev_path(i, ctx); head = p.read_bytes()[:16]
    sigs = [(b"\x89PNG", "PNG image"), (b"\xff\xd8\xff", "JPEG image"), (b"GIF8", "GIF image"), (b"%PDF", "PDF document"), (b"PK", "ZIP container (docx/xlsx/pptx/zip)"), (b"RIFF", "RIFF (WebP/other)")]
    t = next((n for s, n in sigs if head.startswith(s)), "text/unknown")
    return f"{ev.ref}: {t}", {"evidence": ev.ref, "detected": t, "declared_extension": p.suffix, "magic_hex": head.hex(), "source": "Magic-byte inspection"}

def hash_calc(i, ctx):
    ev, p = _ev_path(i, ctx); b = p.read_bytes()
    return f"{ev.ref} hashes", {"evidence": ev.ref, "sha256": hashlib.sha256(b).hexdigest(), "sha1": hashlib.sha1(b).hexdigest(), "md5": hashlib.md5(b).hexdigest(), "stored_sha256": ev.sha256, "matches_stored": hashlib.sha256(b).hexdigest() == ev.sha256, "source": "Local computation"}

def pdf_metadata(i, ctx):
    from pypdf import PdfReader
    ev, p = _ev_path(i, ctx)
    try: r = PdfReader(str(p)); m = {k.lstrip("/"): str(v)[:300] for k, v in (r.metadata or {}).items()}
    except Exception as e: raise ToolError(f"Not a readable PDF: {e.__class__.__name__}")
    return f"{ev.ref}: {len(r.pages)} pages", {"evidence": ev.ref, "pages": len(r.pages), "encrypted": r.is_encrypted, "metadata": m, "source": "pypdf (file parsed, never executed)"}

def image_metadata(i, ctx):
    from PIL import Image, ExifTags
    ev, p = _ev_path(i, ctx)
    try:
        im = Image.open(p); ex = im.getexif()
        tags = {ExifTags.TAGS.get(k, str(k)): str(v)[:200] for k, v in ex.items()}
        gps = "GPS" if 34853 in ex else None
    except Exception as e: raise ToolError(f"Not a readable image: {e.__class__.__name__}")
    return f"{ev.ref}: {im.format} {im.size[0]}x{im.size[1]}", {"evidence": ev.ref, "format": im.format, "size": list(im.size), "exif": tags, "has_gps_block": bool(gps),
        "privacy_note": "GPS values are not extracted by this tool by design; handle location metadata under your authorization scope." if gps else "", "source": "Pillow"}

def _text_of(i, ctx):
    t = i.get("text") or ""
    if i.get("evidence_id"):
        ev, p = _ev_path(i, ctx)
        if ev.mime != "text": raise ToolError("Select a text-based evidence item")
        t += "\n" + p.read_bytes()[:500_000].decode("utf-8", "replace")
    if not t.strip(): raise ToolError("Provide text or select text evidence")
    return t

def entity_extraction(i, ctx):
    t = _text_of(i, ctx)
    emails = sorted(set(EMAIL_RE.findall(t))); urls = sorted(set(URL_RE.findall(t)))
    ips = sorted({x for x in IPV4_RE.findall(t)})
    doms = sorted({d.lower() for d in DOMAIN_RE.findall(t)} - {e.split("@")[1].lower() for e in emails})
    return f"{len(emails)} emails, {len(doms)} domains, {len(ips)} IPs", {"emails": emails, "domains": doms[:200], "ips": ips, "urls": urls[:200], "handles": sorted(set(HANDLE_RE.findall(t))), "dates": sorted(set(DATE_RE.findall(t))), "note": "Regex extraction - review for false positives.", "source": "Local analysis"}

def relationship_extraction(i, ctx):
    t = _text_of(i, ctx); out = []
    for sent in re.split(r"(?<=[.!?\n])\s+", t):
        ents = sorted(set(EMAIL_RE.findall(sent)) | set(DOMAIN_RE.findall(sent)) | {"@" + h for h in HANDLE_RE.findall(sent)})
        if len(ents) >= 2: out.append({"entities": ents[:6], "context": sent.strip()[:300], "suggested_type": "ASSOCIATED_WITH", "certainty": "POSSIBLE"})
    return f"{len(out)} co-occurrence candidates", {"candidates": out[:100], "note": "Co-occurrence is not a relationship. Review each before recording.", "source": "Local analysis"}

def timeline_builder(i, ctx):
    from .models import Source, Evidence, Account, Domain, Identifier
    db, cid = ctx["db"], i["case_id"]; ev = []
    for M, field, label in [(Source, "publication_date", "Source published"), (Source, "access_date", "Source accessed"), (Evidence, "collected_at", "Evidence collected"),
                            (Account, "first_observed", "Account first observed"), (Account, "last_observed", "Account last observed"), (Domain, "registered_on", "Domain registered"), (Identifier, "observed_date", "Identifier observed")]:
        for r in db.query(M).filter_by(case_id=cid):
            d = getattr(r, field)
            if d: ev.append({"event_date": d[:10], "title": f"{label}: {getattr(r, 'title', None) or getattr(r, 'username', None) or getattr(r, 'name', None) or r.ref}", "ref": r.ref, "event_type": "Observation"})
    ev.sort(key=lambda x: x["event_date"])
    return f"{len(ev)} candidate events", {"events": ev, "source": "Dates recorded in this case"}

def duplicate_detection(i, ctx):
    from .models import Identifier, Account, Source
    db, cid = ctx["db"], i["case_id"]; groups = {}
    for x in db.query(Identifier).filter_by(case_id=cid): groups.setdefault(("identifier", x.value.lower()), []).append(x.ref)
    for x in db.query(Account).filter_by(case_id=cid): groups.setdefault(("account", f"{x.platform.lower()}:{x.username.lower()}"), []).append(x.ref)
    for x in db.query(Source).filter_by(case_id=cid):
        if x.url: groups.setdefault(("source", x.url.lower().rstrip("/")), []).append(x.ref)
    d = [{"type": k[0], "value": k[1] if k[0] != "identifier" else "(value hidden)", "records": v} for k, v in groups.items() if len(v) > 1]
    return f"{len(d)} duplicate groups", {"duplicates": d, "source": "Exact-match comparison within case"}

def evidence_correlation(i, ctx):
    from .models import Evidence, Source
    db, cid = ctx["db"], i["case_id"]; by_hash, by_src = {}, {}
    for e in db.query(Evidence).filter_by(case_id=cid).filter(Evidence.deleted_at.is_(None)):
        by_hash.setdefault(e.sha256, []).append(e.ref)
        if e.source_id: by_src.setdefault(e.source_id, []).append(e.ref)
    return "Evidence correlation", {"identical_content": [v for v in by_hash.values() if len(v) > 1],
        "shared_source": [{"source": (db.get(Source, k).ref), "evidence": v} for k, v in by_src.items() if len(v) > 1], "source": "Hash and source linkage"}

IN = lambda n, label, t="text", req=True: dict(name=n, label=label, type=t, required=req)
TOOLS = {
 "dns_lookup": ("DNS lookup", "Domain / Network", "A, AAAA, CNAME, NS, SOA records", [IN("domain", "Domain")], dns_lookup, "DNS"),
 "whois_lookup": ("WHOIS lookup", "Domain / Network", "Registration data via WHOIS (port 43)", [IN("domain", "Domain")], whois_lookup, "WHOIS"),
 "ip_info": ("IP information", "Domain / Network", "Reverse DNS and ASN for an IP", [IN("ip", "IP address")], ip_info, "IP"),
 "asn_lookup": ("ASN lookup", "Domain / Network", "Origin AS and prefix", [IN("ip", "IPv4 address")], asn_lookup, "ASN"),
 "mx_records": ("MX records", "Domain / Network", "Mail exchangers", [IN("domain", "Domain")], mx_records, "MX"),
 "txt_records": ("TXT records", "Domain / Network", "TXT, SPF, DMARC", [IN("domain", "Domain")], txt_records, "TXT"),
 "reverse_dns": ("Reverse DNS", "Domain / Network", "PTR lookup", [IN("ip", "IP address")], reverse_dns, "RDNS"),
 "ct_lookup": ("Certificate transparency", "Domain / Network", "Hostnames from public CT logs (crt.sh)", [IN("domain", "Domain")], ct_lookup, "CT"),
 "url_metadata": ("URL metadata", "Web", "Title, meta tags, links, content hash", [IN("url", "URL")], url_metadata, "URL"),
 "http_headers": ("HTTP headers", "Web", "Response headers, redirects, security headers", [IN("url", "URL")], http_headers, "HDR"),
 "robots_viewer": ("robots.txt", "Web", "Fetch and parse robots.txt", [IN("url", "Site URL")], robots_viewer, "ROBOTS"),
 "sitemap_viewer": ("Sitemap", "Web", "List URLs in sitemap.xml", [IN("url", "Site URL")], sitemap_viewer, "SMAP"),
 "page_metadata": ("Page metadata", "Web", "OpenGraph / meta / canonical", [IN("url", "URL")], page_metadata, "META"),
 "tech_id": ("Technology identification", "Web", "Heuristic stack detection", [IN("url", "URL")], tech_id, "TECH"),
 "username_search": ("Username candidates", "Identifier research", "Candidate public profile URLs to review manually", [IN("username", "Username")], username_search, "USR"),
 "email_check": ("Public email check", "Identifier research", "Syntax and domain MX only", [IN("email", "Email")], email_check, "EML"),
 "profile_correlate": ("Profile correlation", "Identifier research", "Compare two recorded accounts", [IN("account_a", "Account A", "account"), IN("account_b", "Account B", "account")], profile_correlate, "COR"),
 "pdf_metadata": ("PDF metadata", "Document analysis", "Document info of a PDF evidence item", [IN("evidence_id", "Evidence", "evidence")], pdf_metadata, "PDF"),
 "image_metadata": ("Image metadata", "Document analysis", "EXIF of an image evidence item", [IN("evidence_id", "Evidence", "evidence")], image_metadata, "IMG"),
 "hash_calc": ("Hash calculation", "Document analysis", "SHA-256/SHA-1/MD5 of evidence", [IN("evidence_id", "Evidence", "evidence")], hash_calc, "HASH"),
 "file_type": ("File type identification", "Document analysis", "Magic-byte detection", [IN("evidence_id", "Evidence", "evidence")], file_type, "FTYPE"),
 "entity_extraction": ("Entity extraction", "Analysis", "Emails, domains, IPs, URLs, handles, dates", [IN("text", "Text", "textarea", False), IN("evidence_id", "Or text evidence", "evidence", False)], entity_extraction, "ENT"),
 "relationship_extraction": ("Relationship extraction", "Analysis", "Co-occurrence candidates", [IN("text", "Text", "textarea", False), IN("evidence_id", "Or text evidence", "evidence", False)], relationship_extraction, "RELX"),
 "timeline_builder": ("Timeline builder", "Analysis", "Candidate events from recorded dates", [IN("case_id", "Case", "case")], timeline_builder, "TLB"),
 "duplicate_detection": ("Duplicate detection", "Analysis", "Duplicate identifiers/accounts/sources", [IN("case_id", "Case", "case")], duplicate_detection, "DUP"),
 "evidence_correlation": ("Evidence correlation", "Analysis", "Identical content and shared sources", [IN("case_id", "Case", "case")], evidence_correlation, "ECOR"),
}
