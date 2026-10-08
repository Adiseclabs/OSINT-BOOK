import { useCallback, useEffect, useState } from "react";
import { Link2, Sparkles, Check, X as XIcon, ShieldCheck } from "lucide-react";
import { api, Rec, qs } from "../lib";
import { useApp } from "../ctx";
import { FindingsTable } from "./Entities";
import { Btn, Modal, Kind, Mono, Hash, Status, Loading, Empty, Panel, AIBadge, Tag, Certainty } from "../ui";

export function ProvenanceModal({ f, onClose }: { f: Rec; onClose: () => void }) {
  const { toast, canWrite } = useApp();
  const [p, setP] = useState<Rec | null>(null); const [opts, setOpts] = useState<Rec>({ evidence: [], source: [] }); const [sel, setSel] = useState("");
  const load = useCallback(async () => { setP(await api(`/findings/${f.id}/provenance`)); }, [f.id]);
  useEffect(() => { load(); api("/entities" + qs({ case_id: f.case_id })).then((e: Rec[]) => setOpts({ evidence: e.filter((x) => x.type === "evidence"), source: e.filter((x) => x.type === "source") })); }, [f.case_id, load]);
  const add = async () => { const [t, id] = sel.split(":"); try { await api(`/findings/${f.id}/links`, { body: { target_type: t, target_id: id } }); setSel(""); load(); toast("Linked"); } catch (e: any) { toast(e.message, "err"); } };
  const rm = async (t: string, id: string) => { await api(`/findings/${f.id}/links/${t}/${id}`, { method: "DELETE" }); load(); };
  return <Modal wide title={`Provenance - ${f.ref}`} onClose={onClose}>
    {!p ? <Loading /> : <div className="space-y-3">
      <div><div className="text-xs text-mute mb-0.5">Claim</div><div className="flex gap-2 items-start"><Kind v={p.kind} /><span>{p.claim}</span><Status v={p.confidence} /></div></div>
      {!p.sources.length && !p.evidence.length && <div className="border border-warn/60 text-warn text-sm p-2">UNSUPPORTED - link at least one source or evidence item. Reports flag unsupported findings.</div>}
      <div><div className="text-xs text-mute mb-1">Sources</div>{p.sources.length === 0 ? <div className="text-xs text-mute">None linked.</div> : p.sources.map((s: Rec) => (
        <div key={s.id} className="border border-line p-2 mb-1 flex justify-between gap-2"><div><Mono>{s.ref}</Mono> {s.title}<div className="font-mono text-xs text-mute break-all">{s.url}</div><div className="text-xs">Observed {s.access_date || "-"} - reliability <Status v={s.reliability} /></div></div>
          {canWrite && <Btn small kind="ghost" onClick={() => rm("source", s.id)} aria-label="Unlink source"><XIcon size={13} /></Btn>}</div>))}</div>
      <div><div className="text-xs text-mute mb-1">Evidence</div>{p.evidence.length === 0 ? <div className="text-xs text-mute">None linked.</div> : p.evidence.map((e: Rec) => (
        <div key={e.id} className="border border-line p-2 mb-1 flex justify-between gap-2"><div><Mono>{e.ref}</Mono> {e.description}<div className="text-xs mt-0.5">SHA-256 <Hash v={e.sha256} /></div><div className="text-xs">Integrity <Status v={e.integrity} /></div></div>
          {canWrite && <Btn small kind="ghost" onClick={() => rm("evidence", e.id)} aria-label="Unlink evidence"><XIcon size={13} /></Btn>}</div>))}</div>
      {canWrite && <div className="flex gap-2"><select value={sel} onChange={(e) => setSel(e.target.value)} aria-label="Item to link"><option value="">Link a source or evidence item...</option>
        <optgroup label="Sources">{opts.source.map((o: Rec) => <option key={o.id} value={"source:" + o.id}>{o.ref} {o.label}</option>)}</optgroup><optgroup label="Evidence">{opts.evidence.map((o: Rec) => <option key={o.id} value={"evidence:" + o.id}>{o.ref} {o.label}</option>)}</optgroup></select>
        <Btn kind="primary" disabled={!sel} onClick={add}>Link</Btn></div>}
    </div>}
  </Modal>;
}

export function FindingsPanel({ onChanged }: { onChanged?: () => void }) {
  const [prov, setProv] = useState<Rec | null>(null); const [k, setK] = useState(0);
  return <>
    <FindingsTable key={k} onChanged={onChanged} />
    <ExtraProv setProv={setProv} />
    {prov && <ProvenanceModal f={prov} onClose={() => { setProv(null); setK(k + 1); }} />}
  </>;
}
// Provenance opens from a dedicated selector so the generic table stays generic.
function ExtraProv({ setProv }: { setProv: (f: Rec) => void }) {
  const { caseId } = useApp(); const [fs, setFs] = useState<Rec[]>([]);
  useEffect(() => { if (caseId) api("/findings" + qs({ case_id: caseId, size: 200 })).then((r) => setFs(r.items)); }, [caseId]);
  if (!fs.length) return null;
  return <div className="mt-3 flex items-center gap-2 text-xs text-mute"><ShieldCheck size={14} /> Source provenance for:
    <select className="w-auto" defaultValue="" onChange={(e) => { const f = fs.find((x) => x.id === e.target.value); if (f) setProv(f); e.target.value = ""; }} aria-label="Open finding provenance"><option value="">choose a finding</option>{fs.map((f) => <option key={f.id} value={f.id}>{f.ref} {f.title}</option>)}</select></div>;
}

const TASKS = [["summarize", "Summarize sources & evidence"], ["entities", "Find unrecorded domains / entities"], ["duplicates", "Find duplicate identifiers"], ["timeline", "Suggest timeline events"], ["relationships", "Suggest relationships"], ["findings", "Draft hypotheses from suggestions"]];
export function AIPanel() {
  const { caseId, toast, canWrite } = useApp();
  const [items, setItems] = useState<Rec[] | null>(null); const [busy, setBusy] = useState("");
  const load = useCallback(async () => { if (caseId) setItems(await api("/ai/suggestions" + qs({ case_id: caseId }))); }, [caseId]);
  useEffect(() => { load(); }, [load]);
  const run = async (t: string) => { setBusy(t); try { const r = await api("/ai/analyze", { body: { case_id: caseId, task: t } }); toast(r.length ? `${r.length} suggestion(s) added for review` : "Nothing new to suggest"); load(); } catch (e: any) { toast(e.message, "err"); } setBusy(""); };
  const act = async (id: string, a: string) => { try { const r = await api(`/ai/suggestions/${id}/${a}`, { method: "POST" }); toast(a === "approve" ? `Approved${r.created ? " - created " + r.created : ""}` : "Rejected"); load(); } catch (e: any) { toast(e.message, "err"); } };
  return <div className="space-y-3">
    <div className="text-xs text-mute max-w-2xl">The assistant only proposes. Nothing becomes a finding, relationship or timeline event until an analyst approves it, and approved findings stay marked AI-assisted. Runs locally; connect a local model in Settings (Ollama) for summaries.</div>
    {canWrite && <div className="flex flex-wrap gap-1.5">{TASKS.map(([id, label]) => <Btn key={id} disabled={!!busy} onClick={() => run(id)}><Sparkles size={13} />{busy === id ? "Working..." : label}</Btn>)}</div>}
    {!items ? <Loading /> : items.length === 0 ? <Empty title="No suggestions yet" hint="Run an assistant task above." /> : (
      <div className="space-y-1.5">{items.map((s) => <Panel key={s.id} className={s.status !== "Pending" ? "opacity-60" : ""}>
        <div className="flex justify-between gap-3"><div className="min-w-0"><div className="flex gap-2 items-center mb-1"><AIBadge /><Tag>{s.kind}</Tag><Mono className="text-mute">{s.ref} - {s.origin}</Mono><Status v={s.status} /></div>
          <div className="text-sm whitespace-pre-wrap break-words">{s.payload.title || s.payload.name || s.payload.text || (s.payload.rel_type && `${s.payload.labels?.join(" -> ")} ${s.payload.rel_type}`)}</div>
          {s.payload.certainty && <div className="mt-1"><Certainty v={s.payload.certainty} pct={s.payload.confidence_pct} /></div>}
          {(s.payload.reasoning || s.payload.description) && <div className="text-xs text-mute mt-1">{s.payload.reasoning || s.payload.description}</div>}</div>
          {canWrite && s.status === "Pending" && s.kind !== "summary" && <div className="flex gap-1 shrink-0"><Btn small kind="primary" onClick={() => act(s.id, "approve")}><Check size={12} /> Approve</Btn><Btn small onClick={() => act(s.id, "reject")}>Reject</Btn></div>}
          {canWrite && s.status === "Pending" && s.kind === "summary" && <Btn small onClick={() => act(s.id, "reject")}>Dismiss</Btn>}</div></Panel>)}</div>)}
  </div>;
}
