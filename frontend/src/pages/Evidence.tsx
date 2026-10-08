import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, ShieldCheck, Download, Trash2, Eye, FileText } from "lucide-react";
import { api, qs, Rec, ApiError, download, blobUrl, fmtTs, fmtTime } from "../lib";
import { useApp } from "../ctx";
import { useRefs, refLabel } from "../EntityPage";
import { Btn, Confirm, Dl, Empty, Hash, Loading, Modal, Mono, PageHead, Pager, Panel, Status, Tag, useDebounced } from "../ui";

const TYPES = ["Screenshot", "PDF", "Image", "Text file", "HTML export", "Document", "WHOIS output", "DNS output", "Webpage capture", "Analyst note", "Tool output"];

function UploadForm({ caseId, refs, onClose, onDone }: { caseId: string; refs: Rec; onClose: () => void; onDone: () => void }) {
  const { toast } = useApp(); const [file, setFile] = useState<File | null>(null); const [v, setV] = useState<Rec>({ evidence_type: "Screenshot" }); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const go = async () => {
    if (!file) return setErr("Choose a file"); setBusy(true); setErr("");
    const f = new FormData(); f.append("case_id", caseId); f.append("file", file); ["evidence_type", "description", "source_id", "notes", "collected_at"].forEach((k) => v[k] && f.append(k, v[k]));
    try { const r = await api("/evidence", { form: f }); toast(`${r.ref} preserved - SHA-256 ${r.sha256.slice(0, 12)}...`); onDone(); } catch (e: any) { setErr(e instanceof ApiError ? e.message : "Upload failed"); }
    setBusy(false);
  };
  return <Modal title="Preserve evidence" onClose={onClose}><div className="space-y-2.5">
    <label className="f block"><span>File (max 25 MB; images, PDF, text, HTML, Office)</span><input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>
    <label className="f block"><span>Evidence type</span><select value={v.evidence_type} onChange={(e) => setV({ ...v, evidence_type: e.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select></label>
    <label className="f block"><span>Description</span><textarea rows={2} value={v.description || ""} onChange={(e) => setV({ ...v, description: e.target.value })} /></label>
    <label className="f block"><span>Source (where was it captured from?)</span><select value={v.source_id || ""} onChange={(e) => setV({ ...v, source_id: e.target.value })}><option value="">- none -</option>{(refs.source || []).map((o: Rec) => <option key={o.id} value={o.id}>{o.ref} {o.label}</option>)}</select></label>
    <label className="f block"><span>Collected at (UTC, optional)</span><input placeholder="2026-10-07T14:30" value={v.collected_at || ""} onChange={(e) => setV({ ...v, collected_at: e.target.value })} /></label>
    <p className="text-xs text-mute">The file is hashed on import, stored outside the database and never executed or rendered as active content.</p>
    {err && <div className="text-xs text-bad">{err}</div>}
    <div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn><Btn kind="primary" disabled={busy} onClick={go}><Upload size={13} /> {busy ? "Hashing..." : "Preserve"}</Btn></div></div></Modal>;
}

function Detail({ id, refs, onClose, onChanged }: { id: string; refs: Rec; onClose: () => void; onChanged: () => void }) {
  const { toast, canWrite } = useApp(); const [e, setE] = useState<Rec | null>(null); const [cust, setCust] = useState<Rec[]>([]); const [pv, setPv] = useState<Rec | null>(null); const [del, setDel] = useState(false); const [note, setNote] = useState<Rec>({});
  const urlRef = useRef<string>("");
  const load = useCallback(async () => { const x = await api(`/evidence/${id}`); setE(x); setNote({ description: x.description, notes: x.notes, tags: x.tags, source_id: x.source_id || "", verification_status: x.verification_status }); setCust(await api(`/evidence/${id}/custody`)); }, [id]);
  useEffect(() => { load(); return () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current); }; }, [load]);
  const preview = async () => {
    try {
      const r = await fetch(`/api/evidence/${id}/preview`, { headers: { Authorization: "Bearer " + sessionStorage.getItem("ob_token") } });
      const ct = r.headers.get("content-type") || ""; if (!r.ok) throw new Error("Preview unavailable");
      if (ct.startsWith("application/json")) setPv(await r.json()); else { const u = URL.createObjectURL(await r.blob()); urlRef.current = u; setPv({ kind: ct.includes("pdf") ? "pdf" : "image", url: u }); }
      load();
    } catch (x: any) { toast(x.message, "err"); }
  };
  const verify = async () => { const r = await api(`/evidence/${id}/verify`, { method: "POST" }); toast(`Integrity ${r.result}`, r.result === "VALID" ? "ok" : "err"); load(); onChanged(); };
  const save = async () => { try { await api(`/evidence/${id}`, { method: "PATCH", body: note }); toast("Metadata saved (logged)"); load(); onChanged(); } catch (x: any) { toast(x.message, "err"); } };
  if (!e) return <Modal title="Evidence" onClose={onClose}><Loading /></Modal>;
  return <Modal wide title={`${e.ref} - ${e.evidence_type}`} onClose={onClose}>
    <div className="grid md:grid-cols-2 gap-3">
      <div className="space-y-3"><Dl rows={[["File", <span className="font-mono text-xs">{e.original_filename}</span>], ["Size", `${e.size.toLocaleString()} bytes`], ["Collected", fmtTs(e.collected_at)], ["Collector", e.collector], ["Source", refLabel(refs, "source", e.source_id)],
        ["SHA-256", <Hash v={e.sha256} />], ["Integrity", <span className="flex gap-2 items-center"><Status v={e.integrity_status} /><span className="text-xs text-mute">verified {fmtTs(e.last_verified)}</span></span>], ["Review", <Status v={e.verification_status} />],
        ["Linked findings", e.linked_findings.length ? e.linked_findings.map((f: Rec) => <div key={f.id}><Mono>{f.ref}</Mono> {f.title}</div>) : "none"]]} />
        <div className="flex flex-wrap gap-1.5">{!e.deleted_at && <><Btn onClick={verify}><ShieldCheck size={13} /> Verify hash</Btn><Btn onClick={preview}><Eye size={13} /> Preview</Btn><Btn onClick={() => download(`/evidence/${id}/download`, e.original_filename).catch((x) => toast(x.message, "err"))}><Download size={13} /> Download</Btn></>}
          {canWrite && !e.deleted_at && <Btn kind="danger" onClick={() => setDel(true)}><Trash2 size={13} /> Secure delete</Btn>}</div>
        {canWrite && !e.deleted_at && <div className="space-y-2 border-t border-line pt-2"><div className="text-xs text-mute">Editable metadata (file and hash are immutable; edits are logged)</div>
          <input aria-label="Description" value={note.description || ""} onChange={(x) => setNote({ ...note, description: x.target.value })} placeholder="Description" /><input aria-label="Tags" value={note.tags || ""} onChange={(x) => setNote({ ...note, tags: x.target.value })} placeholder="Tags" />
          <select aria-label="Review status" value={note.verification_status} onChange={(x) => setNote({ ...note, verification_status: x.target.value })}><option>Pending</option><option>Verified</option><option>Disputed</option></select>
          <textarea rows={2} aria-label="Notes" value={note.notes || ""} onChange={(x) => setNote({ ...note, notes: x.target.value })} placeholder="Notes" /><Btn kind="primary" small onClick={save}>Save metadata</Btn></div>}</div>
      <div className="space-y-3">
        {pv && <Panel title="Preview" pad>{pv.kind === "image" ? <img src={pv.url} alt={e.description || e.ref} className="max-w-full border border-line" /> : pv.kind === "pdf" ? <iframe title="pdf" src={pv.url} sandbox="" className="w-full h-72 border border-line" /> :
          <pre className="text-xs font-mono whitespace-pre-wrap break-all max-h-72 overflow-auto bg-bg p-2 border border-line">{pv.text}</pre>}{pv.kind === "text" && <div className="text-xs text-mute mt-1">Shown as inert text. Active content is never rendered.</div>}</Panel>}
        <Panel title="Chain of custody" pad={false}><div className="max-h-72 overflow-auto"><table className="w-full"><tbody>{cust.map((c, i) => <tr key={i}><td className="font-mono text-xs whitespace-nowrap">{fmtTime(c.ts)}</td><td className="text-xs">{c.action.replaceAll("_", " ")}<div className="text-mute">{c.user}</div></td></tr>)}</tbody></table></div></Panel>
        <Panel title="Hash history" pad={false}><div className="max-h-40 overflow-auto"><table className="w-full"><tbody>{e.hash_history.map((h: Rec, i: number) => <tr key={i}><td className="text-xs whitespace-nowrap">{fmtTs(h.at)}</td><td className="text-xs">{h.kind}</td><td><Status v={h.result} /></td></tr>)}</tbody></table></div></Panel></div></div>
    {del && <Confirm danger title={`Securely delete ${e.ref}?`} confirm="Delete file" body="The stored file is overwritten and removed. A metadata tombstone with the original hash stays for chain of custody. This cannot be undone." onYes={async () => { await api(`/evidence/${id}`, { method: "DELETE" }); toast("Evidence deleted"); onChanged(); onClose(); }} onClose={() => setDel(false)} />}
  </Modal>;
}

export default function Evidence() {
  const { caseId, activeCase, canWrite, toast, cases } = useApp(); const { refs, reload } = useRefs(caseId);
  const [d, setD] = useState<Rec | null>(null); const [q, setQ] = useState(""); const dq = useDebounced(q); const [et, setEt] = useState(""); const [integ, setInteg] = useState(""); const [ver, setVer] = useState(""); const [page, setPage] = useState(1);
  const [up, setUp] = useState(false); const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(async () => { try { setD(await api("/evidence" + qs({ case_id: caseId, q: dq, evidence_type: et, integrity: integ, verification: ver, page, size: 40 }))); } catch (e: any) { toast(e.message, "err"); setD({ items: [], total: 0 }); } }, [caseId, dq, et, integ, ver, page, toast]);
  useEffect(() => { setPage(1); }, [caseId, dq, et, integ, ver]); useEffect(() => { load(); }, [load]);
  const verifyAll = async () => { const r = await api(`/evidence/verify-all${qs({ case_id: caseId })}`, { method: "POST" }); const bad = r.filter((x: Rec) => x.result !== "VALID").length; toast(bad ? `${bad} item(s) failed verification` : `All ${r.length} items VALID`, bad ? "err" : "ok"); load(); };
  const cref = (id: string) => cases.find((c) => c.id === id)?.ref;
  return <div><PageHead title="Evidence" sub={activeCase ? <>Case <Mono>{activeCase.ref}</Mono></> : "All accessible cases"} actions={<>{caseId && <Btn onClick={verifyAll}><ShieldCheck size={14} /> Verify all</Btn>}{canWrite && <Btn kind="primary" disabled={!caseId} title={caseId ? "" : "Select a case first"} onClick={() => setUp(true)}><Upload size={14} /> Preserve evidence</Btn>}</>} />
    <Panel pad={false}><div className="flex gap-2 p-2 border-b border-line flex-wrap"><input className="flex-1 min-w-[160px]" placeholder="Search ID, description, filename, hash prefix" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search evidence" />
      <select className="w-auto" value={et} onChange={(e) => setEt(e.target.value)} aria-label="Type"><option value="">Type: any</option>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>
      <select className="w-auto" value={integ} onChange={(e) => setInteg(e.target.value)} aria-label="Integrity"><option value="">Integrity: any</option>{["VALID", "MISMATCH", "MISSING", "DELETED"].map((t) => <option key={t}>{t}</option>)}</select>
      <select className="w-auto" value={ver} onChange={(e) => setVer(e.target.value)} aria-label="Review"><option value="">Review: any</option>{["Pending", "Verified", "Disputed"].map((t) => <option key={t}>{t}</option>)}</select></div>
      {!d ? <Loading /> : d.items.length === 0 ? <Empty title="No evidence" hint="Preserve screenshots, captures and tool output here. Each file is hashed and its custody tracked from the first moment." /> :
        <table className="w-full"><thead><tr>{!caseId && <th>Case</th>}<th>ID</th><th>Type</th><th>Description</th><th>Source</th><th>SHA-256</th><th>Integrity</th><th>Review</th><th>Collected</th></tr></thead><tbody>{d.items.map((e: Rec) => (
          <tr key={e.id} className="cursor-pointer" onClick={() => setOpen(e.id)}>{!caseId && <td><Mono className="text-mute">{cref(e.case_id)}</Mono></td>}<td><Mono>{e.ref}</Mono></td><td><FileText size={12} className="inline mr-1 text-mute" />{e.evidence_type}</td><td>{e.description}<div className="font-mono text-xs text-mute">{e.original_filename}</div></td>
            <td>{refLabel(refs, "source", e.source_id)}</td><td className="font-mono text-xs text-mute">{e.sha256.slice(0, 16)}...</td><td><Status v={e.integrity_status} /></td><td><Status v={e.verification_status} /></td><td className="text-mute">{fmtTs(e.collected_at)}</td></tr>))}</tbody></table>}
      {d && <div className="px-2 pb-2"><Pager page={page} size={40} total={d.total} onPage={setPage} /></div>}</Panel>
    {up && <UploadForm caseId={caseId} refs={refs} onClose={() => setUp(false)} onDone={() => { setUp(false); load(); reload(); }} />}
    {open && <Detail id={open} refs={refs} onClose={() => setOpen(null)} onChanged={() => { load(); reload(); }} />}</div>;
}
