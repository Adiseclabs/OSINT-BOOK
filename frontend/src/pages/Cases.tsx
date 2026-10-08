import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Plus, ChevronRight, ShieldCheck } from "lucide-react";
import { api, qs, Rec, ApiError, fmtTs, STAGES, PRIORITIES, CASE_STATUS, CASE_TYPES } from "../lib";
import { useApp } from "../ctx";
import { Btn, Dl, Empty, Field, FieldDef, Loading, Modal, Mono, PageHead, Pager, Panel, Status, Tabs, Tag, TLP, useDebounced } from "../ui";
import { FindingsPanel, AIPanel } from "./Findings";
import { EntityPage } from "../EntityPage";
import { sourceFields } from "./Entities";
import Analytics from "./Analytics";

export const caseFields: FieldDef[] = [
  { name: "title", label: "Title", req: true }, { name: "case_type", label: "Case type", type: "select", options: CASE_TYPES, half: true, help: "Impersonation, alias, incident and due-diligence types add a starter task list." }, { name: "priority", label: "Priority", type: "select", options: PRIORITIES, half: true },
  { name: "status", label: "Status", type: "select", options: CASE_STATUS, half: true }, { name: "tlp", label: "Sharing marking (TLP)", type: "select", options: ["CLEAR", "GREEN", "AMBER", "AMBER+STRICT", "RED"], req: true, half: true }, { name: "tags", label: "Tags", type: "list", half: true }, { name: "start_date", label: "Start date", type: "date", half: true }, { name: "target_date", label: "Target completion", type: "date", half: true },
  { name: "description", label: "Description", type: "textarea" }, { name: "objectives", label: "Objectives", type: "textarea" }, { name: "scope", label: "Scope", type: "textarea", help: "What is in and out of scope? Public sources only." },
  { name: "authorization_notes", label: "Legal / authorization notes", type: "textarea", req: true, help: "Who authorized this investigation and on what basis?" }];

export function Stepper({ stage, onPick }: { stage: string; onPick?: (s: string) => void }) {
  const i = STAGES.indexOf(stage);
  return <ol className="flex text-xs border border-line  overflow-hidden bg-panel" aria-label="Analyst workflow">{STAGES.map((s, n) => (
    <li key={s} className="flex-1"><button disabled={!onPick} onClick={() => onPick?.(s)} aria-current={n === i ? "step" : undefined}
      className={`w-full px-1 py-1 border-r border-line last:border-r-0 text-center ${n === i ? "bg-accent text-bg font-medium" : n < i ? "text-ink bg-raised" : "text-mute"} ${onPick ? "hover:opacity-80" : ""}`}>{s}</button></li>))}</ol>;
}

export function CaseForm({ rec, onClose, onSaved }: { rec: Rec; onClose: () => void; onSaved: (c: Rec) => void }) {
  const { toast } = useApp(); const isNew = !rec.id;
  const [v, setV] = useState<Rec>({ case_type: "General", priority: "Medium", status: "Draft", tlp: "AMBER", ...rec }); const [errs, setErrs] = useState<Rec>({}); const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true); setErrs({}); const body: Rec = {}; caseFields.forEach((f) => { if (v[f.name] !== undefined) body[f.name] = v[f.name]; });
    try { const c = isNew ? await api("/cases", { body }) : await api(`/cases/${rec.id}`, { method: "PATCH", body }); toast(`${c.ref} saved`); onSaved(c); } catch (e: any) { if (e instanceof ApiError && Object.keys(e.fields).length) setErrs(e.fields); else toast(e.message, "err"); }
    setBusy(false);
  };
  return <Modal wide title={isNew ? "New case" : `Edit ${rec.ref}`} onClose={onClose}><form onSubmit={(e) => { e.preventDefault(); save(); }}>
    <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">{caseFields.map((f) => <Field key={f.name} f={f} value={v[f.name]} error={errs[f.name]} onChange={(x) => setV({ ...v, [f.name]: x })} />)}</div>
    <div className="flex justify-end gap-2 mt-4"><Btn type="button" onClick={onClose}>Cancel</Btn><Btn kind="primary" type="submit" disabled={busy}>{busy ? "Saving..." : "Save case"}</Btn></div></form></Modal>;
}

export function CaseList() {
  const nav = useNavigate(); const { canWrite, setCaseId, refreshCases } = useApp();
  const [d, setD] = useState<Rec | null>(null); const [q, setQ] = useState(""); const dq = useDebounced(q); const [status, setStatus] = useState(""); const [priority, setPriority] = useState(""); const [page, setPage] = useState(1); const [form, setForm] = useState(false);
  const load = useCallback(async () => setD(await api("/cases" + qs({ q: dq, status, priority, page, size: 30 }))), [dq, status, priority, page]);
  useEffect(() => { setPage(1); }, [dq, status, priority]); useEffect(() => { load(); }, [load]);
  return <div><PageHead title="Cases" sub="Every investigation is a case. Records, evidence and findings live inside it." actions={canWrite && <Btn kind="primary" onClick={() => setForm(true)}><Plus size={14} /> New case</Btn>} />
    <Panel pad={false}><div className="flex gap-2 p-2 border-b border-line"><input placeholder="Search cases" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search cases" />
      <select className="w-auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="">Status: any</option>{CASE_STATUS.map((s) => <option key={s}>{s}</option>)}</select>
      <select className="w-auto" value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority"><option value="">Priority: any</option>{PRIORITIES.map((s) => <option key={s}>{s}</option>)}</select></div>
      {!d ? <Loading /> : d.items.length === 0 ? <Empty title="No cases found" hint="Create a case to record the authorization, scope and objectives before collecting anything." action={canWrite && <Btn kind="primary" onClick={() => setForm(true)}><Plus size={14} /> New case</Btn>} /> :
        <table className="w-full"><thead><tr><th>Case</th><th>TLP</th><th>Title</th><th>Type</th><th>Stage</th><th>Priority</th><th>Status</th><th>Investigator</th><th>Updated</th></tr></thead><tbody>{d.items.map((c: Rec) => (
          <tr key={c.id} className="cursor-pointer" onClick={() => { setCaseId(c.id); nav(`/cases/${c.id}`); }}><td><Mono>{c.ref}</Mono></td><td><TLP v={c.tlp} /></td><td>{c.title}<div className="flex gap-1 mt-0.5">{c.tags.map((t: string) => <Tag key={t}>{t}</Tag>)}</div></td><td>{c.case_type}</td><td><Tag>{c.stage}</Tag></td><td><Status v={c.priority} /></td><td><Status v={c.status} /></td><td>{c.investigator}</td><td className="text-mute">{fmtTs(c.updated_at)}</td></tr>))}</tbody></table>}
      {d && <div className="px-2 pb-2"><Pager page={page} size={30} total={d.total} onPage={setPage} /></div>}</Panel>
    {form && <CaseForm rec={{}} onClose={() => setForm(false)} onSaved={(c) => { setForm(false); setCaseId(c.id); refreshCases(); nav(`/cases/${c.id}`); }} />}</div>;
}

export function CaseDetail() {
  const { id } = useParams(); const { setCaseId, refreshCases, canWrite, toast, user } = useApp(); const [c, setC] = useState<Rec | null>(null); const [tab, setTab] = useState("overview"); const [edit, setEdit] = useState(false); const [act, setAct] = useState<Rec[]>([]); const [err, setErr] = useState("");
  const load = useCallback(async () => { try { const x = await api(`/cases/${id}`); setC(x); setCaseId(x.id); setAct(await api(`/cases/${id}/activity`)); } catch (e: any) { setErr(e.message); } }, [id, setCaseId]);
  useEffect(() => { load(); }, [load]);
  if (err) return <Empty title="Case unavailable" hint={err} />; if (!c) return <Loading />;
  const n = c.counts;
  const setStage = async (stage: string) => { try { await api(`/cases/${c.id}`, { method: "PATCH", body: { stage } }); load(); refreshCases(); } catch (e: any) { toast(e.message, "err"); } };
  return <div>
    <div className="text-xs text-mute flex items-center gap-1 mb-1"><Link to="/cases" className="hover:text-ink">Cases</Link><ChevronRight size={12} /><Mono>{c.ref}</Mono></div>
    <PageHead title={c.title} sub={<span className="flex gap-2 items-center"><TLP v={c.tlp} /><Status v={c.status} /><Status v={c.priority} /><Tag>{c.case_type}</Tag>{c.tags.map((t: string) => <Tag key={t}>{t}</Tag>)}</span>} actions={canWrite && <Btn onClick={() => setEdit(true)}>Edit case</Btn>} />
    <div className="mb-3"><Stepper stage={c.stage} onPick={canWrite ? setStage : undefined} /></div>
    <Tabs value={tab} onChange={setTab} tabs={[{ id: "overview", label: "Overview" }, { id: "analytics", label: "Readiness" }, { id: "findings", label: "Findings", n: n.findings }, { id: "sources", label: "Sources", n: n.sources }, { id: "notes", label: "Notes", n: n.notes }, { id: "assistant", label: "AI assistant" }, { id: "activity", label: "Activity", n: act.length }, { id: "access", label: "Access" }]} />
    {tab === "overview" && <div className="grid lg:grid-cols-[1fr_320px] gap-3"><div className="space-y-3">
      <Panel title="Objectives & scope"><Dl rows={[["Description", c.description], ["Objectives", c.objectives], ["Scope", c.scope]]} /></Panel>
      <Panel title={<span className="flex items-center gap-1.5"><ShieldCheck size={14} /> Legal / authorization</span>}><p className="text-sm whitespace-pre-wrap">{c.authorization_notes}</p></Panel></div>
      <div className="space-y-3"><Panel title="Case record"><Dl rows={[["Case ID", <Mono>{c.ref}</Mono>], ["Investigator", c.investigator], ["Created", fmtTs(c.created_at)], ["Updated", fmtTs(c.updated_at)], ["Start", c.start_date], ["Target", c.target_date]]} /></Panel>
        <Panel title="Contents"><div className="grid grid-cols-2 gap-1 text-sm">{[["Subjects", n.subjects, "/subjects"], ["Identifiers", n.identifiers, "/subjects"], ["Accounts", n.accounts, "/subjects"], ["Evidence", n.evidence, "/evidence"], ["Sources", n.sources, "/sources"], ["Timeline", n.timeline, "/timeline"], ["Relationships", n.relationships, "/relationships"], ["Tasks", n.tasks, "/tasks"]].map(([l, v, to]) => <Link key={l as string} to={to as string} className="flex justify-between border border-line px-2 py-1  hover:border-mute"><span>{l}</span><b className="font-mono">{v}</b></Link>)}</div></Panel></div></div>}
    {tab === "analytics" && <Analytics caseId={c.id} />}
    {tab === "findings" && <FindingsPanel onChanged={load} />}
    {tab === "sources" && <EntityPage hideHead endpoint="sources" title="Sources" singular="Source" fields={sourceFields} defaults={{ source_type: "Web page", reliability: "Unknown", confidence: "Medium" }} cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono> }, { key: "title", label: "Title" }, { key: "reliability", label: "Reliability", render: (r) => <Status v={r.reliability} /> }, { key: "access_date", label: "Accessed" }]} />}
    {tab === "notes" && <EntityPage hideHead endpoint="notes" title="Notes" singular="Note" fields={[{ name: "title", label: "Title", req: true }, { name: "body", label: "Note", type: "textarea" }]} cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono> }, { key: "title", label: "Title" }, { key: "body", label: "Text", render: (r) => <span className="text-mute">{(r.body || "").slice(0, 120)}</span> }, { key: "updated_at", label: "Updated", render: (r) => fmtTs(r.updated_at) }]} />}
    {tab === "assistant" && <AIPanel />}
    {tab === "activity" && <Panel pad={false}>{act.length === 0 ? <Empty title="No activity yet" /> : <table className="w-full"><thead><tr><th>Time</th><th>User</th><th>Action</th><th>Record</th></tr></thead><tbody>{act.map((a) => <tr key={a.id}><td className="font-mono text-xs">{fmtTs(a.ts)}</td><td>{a.user}</td><td>{a.action.replaceAll("_", " ")}</td><td><Mono>{a.entity_ref}</Mono></td></tr>)}</tbody></table>}</Panel>}
    {tab === "access" && <Access c={c} reload={load} me={user} />}
    {edit && <CaseForm rec={c} onClose={() => setEdit(false)} onSaved={() => { setEdit(false); load(); refreshCases(); }} />}
  </div>;
}

function Access({ c, reload, me }: { c: Rec; reload: () => void; me: Rec | null }) {
  const { toast } = useApp(); const [users, setUsers] = useState<Rec[]>([]); const [m, setM] = useState<Rec[]>(c.members);
  useEffect(() => { api("/users").then(setUsers); }, []);
  const can = me?.role === "admin" || c.investigator_id === me?.id;
  const set = (uid: string, access: string) => setM([...m.filter((x) => x.user_id !== uid), ...(access ? [{ user_id: uid, access }] : [])]);
  const save = async () => { try { await api(`/cases/${c.id}/members`, { method: "PUT", body: { members: m } }); toast("Access updated"); reload(); } catch (e: any) { toast(e.message, "err"); } };
  return <Panel title="Case-level access" actions={can && <Btn kind="primary" small onClick={save}>Save access</Btn>}><div className="text-xs text-mute mb-2">Admins and the lead investigator always have access. Others see this case only if listed here.</div>
    <table className="w-full"><thead><tr><th>User</th><th>Role</th><th>Access to this case</th></tr></thead><tbody>{users.filter((u) => u.id !== c.investigator_id).map((u) => <tr key={u.id}><td>{u.display_name} <span className="text-mute">({u.username})</span></td><td>{u.role}</td>
      <td><select disabled={!can} className="w-auto" value={m.find((x) => x.user_id === u.id)?.access || ""} onChange={(e) => set(u.id, e.target.value)} aria-label={`Access for ${u.username}`}><option value="">None</option><option value="read">Read</option><option value="write">Read / write</option></select></td></tr>)}</tbody></table></Panel>;
}
