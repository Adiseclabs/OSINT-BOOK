import { useCallback, useEffect, useRef, useState } from "react";
import { Database, Upload } from "lucide-react";
import { api, Rec, download, ApiError } from "../lib";
import { useApp } from "../ctx";
import { Btn, Empty, Loading, Mono, PageHead, Panel, Status, Tabs, Confirm } from "../ui";

export default function Settings() {
  const { user, caseId, activeCase, toast, refreshCases } = useApp(); const [tab, setTab] = useState("general"); const isAdmin = user?.role === "admin";
  const [s, setS] = useState<Rec | null>(null); const [users, setUsers] = useState<Rec[]>([]); const [bk, setBk] = useState<Rec[]>([]); const [pw, setPw] = useState<Rec>({}); const [nu, setNu] = useState<Rec>({ role: "investigator" }); const [restore, setRestore] = useState<File | null>(null); const fileRef = useRef<HTMLInputElement>(null);
  const load = useCallback(async () => { setS(await api("/settings")); setUsers(await api("/users")); if (isAdmin) setBk(await api("/backup")); }, [isAdmin]);
  useEffect(() => { load(); }, [load]);
  const put = async (k: string, v: any) => { try { setS(await api("/settings", { method: "PUT", body: { [k]: v } })); toast("Setting saved"); } catch (e: any) { toast(e.message, "err"); } };
  const run = async (fn: () => Promise<any>, ok: string) => { try { const r = await fn(); toast(ok); load(); return r; } catch (e: any) { toast(e instanceof ApiError ? e.message : "Failed", "err"); } };
  if (!s) return <Loading />;
  const row = (label: string, help: string, ctl: any) => <div className="flex justify-between gap-4 py-2 border-b border-line/60 last:border-0"><div><div className="text-sm">{label}</div><div className="text-xs text-mute max-w-md">{help}</div></div><div className="w-56 shrink-0">{ctl}</div></div>;
  return <div><PageHead title="Settings" /><Tabs value={tab} onChange={setTab} tabs={[{ id: "general", label: "General" }, { id: "account", label: "Account" }, ...(isAdmin ? [{ id: "users", label: "Users" }, { id: "backup", label: "Backup & restore" }] : [])]} />
    {tab === "general" && <Panel>{row("Report classification banner", "Printed at the top of every report.", <input disabled={!isAdmin} defaultValue={s.report_classification} onBlur={(e) => e.target.value !== s.report_classification && put("report_classification", e.target.value)} />)}
      {row("Organization name", "Shown in report header.", <input disabled={!isAdmin} defaultValue={s.org_name} onBlur={(e) => e.target.value !== s.org_name && put("org_name", e.target.value)} />)}
      {row("Allow private-network targets", "Off by default: URL tools refuse loopback/private addresses (SSRF protection). Enable only for authorized internal assessments.", <input type="checkbox" disabled={!isAdmin} checked={s.allow_private_targets === "true"} onChange={(e) => put("allow_private_targets", e.target.checked)} />)}
      {row("AI assistant provider", "'none' uses built-in rule-based suggestions. 'ollama' sends summaries to a model on this machine (127.0.0.1:11434). Nothing leaves your computer.", <select disabled={!isAdmin} value={s.ai_provider} onChange={(e) => put("ai_provider", e.target.value)}><option>none</option><option>ollama</option></select>)}
      {row("Local model name", "Used when provider is ollama.", <input disabled={!isAdmin} defaultValue={s.ai_model} onBlur={(e) => put("ai_model", e.target.value)} />)}
      <p className="text-xs text-mute pt-2">Telemetry: none. The application makes no network requests except those you run from OSINT tools.{!isAdmin && " Settings are editable by administrators."}</p></Panel>}
    {tab === "account" && <Panel title="Change password"><form className="max-w-sm space-y-2" onSubmit={(e) => { e.preventDefault(); run(() => api("/auth/password", { body: { current: pw.cur, new: pw.new } }), "Password changed - sign in again"); }}>
      <label className="f block"><span>Current password</span><input type="password" autoComplete="current-password" onChange={(e) => setPw({ ...pw, cur: e.target.value })} /></label><label className="f block"><span>New password (10+ chars, mixed case, digit)</span><input type="password" autoComplete="new-password" onChange={(e) => setPw({ ...pw, new: e.target.value })} /></label><Btn kind="primary" type="submit">Change password</Btn></form></Panel>}
    {tab === "users" && <div className="space-y-3"><Panel pad={false}><table className="w-full"><thead><tr><th>User</th><th>Name</th><th>Role</th></tr></thead><tbody>{users.map((u) => <tr key={u.id}><td><Mono>{u.username}</Mono></td><td>{u.display_name}</td><td>{u.role}</td></tr>)}</tbody></table></Panel>
      <Panel title="Add user"><form className="grid grid-cols-4 gap-2 items-end" onSubmit={(e) => { e.preventDefault(); run(() => api("/users", { body: nu }), "User created"); }}>
        <label className="f"><span>Username</span><input onChange={(e) => setNu({ ...nu, username: e.target.value })} /></label><label className="f"><span>Display name</span><input onChange={(e) => setNu({ ...nu, display_name: e.target.value })} /></label>
        <label className="f"><span>Role</span><select value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}><option value="admin">admin</option><option value="investigator">investigator</option><option value="viewer">viewer (read-only)</option></select></label><label className="f"><span>Password</span><input type="password" onChange={(e) => setNu({ ...nu, password: e.target.value })} /></label><Btn kind="primary" type="submit">Add</Btn></form></Panel></div>}
    {tab === "backup" && <div className="space-y-3"><Panel title="Create backup" actions={<></>}><div className="flex gap-2 flex-wrap"><Btn onClick={() => run(() => api("/backup/database", { method: "POST" }), "Full backup created")}><Database size={13} /> Backup database + all evidence</Btn>
      <Btn disabled={!caseId} title={caseId ? "" : "Select a case"} onClick={() => run(() => api(`/backup/case/${caseId}`, { method: "POST" }), "Case backup created")}>Backup case {activeCase?.ref}</Btn></div><p className="text-xs text-mute mt-2">Archives contain the SQLite snapshot, evidence files, configuration and a SHA-256 integrity manifest. Store them encrypted and offline.</p></Panel>
      <Panel title="Backups" pad={false}>{bk.length === 0 ? <Empty title="No backups yet" /> : <table className="w-full"><tbody>{bk.map((b) => <tr key={b.name}><td className="font-mono text-xs">{b.name}</td><td className="text-mute">{(b.size / 1024).toFixed(0)} KB</td><td className="text-right"><Btn small onClick={() => download(`/backup/${b.name}/download`, b.name)}>Download</Btn></td></tr>)}</tbody></table>}</Panel>
      <Panel title="Restore"><div className="flex gap-2 items-center"><input ref={fileRef} type="file" accept=".zip" onChange={(e) => setRestore(e.target.files?.[0] || null)} /><Btn disabled={!restore} onClick={async () => { const f = new FormData(); f.append("file", restore!); await run(async () => { const r = await api("/backup/verify", { form: f }); return r; }, "Archive integrity verified"); }}>Verify only</Btn><Btn kind="danger" disabled={!restore} onClick={() => setRestore(restore && Object.assign(restore, {}))} data-confirm>Restore...</Btn></div>
        <p className="text-xs text-mute mt-2">A full restore replaces the database and case files (a safety copy is taken first) and requires signing in again. A case restore adds the case only if it does not already exist.</p></Panel></div>}
    {restore && tab === "backup" && <RestoreConfirm file={restore} onClose={() => { setRestore(null); if (fileRef.current) fileRef.current.value = ""; }} refresh={refreshCases} />}
  </div>;
}
function RestoreConfirm({ file, onClose, refresh }: { file: File; onClose: () => void; refresh: () => void }) {
  const { toast } = useApp(); const [go, setGo] = useState(false);
  if (!go) return <Confirm danger title="Restore from backup?" confirm="Restore" body={<>Restore <Mono>{file.name}</Mono>. The archive's integrity manifest is checked first. A full-backup restore overwrites current data.</>} onYes={() => setGo(true)} onClose={() => { onClose(); }} />;
  (async () => { const f = new FormData(); f.append("file", file); try { const r = await api("/backup/restore", { form: f }); toast(r.restored === "full" ? "Full restore complete. " + r.note : `Case ${r.case_ref} restored`); refresh(); } catch (e: any) { toast(e.message, "err"); } onClose(); })();
  return null;
}
