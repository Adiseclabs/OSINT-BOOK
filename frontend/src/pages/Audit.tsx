import { useCallback, useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api, qs, Rec, fmtTs } from "../lib";
import { useApp } from "../ctx";
import { Btn, Empty, Loading, Mono, PageHead, Pager, Panel, useDebounced } from "../ui";

export default function Audit() {
  const { caseId, user, toast } = useApp(); const [d, setD] = useState<Rec | null>(null); const [q, setQ] = useState(""); const dq = useDebounced(q); const [action, setAction] = useState(""); const [page, setPage] = useState(1); const [open, setOpen] = useState<number | null>(null);
  const load = useCallback(async () => setD(await api("/audit" + qs({ case_id: caseId, q: dq, action, page, size: 100 }))), [caseId, dq, action, page]);
  useEffect(() => { setPage(1); }, [caseId, dq, action]); useEffect(() => { load(); }, [load]);
  const verify = async () => { const r = await api("/audit/verify"); toast(r.valid ? `Audit chain intact (${r.checked} records)` : `Chain broken at record ${r.broken_at}`, r.valid ? "ok" : "err"); };
  return <div><PageHead title="Audit log" sub="Append-only and hash-chained. Records cannot be edited or deleted." actions={user?.role === "admin" && <Btn onClick={verify}><ShieldCheck size={14} /> Verify chain</Btn>} />
    <Panel pad={false}><div className="flex gap-2 p-2 border-b border-line"><input placeholder="Search record ID or user" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search audit" /><input className="!w-56" placeholder="Action, e.g. VIEWED" value={action} onChange={(e) => setAction(e.target.value.toUpperCase())} aria-label="Action" /></div>
      {!d ? <Loading /> : d.items.length === 0 ? <Empty title="No audit records match" /> : <table className="w-full"><thead><tr><th>Time (UTC)</th><th>User</th><th>Action</th><th>Record</th><th>Hash</th></tr></thead><tbody>{d.items.map((a: Rec) => <>
        <tr key={a.id} className="cursor-pointer" onClick={() => setOpen(open === a.id ? null : a.id)}><td className="font-mono text-xs whitespace-nowrap">{fmtTs(a.ts)}:{a.ts.slice(17, 19)}</td><td>{a.user}</td><td>{a.action.replaceAll("_", " ")}</td><td><Mono>{a.entity_ref}</Mono> <span className="text-mute text-xs">{a.entity_type}</span></td><td className="font-mono text-xs text-mute">{a.hash}</td></tr>
        {open === a.id && <tr key={a.id + "d"}><td colSpan={5}><pre className="text-xs font-mono bg-bg border border-line p-2 whitespace-pre-wrap break-all">{JSON.stringify(a.detail, null, 2)}</pre></td></tr>}</>)}</tbody></table>}
      {d && <div className="px-2 pb-2"><Pager page={page} size={100} total={d.total} onPage={setPage} /></div>}</Panel></div>;
}
