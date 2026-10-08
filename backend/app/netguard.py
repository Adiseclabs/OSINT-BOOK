"""Outbound request safety: block private/loopback targets (SSRF) unless explicitly allowed in Settings."""
import ipaddress, socket
from urllib.parse import urlparse, urljoin
import httpx

class TargetBlocked(Exception): pass

def check_host(host: str, allow_private: bool):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise TargetBlocked(f"Cannot resolve {host}")
    for i in infos:
        ip = ipaddress.ip_address(i[4][0])
        if not allow_private and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast):
            raise TargetBlocked(f"{host} resolves to a non-public address ({ip}). Enable 'allow private targets' in Settings if this is authorized.")

def fetch(url: str, allow_private=False, method="GET", max_bytes=2_000_000, hops=5):
    """Fetch a public URL, re-validating every redirect hop. Returns (final_url, response_headers, status, body_bytes, chain)."""
    chain = []
    with httpx.Client(timeout=10, follow_redirects=False, headers={"User-Agent": "OSINTBook/1.0 (+local analyst workstation)"}) as c:
        for _ in range(hops + 1):
            u = urlparse(url)
            if u.scheme not in ("http", "https") or not u.hostname:
                raise TargetBlocked("Only http(s) URLs are supported")
            check_host(u.hostname, allow_private)
            with c.stream(method, url) as resp:
                chain.append({"url": url, "status": resp.status_code})
                if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                    url = urljoin(url, resp.headers["location"]); continue
                body = b""
                if method == "GET":
                    for chunk in resp.iter_bytes():
                        body += chunk
                        if len(body) >= max_bytes: break
                return url, dict(resp.headers), resp.status_code, body, chain
    raise TargetBlocked("Too many redirects")
