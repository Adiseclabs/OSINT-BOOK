import { useCallback, useEffect, useState } from "react";
import { Play, Paperclip, Globe, Network, Fingerprint, FileSearch, Brain } from "lucide-react";
import { api, qs, Rec, fmtTime } from "../lib";
import { useApp } from "../ctx";
import { useRefs } from "../EntityPage";
import { Btn, Dl, Empty, Loading, Mono, PageHead, Panel, Status, Tag, Modal } from "../ui";

const ICON: Rec = { "Domain / Network": Network, Web: Globe, "Identifier research": Fingerprint, "Document analysis": FileSearch, Analysis: Brain };

function Value({ v, depth = 0 }: { v: any; depth?: number }) {
  if (v === null || v === undefined || v === "") return <span className="text-mute">-</span>;
  if (Array.isArray(v)) return v.length === 0 ? <span className="text-mute">none</span> : <ul className="space-y-0.5">{v.slice(0, 80).map((x, i) => <li key={i} className={typeof x === "object" ? "border-l border-line pl-2" : "font-mono text-xs break-all"}><Value v={x} depth={depth + 1} /></li>)}{v.length > 80 && <li className="text-mute text-xs">+{v.length - 80} more (in saved evidence)</li>}</ul>;
  if (typeof v === "object") return <dl className="grid grid-cols-[130px_1fr] gap-x-2 gap-y-0.5">{Object.entries(v).map(([k, x]) => <div className="contents" key={k}><dt className="text-xs text-mute pt-0.5">{k.replaceAll("_", " ")}</dt><dd className="text-sm min-w-0 break-words"><Value v={x} depth={depth + 1} /></dd></div>)}</dl>;
  if (typeof v === "boolean") return <span>{v ? "yes" : "no"}</span>;
  return <span className={String(v).length > 30 || /[./:@]/.test(String(v)) ? "font-mono text-xs break-all whitespace-pre-wrap" : ""}>{String(v)}</span>;
}

export function RunView({ run, onAttach }: { run: Rec; onAttach?: () => void }) {
  const r = run.result;
  return <div className="space-y-2">
    <Dl rows={[["Tool run", <Mono>{run.ref}</Mono>], ["Tool", run.tool], ["Input", <span className="font-mono text-xs">{JSON.stringify(run.input)}</span>], ["Started", fmtTime(run.started_at)], ["Finished", fmtTime(run.finished_at)], ["Status", <Status v={run.status} />], ["Investigator", run.username],
      ...(r ? [["Result ID", <Mono>{r.ref}</Mono>] as [string, any], ["Summary", r.summary] as [string, any]] : [])]} />
    {run.status === "Failed" && <div className="border border-bad/60 text-bad text-sm p-2">{run.error}</div>}
    {r && <div className="border-t border-line pt-2"><Value v={r.data} /></div>}</div>;
}

export default function Tools() {
  const { caseId, activeCase, canWrite, toast } = useApp(); const { refs } = useRefs(caseId);
  const [cat, setCat] = useState<Rec | null>(null); const [tool, setTool] = useState<Rec | null>(null); const [inp, setInp] = useState<Rec>({}); const [busy, setBusy] = useState(false); const [run, setRun] = useState<Rec | null>(null); const [runs, setRuns] = useState<Rec[] | null>(null); const [attach, setAttach] = useState(false); const [asEv, setAsEv] = useState(true);
  const loadRuns = useCallback(async () => setRuns((await api("/tools/runs" + qs({ case_id: caseId, size: 25 }))).items), [caseId]);
  useEffect(() => { api("/tools").then((c) => { setCat(c); setTool(Object.values(c as Rec)[0][0]); }); }, []); useEffect(() => { loadRuns(); }, [loadRuns]);
  const exec = async () => {
    setBusy(true); setRun(null);
    try { const r = await api("/tools/run", { body: { tool: tool!.id, input: { ...inp, ...(tool!.inputs.some((i: Rec) => i.type === "case") ? { case_id: caseId } : {}) }, case_id: caseId || undefined } }); setRun(r); loadRuns(); } catch (e: any) { toast(e.message, "err"); }
    setBusy(false);
  };
  const doAttach = async () => { try { const r = await api(`/tools/results/${run!.result.id}/attach`, { body: { case_id: caseId, as_evidence: asEv } }); setRun(r); toast(asEv ? "Attached and preserved as evidence" : "Attached to case"); setAttach(false); loadRuns(); } catch (e: any) { toast(e.message, "err"); } };
  const opts = (t: string) => (t === "account" ? refs.account : t === "evidence" ? refs.evidence : []) || [];
  return <div><PageHead title="OSINT tools" sub={<>Passive, public-source collection. Results are structured records, not terminal output. {activeCase ? <>Attach to <Mono>{activeCase.ref}</Mono>.</> : "Select a case to attach results."}</>} />
    {!cat ? <Loading /> : <div className="grid lg:grid-cols-[250px_1fr] gap-3">
      <Panel pad={false}><nav className="max-h-[calc(100vh-190px)] overflow-auto" aria-label="Tools">{Object.entries(cat).map(([c, ts]: [string, any]) => { const I = ICON[c] || Globe; return <div key={c}><div className="flex items-center gap-1.5 px-3 pt-2 pb-1 text-xs text-mute"><I size={12} />{c}</div>{ts.map((t: Rec) => <button key={t.id} onClick={() => { setTool(t); setInp({}); setRun(null); }} className={`block w-full text-left px-3 py-1 text-sm border-l-2 ${tool?.id === t.id ? "border-accent bg-raised" : "border-transparent hover:bg-raised/60"}`}>{t.name}</button>)}</div>; })}</nav></Panel>
      <div className="space-y-3 min-w-0">{tool && <Panel title={tool.name}><p className="text-xs text-mute mb-2">{tool.description}</p>
        <form className="grid grid-cols-2 gap-2.5" onSubmit={(e) => { e.preventDefault(); exec(); }}>{tool.inputs.filter((i: Rec) => i.type !== "case").map((i: Rec) => <label key={i.name} className={`f block ${i.type === "textarea" ? "col-span-2" : ""}`}><span>{i.label}{i.required && <b className="text-bad"> *</b>}</span>
          {i.type === "textarea" ? <textarea rows={5} value={inp[i.name] || ""} onChange={(e) => setInp({ ...inp, [i.name]: e.target.value })} /> : i.type === "account" || i.type === "evidence" ? <select value={inp[i.name] || ""} onChange={(e) => setInp({ ...inp, [i.name]: e.target.value })}><option value="">{caseId ? "-" : "select a case first"}</option>{opts(i.type).map((o: Rec) => <option key={o.id} value={o.id}>{o.ref} {o.label}</option>)}</select> : <input value={inp[i.name] || ""} onChange={(e) => setInp({ ...inp, [i.name]: e.target.value })} />}</label>)}
          <div className="col-span-2 flex gap-2 items-center"><Btn kind="primary" type="submit" disabled={busy || !canWrite || (tool.inputs.some((i: Rec) => i.type === "case") && !caseId)}><Play size={13} /> {busy ? "Running..." : "Run"}</Btn>{!canWrite && <span className="text-xs text-mute">Read-only account</span>}{tool.inputs.some((i: Rec) => i.type === "case") && !caseId && <span className="text-xs text-warn">Select a case first</span>}</div></form></Panel>}
        {run && <Panel title="Result" actions={run.result && canWrite && (run.result.attached_case_id ? <Tag tone="ok">attached</Tag> : <Btn small kind="primary" disabled={!caseId} onClick={() => setAttach(true)} title={caseId ? "" : "Select a case"}><Paperclip size={12} /> Attach to case</Btn>)}><RunView run={run} /></Panel>}
        <Panel title="Recent tool runs" pad={false}>{!runs ? <Loading /> : runs.length === 0 ? <Empty title="No runs yet" hint="Every execution is recorded with its input, time and investigator." /> :
          <table className="w-full"><thead><tr><th>Run</th><th>Tool</th><th>Input</th><th>Time</th><th>Status</th><th>By</th></tr></thead><tbody>{runs.map((r) => <tr key={r.id} className="cursor-pointer" onClick={() => setRun(r)}><td><Mono>{r.ref}</Mono></td><td>{r.tool}</td><td className="font-mono text-xs max-w-[240px] truncate">{Object.values(r.input).join(" ")}</td><td className="text-mute">{fmtTime(r.started_at)}</td><td><Status v={r.status} /></td><td>{r.username}</td></tr>)}</tbody></table>}</Panel></div></div>}
    {attach && <Modal title="Attach result to case" onClose={() => setAttach(false)}><p className="text-sm mb-2">Attach <Mono>{run?.result?.ref}</Mono> to <Mono>{activeCase?.ref}</Mono>.</p><label className="flex gap-2 text-sm items-start"><input type="checkbox" checked={asEv} onChange={(e) => setAsEv(e.target.checked)} /><span>Also preserve as hashed evidence (JSON with tool, input, timestamps and result). Recommended.</span></label><div className="flex justify-end gap-2 mt-4"><Btn onClick={() => setAttach(false)}>Cancel</Btn><Btn kind="primary" onClick={doAttach}>Attach</Btn></div></Modal>}</div>;
}
