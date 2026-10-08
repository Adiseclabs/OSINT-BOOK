import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Rec, fmtTs } from "../lib";
import { useApp } from "../ctx";
import { Empty, Kind, Loading, Mono, PageHead, Panel, Status, Certainty, Tag } from "../ui";

const Row = ({ children, to }: { children: any; to?: string }) => { const c = <div className="px-3 py-1.5 border-b border-line/60 last:border-0 hover:bg-raised/50">{children}</div>; return to ? <Link to={to}>{c}</Link> : c; };
export default function Dashboard() {
  const { setCaseId, user } = useApp(); const nav = useNavigate(); const [d, setD] = useState<Rec | null>(null);
  useEffect(() => { api("/dashboard").then(setD); }, []);
  if (!d) return <Loading />;
  const open = (id: string) => { setCaseId(id); nav(`/cases/${id}`); }; const total = Object.values(d.integrity as Rec).reduce((a: number, b: any) => a + b, 0);
  return <div><PageHead title="Dashboard" sub={`Signed in as ${user?.display_name}`} />
    <div className="grid xl:grid-cols-3 lg:grid-cols-2 gap-3">
      <Panel title="Active cases" pad={false} className="xl:col-span-2">{d.active_cases.length === 0 ? <Empty title="No active cases" action={<Link className="text-accent" to="/cases">Open cases</Link>} /> : d.active_cases.map((c: Rec) => (
        <button key={c.id} onClick={() => open(c.id)} className="w-full text-left px-3 py-2 border-b border-line/60 last:border-0 hover:bg-raised/50 flex justify-between gap-3"><div><Mono>{c.ref}</Mono> <b className="font-medium">{c.title}</b><div className="text-xs text-mute">{c.case_type} - stage <Tag>{c.stage}</Tag></div></div>
          <div className="text-right text-xs shrink-0"><div className="flex gap-1.5 justify-end"><Status v={c.status} /><Status v={c.priority} /></div><div className="text-mute mt-0.5">Last activity {fmtTs(c.last_activity)}</div></div></button>))}</Panel>
      <Panel title="Evidence integrity">{total === 0 ? <div className="text-sm text-mute">No evidence preserved.</div> : <div className="space-y-1.5">{Object.entries(d.integrity as Rec).map(([k, v]) => <div key={k} className="flex items-center gap-2 text-sm"><span className="w-24"><Status v={k} /></span><div className="flex-1 h-1.5 bg-raised"><div className={k === "VALID" ? "bg-ok h-full" : "bg-bad h-full"} style={{ width: `${((v as number) / total) * 100}%` }} /></div><b className="font-mono w-6 text-right">{v as number}</b></div>)}
        <div className="text-xs text-mute pt-1">Run <i>Verify all</i> on a case to refresh. Mismatches mean a stored file no longer matches its import hash.</div></div>}</Panel>
      <Panel title="Pending verification" pad={false}>{d.pending_verification.length === 0 ? <Empty title="Nothing awaiting review" /> : d.pending_verification.map((e: Rec) => <Row key={e.id} to="/evidence"><Mono>{e.ref}</Mono> {e.description || e.original_filename}</Row>)}</Panel>
      <Panel title="High-priority findings" pad={false}>{d.priority_findings.length === 0 ? <Empty title="No high or critical findings" /> : d.priority_findings.map((f: Rec) => <Row key={f.id}><div className="flex gap-2 items-center"><Kind v={f.kind} /><span>{f.title}</span><Status v={f.severity} /></div></Row>)}</Panel>
      <Panel title="Unverified claims" pad={false}>{d.unverified_claims.length === 0 ? <Empty title="No open inferences" /> : d.unverified_claims.map((f: Rec) => <Row key={f.id}><div className="flex gap-2 items-center"><Kind v={f.kind} /><span>{f.title}</span></div></Row>)}</Panel>
      <Panel title="Unresolved relationships" pad={false}>{d.unresolved_relationships.length === 0 ? <Empty title="All relationships confirmed" /> : d.unresolved_relationships.map((r: Rec) => <Row key={r.id} to="/relationships"><Mono>{r.ref}</Mono> {r.rel_type} <Certainty v={r.certainty} pct={r.confidence_pct} /></Row>)}</Panel>
      <Panel title={`Recently added sources${d.sources_today ? ` (${d.sources_today} today)` : ""}`} pad={false}>{d.recent_sources.length === 0 ? <Empty title="No sources" /> : d.recent_sources.map((s: Rec) => <Row key={s.id} to="/sources"><Mono>{s.ref}</Mono> {s.title}</Row>)}</Panel>
      <Panel title="Open tasks" pad={false}>{d.open_tasks.length === 0 ? <Empty title="No open tasks" /> : d.open_tasks.map((t: Rec) => <Row key={t.id} to="/tasks"><div className="flex justify-between"><span><Tag>{t.stage}</Tag> {t.title}</span><span className="text-xs text-mute">{t.due_date}</span></div></Row>)}</Panel>
      <Panel title="Recent evidence" pad={false}>{d.recent_evidence.length === 0 ? <Empty title="No evidence" /> : d.recent_evidence.map((e: Rec) => <Row key={e.id} to="/evidence"><Mono>{e.ref}</Mono> {e.description || e.original_filename} <Status v={e.integrity_status} /></Row>)}</Panel>
      {d.ai_pending > 0 && <Panel title="AI suggestions"><span className="text-sm">{d.ai_pending} AI-generated suggestion(s) await analyst review.</span></Panel>}
    </div></div>;
}
