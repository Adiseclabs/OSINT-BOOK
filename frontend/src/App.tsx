import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import { Gavel, Info, Keyboard, LayoutDashboard, FolderOpen, Users, FileArchive, BookMarked, Clock, Share2, Wrench, FileText, ListChecks, ScrollText, Settings as Cog, Search, PanelLeftClose, PanelLeftOpen, Sun, Moon, LogOut } from "lucide-react";
import { useApp } from "./ctx";
import { api, Rec, qs } from "./lib";
import { Btn, Loading, Mono, Modal, TLP, Status } from "./ui";
import Dashboard from "./pages/Dashboard";
import { CaseList, CaseDetail, Stepper } from "./pages/Cases";
import { Subjects, Sources, Tasks } from "./pages/Entities";
import Evidence from "./pages/Evidence";
import Timeline from "./pages/Timeline";
import Relationships from "./pages/Graph";
import Tools from "./pages/Tools";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";
import Settings from "./pages/Settings";
import About from "./pages/About";
import FindingsPage from "./pages/FindingsPage";

const GROUPS: { label: string; items: [string, string, any][] }[] = [
  { label: "Workspace", items: [["/", "Dashboard", LayoutDashboard], ["/cases", "Cases", FolderOpen]] },
  { label: "Case file", items: [["/subjects", "Subjects", Users], ["/evidence", "Evidence", FileArchive], ["/sources", "Sources", BookMarked], ["/timeline", "Timeline", Clock], ["/relationships", "Relationships", Share2], ["/findings", "Findings", Gavel]] },
  { label: "Operate", items: [["/tools", "OSINT Tools", Wrench], ["/reports", "Reports", FileText], ["/tasks", "Tasks", ListChecks]] },
  { label: "System", items: [["/audit", "Audit Log", ScrollText], ["/settings", "Settings", Cog], ["/about", "About", Info]] }];
const NAV = GROUPS.flatMap((g) => g.items);

function Login() {
  const { login } = useApp(); const [u, setU] = useState(""); const [p, setP] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  return <div className="h-full grid md:grid-cols-[1.1fr_1fr]">
    <div className="hidden md:flex flex-col justify-between p-10 bg-panel border-r border-line">
      <div className="font-mono text-xs tracking-[.2em] text-mute">CASE FILE / LOCAL WORKSTATION</div>
      <div><h1 className="text-4xl font-semibold tracking-tight">OSINT BOOK</h1><p className="text-mute mt-2 max-w-md">Open Source Intelligence Investigation &amp; Case Management. Every claim traced to its source. Every file hashed. Every conclusion graded.</p>
        <div className="mt-8 space-y-1 font-mono text-xs text-mute">{["DISCOVER", "COLLECT", "PRESERVE", "VERIFY", "CORRELATE", "ANALYZE", "ASSESS", "REPORT"].map((s, i) => <div key={s} className="flex gap-3"><span className="w-5 text-right">{String(i + 1).padStart(2, "0")}</span><span className="text-ink/80">{s}</span></div>)}</div></div>
      <div className="text-xs text-mute">Designed and built by Aditya Bhosale</div></div>
    <div className="grid place-items-center p-6"><form className="w-[320px]" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setErr(""); try { await login(u, p); } catch (x: any) { setErr(x.message); } setBusy(false); }}>
      <div className="label mb-3">Sign in</div>
      <label className="f block mb-3"><span>Username</span><input autoFocus autoComplete="username" value={u} onChange={(e) => setU(e.target.value)} /></label>
      <label className="f block mb-4"><span>Password</span><input type="password" autoComplete="current-password" value={p} onChange={(e) => setP(e.target.value)} /></label>
      {err && <div role="alert" className="text-xs text-bad mb-3">{err}</div>}<Btn kind="primary" className="w-full justify-center" disabled={busy || !u || !p}>{busy ? "Signing in..." : "Sign in"}</Btn>
      <p className="text-xs text-mute mt-6">Authorized use only. Public, lawfully obtained information. All actions are audit-logged.</p></form></div></div>;
}

function Shortcuts({ onClose }: { onClose: () => void }) {
  return <Modal title="Keyboard shortcuts" onClose={onClose}><table className="w-full">{[["Ctrl K  /  /", "Global search"], ...NAV.map(([, l], i) => [`Alt ${i + 1}`, l]).slice(0, 9), ["?", "This help"], ["Esc", "Close dialog"]].map(([k, d]) => <tr key={k}><td className="font-mono text-xs py-0.5">{k}</td><td>{d}</td></tr>)}</table></Modal>;
}

function SearchPalette({ onClose }: { onClose: () => void }) {
  const { setCaseId } = useApp(); const nav = useNavigate(); const [q, setQ] = useState(""); const [res, setRes] = useState<Rec | null>(null);
  useEffect(() => { if (q.trim().length < 2) return setRes(null); const t = setTimeout(() => api("/search" + qs({ q })).then(setRes).catch(() => setRes({ groups: [] })), 220); return () => clearTimeout(t); }, [q]);
  const go = (k: string, i: Rec) => { setCaseId(i.case_id); const to: Rec = { case: `/cases/${i.id}`, subject: "/subjects", identifier: "/subjects", account: "/subjects", organization: "/subjects", domain: "/subjects", evidence: "/evidence", source: "/sources", finding: `/cases/${i.case_id}`, timeline: "/timeline", note: `/cases/${i.case_id}` }; nav(to[k] || "/"); onClose(); };
  return <Modal title="Search investigations" onClose={onClose} wide><input autoFocus placeholder="Exact text across cases, subjects, evidence, sources, findings, notes..." value={q} onChange={(e) => setQ(e.target.value)} aria-label="Global search" />
    <div className="mt-3 max-h-[50vh] overflow-auto">{!res ? <div className="text-xs text-mute">Type at least 2 characters. Masked identifiers match only on exact value.</div> : res.groups.length === 0 ? <div className="text-sm text-mute">No matches.</div> : res.groups.map((g: Rec) => <div key={g.kind} className="mb-2"><div className="text-xs text-mute mb-0.5">{g.kind}</div>{g.items.map((i: Rec) => <button key={i.id} onClick={() => go(g.kind, i)} className="block w-full text-left px-2 py-1 hover:bg-raised text-sm"><Mono className="text-mute mr-2">{i.ref}</Mono>{i.label}</button>)}</div>)}</div></Modal>;
}

export default function App() {
  const { user, ready, logout, cases, caseId, setCaseId, activeCase, theme, toggleTheme, toasts } = useApp(); const nav = useNavigate(); const loc = useLocation();
  const [collapsed, setCollapsed] = useState(localStorage.getItem("ob_nav") === "1"); const [search, setSearch] = useState(false); const [help, setHelp] = useState(false);
  useEffect(() => localStorage.setItem("ob_nav", collapsed ? "1" : "0"), [collapsed]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { const t = e.target as HTMLElement; const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearch(true); }
      else if (!typing && e.key === "/") { e.preventDefault(); setSearch(true); }
      else if (!typing && e.key === "?") setHelp(true);
      else if (!typing && e.altKey && /^[1-9]$/.test(e.key)) nav(NAV[+e.key - 1][0]); };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, [nav]);
  if (!ready) return <Loading />; if (!user) return <><Login /><Toasts t={toasts} /></>;
  let n = 0;
  return <div className="h-full flex">
    <aside className={`${collapsed ? "w-12" : "w-52"} shrink-0 border-r border-line bg-panel flex flex-col`}>
      <div className="h-12 px-3.5 flex items-center border-b border-line overflow-hidden whitespace-nowrap">{collapsed ? <b className="font-mono text-sm">OB</b> : <div><div className="font-semibold tracking-[.14em] text-[13px] leading-none">OSINT BOOK</div><div className="text-[10px] text-mute mt-1 tracking-wide">CASE WORKSTATION</div></div>}</div>
      <nav className="flex-1 py-1 overflow-y-auto" aria-label="Main">{GROUPS.map((g) => <div key={g.label} className="pt-2">{!collapsed && <div className="label px-3.5 pb-1">{g.label}</div>}{g.items.map(([to, label, I]) => { n++; return <NavLink key={to} to={to} end={to === "/"} title={`${label} (Alt+${n})`} className={({ isActive }) => `flex items-center gap-2.5 px-3.5 py-[5px] text-sm border-l-2 ${isActive ? "border-accent bg-raised text-ink font-medium" : "border-transparent text-mute hover:text-ink hover:bg-raised/50"}`}><I size={15} className="shrink-0" />{!collapsed && label}</NavLink>; })}</div>)}</nav>
      <div className="flex border-t border-line"><button onClick={() => setCollapsed(!collapsed)} className="h-9 flex-1 text-mute hover:text-ink grid place-items-center" aria-label="Toggle navigation">{collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}</button>{!collapsed && <button onClick={() => setHelp(true)} className="h-9 w-9 text-mute hover:text-ink grid place-items-center" aria-label="Keyboard shortcuts"><Keyboard size={15} /></button>}</div></aside>
    <div className="flex-1 min-w-0 flex flex-col">
      <header className="h-12 border-b border-line bg-panel flex items-center gap-3 px-4">
        <select className="!w-80" aria-label="Active case" value={caseId} onChange={(e) => setCaseId(e.target.value)}><option value="">All cases</option>{cases.map((c) => <option key={c.id} value={c.id}>{c.ref}  {c.title}</option>)}</select>
        <div className="flex-1" /><button onClick={() => setSearch(true)} className="flex items-center gap-2 border border-line px-2.5 py-1 text-xs text-mute hover:text-ink hover:border-mute w-56"><Search size={13} /> Search everything<kbd className="font-mono text-[10px] border border-line px-1 ml-auto">Ctrl K</kbd></button>
        <button onClick={toggleTheme} aria-label="Toggle theme" className="text-mute hover:text-ink">{theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}</button>
        <div className="text-xs leading-tight text-right hidden md:block"><div>{user.display_name}</div><div className="text-mute">{user.role}</div></div><button onClick={logout} aria-label="Sign out" className="text-mute hover:text-ink"><LogOut size={15} /></button></header>
      {activeCase && <div className="border-b border-line bg-panel/60 px-4 py-1.5 flex items-center gap-4 text-xs"><div className="flex items-center gap-2 min-w-0"><Mono className="text-mute">{activeCase.ref}</Mono><b className="font-medium truncate">{activeCase.title}</b><TLP v={activeCase.tlp} /><Status v={activeCase.status} /></div>{!loc.pathname.startsWith("/cases/") && <div className="flex-1 max-w-xl ml-auto"><Stepper stage={activeCase.stage} /></div>}</div>}
      <main className="flex-1 overflow-auto p-5"><Routes><Route path="/" element={<Dashboard />} /><Route path="/cases" element={<CaseList />} /><Route path="/cases/:id" element={<CaseDetail />} /><Route path="/subjects" element={<Subjects />} /><Route path="/evidence" element={<Evidence />} />
        <Route path="/sources" element={<Sources />} /><Route path="/timeline" element={<Timeline />} /><Route path="/relationships" element={<Relationships />} /><Route path="/findings" element={<FindingsPage />} /><Route path="/tools" element={<Tools />} /><Route path="/reports" element={<Reports />} /><Route path="/tasks" element={<Tasks />} />
        <Route path="/audit" element={<Audit />} /><Route path="/settings" element={<Settings />} /><Route path="/about" element={<About />} /><Route path="*" element={<Navigate to="/" />} /></Routes></main></div>
    {search && <SearchPalette onClose={() => setSearch(false)} />}{help && <Shortcuts onClose={() => setHelp(false)} />}<Toasts t={toasts} /></div>;
}
function Toasts({ t }: { t: { id: number; msg: string; kind: string }[] }) {
  return <div className="fixed bottom-3 right-3 z-50 space-y-1.5" role="status" aria-live="polite">{t.map((x) => <div key={x.id} className={`border bg-panel px-3 py-1.5 text-sm max-w-sm  ${x.kind === "err" ? "border-bad text-bad" : "border-line"}`}>{x.msg}</div>)}</div>;
}
