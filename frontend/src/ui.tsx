import { ReactNode, useEffect, useState, ButtonHTMLAttributes } from "react";
import { X, Loader2, Inbox, ChevronLeft, ChevronRight } from "lucide-react";
import { Rec } from "./lib";

export function Btn({ kind = "default", small, className = "", ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: "default" | "primary" | "danger" | "ghost"; small?: boolean }) {
  const k = { default: "bg-transparent border-line hover:bg-raised", primary: "bg-accent text-bg border-accent hover:brightness-110 font-medium", danger: "border-bad text-bad hover:bg-bad/10", ghost: "border-transparent hover:bg-raised" }[kind];
  return <button {...p} className={`inline-flex items-center gap-1.5 border  ${small ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm"} disabled:opacity-40 disabled:cursor-not-allowed ${k} ${className}`} />;
}
export const Mono = ({ children, className = "" }: { children: ReactNode; className?: string }) => <span className={`ref ${className}`}>{children}</span>;
export const Tag = ({ children, tone = "mute" }: { children: ReactNode; tone?: string }) => {
  const t: Rec = { mute: "text-mute border-line", ok: "text-ok border-ok/50", warn: "text-warn border-warn/50", bad: "text-bad border-bad/50", accent: "text-accent border-accent/50" };
  return <span className={`inline-block border px-1.5 text-[10.5px] leading-4 whitespace-nowrap font-mono ${t[tone] || t.mute}`}>{children}</span>;
};
const TONES: Rec = { Critical: "bad", High: "warn", Medium: "accent", Low: "mute", Informational: "mute", Active: "ok", Closed: "mute", Archived: "mute", Suspended: "warn", "Under Review": "accent", Draft: "mute",
  VALID: "ok", MISMATCH: "bad", MISSING: "bad", DELETED: "mute", UNVERIFIED: "warn", Verified: "ok", Pending: "warn", Disputed: "bad", Done: "ok", Blocked: "bad", Open: "mute", "In Progress": "accent", Completed: "ok", Failed: "bad", Running: "warn",
  Approved: "ok", Rejected: "bad", Confirmed: "ok", Unknown: "mute", Deleted: "mute" };
const DOT: Rec = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", accent: "bg-accent", mute: "bg-mute/60" };
export const Status = ({ v }: { v?: string | null }) => (v ? <span className="inline-flex items-center gap-1.5 whitespace-nowrap"><i className={`w-1.5 h-1.5 shrink-0 ${DOT[TONES[v] || "mute"]}`} />{v}</span> : <span className="text-mute">-</span>);
const TLPC: Rec = { CLEAR: "border-mute text-ink", GREEN: "border-ok text-ok", AMBER: "border-warn text-warn", "AMBER+STRICT": "border-warn text-warn", RED: "border-bad text-bad" };
export const TLP = ({ v }: { v?: string }) => (v ? <span title="Traffic Light Protocol sharing marking" className={`font-mono text-[10.5px] border px-1.5 tracking-wide ${TLPC[v] || ""}`}>TLP:{v}</span> : null);
/** FACT is solid, OBSERVATION outlined, INFERENCE dashed, HYPOTHESIS dotted: uncertainty is visible without reading. */
export const Kind = ({ v }: { v: string }) => <span className={`k-${v} inline-block  px-1.5 text-xs leading-4`} title="Epistemic status of this finding">{v}</span>;
export const Certainty = ({ v, pct }: { v: string; pct?: number }) => <span className={`c-${v} inline-block  px-1.5 text-xs leading-4`}>{v}{pct !== undefined ? ` ${pct}%` : ""}</span>;
export const AIBadge = () => <span className="inline-block border border-accent text-accent  px-1.5 text-xs leading-4 font-mono">AI GENERATED</span>;

export function Panel({ title, actions, children, className = "", pad = true }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`bg-panel border border-line ${className}`}>
      {(title || actions) && <header className="flex items-center justify-between px-3 h-8 border-b border-line"><h3 className="label !text-ink/80">{title}</h3><div className="flex gap-1.5">{actions}</div></header>}
      <div className={pad ? "p-3" : ""}>{children}</div>
    </section>
  );
}
export const Loading = () => <div className="flex items-center gap-2 text-mute p-4 text-sm"><Loader2 className="animate-spin" size={14} /> Loading...</div>;
export const Empty = ({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) => (
  <div className="flex flex-col items-center text-center py-10 text-mute gap-1.5"><Inbox size={22} /><div className="text-ink text-sm">{title}</div>{hint && <div className="text-xs max-w-sm">{hint}</div>}{action && <div className="mt-2">{action}</div>}</div>
);
export function PageHead({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return <div className="flex items-end justify-between mb-4 pb-3 border-b border-line"><div><h1 className="text-[19px] font-semibold tracking-tight leading-tight">{title}</h1>{sub && <div className="text-xs text-mute mt-0.5">{sub}</div>}</div><div className="flex gap-1.5">{actions}</div></div>;
}
export function Tabs({ tabs, value, onChange }: { tabs: { id: string; label: string; n?: number }[]; value: string; onChange: (v: string) => void }) {
  return <div className="flex gap-0 border-b border-line mb-3 overflow-x-auto" role="tablist">{tabs.map((t) => (
    <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)} className={`px-3 py-1.5 text-sm border-b-2 -mb-px whitespace-nowrap font-medium ${value === t.id ? "border-accent text-ink" : "border-transparent text-mute hover:text-ink"}`}>{t.label}{t.n !== undefined && <span className="ml-1.5 text-xs text-mute">{t.n}</span>}</button>))}</div>;
}
export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => { const h = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h); }, [onClose]);
  return (
    <div className="fixed inset-0 z-40 bg-black/55 flex items-start justify-center pt-[8vh] px-3" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className={`bg-panel border border-line  w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[84vh] flex flex-col`}>
        <header className="flex items-center justify-between px-3 py-2 border-b border-line"><h2 className="text-sm font-semibold">{title}</h2><button aria-label="Close" onClick={onClose} className="text-mute hover:text-ink"><X size={15} /></button></header>
        <div className="p-3 overflow-auto">{children}</div>
      </div>
    </div>
  );
}
export function Confirm({ title, body, confirm = "Confirm", danger, onYes, onClose }: { title: string; body: ReactNode; confirm?: string; danger?: boolean; onYes: () => void | Promise<void>; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  return <Modal title={title} onClose={onClose}><div className="text-sm mb-4">{body}</div><div className="flex justify-end gap-2"><Btn onClick={onClose}>Cancel</Btn>
    <Btn kind={danger ? "danger" : "primary"} disabled={busy} autoFocus onClick={async () => { setBusy(true); try { await onYes(); } finally { setBusy(false); } onClose(); }}>{confirm}</Btn></div></Modal>;
}
export function Pager({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size)); if (total <= size) return null;
  return <div className="flex items-center justify-end gap-2 text-xs text-mute mt-2"><span>{(page - 1) * size + 1}-{Math.min(total, page * size)} of {total}</span>
    <Btn small disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={12} /></Btn><Btn small disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={12} /></Btn></div>;
}
export const Hash = ({ v }: { v: string }) => <span className="ref !whitespace-normal break-all text-mute select-all">{v}</span>;
export const Dl = ({ rows }: { rows: [string, ReactNode][] }) => <dl className="grid grid-cols-[120px_1fr] gap-x-3 gap-y-1 text-sm">{rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-mute text-xs pt-0.5">{k}</dt><dd className="break-words">{v ?? "-"}</dd></div>)}</dl>;

export type FieldDef = { name: string; label: string; type?: "text" | "textarea" | "select" | "date" | "number" | "check" | "ref" | "list"; options?: string[]; req?: boolean; ref?: string; help?: string; half?: boolean };
export function Field({ f, value, onChange, error, refs }: { f: FieldDef; value: any; onChange: (v: any) => void; error?: string; refs?: Rec }) {
  const common = { id: "f_" + f.name, "aria-invalid": !!error };
  let input: ReactNode;
  if (f.type === "textarea") input = <textarea {...common} rows={3} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  else if (f.type === "select") input = <select {...common} value={value ?? ""} onChange={(e) => onChange(e.target.value)}>{!f.req && <option value="">-</option>}{f.options!.map((o) => <option key={o}>{o}</option>)}</select>;
  else if (f.type === "ref") { const opts: Rec[] = refs?.[f.ref!] || []; input = <select {...common} value={value ?? ""} onChange={(e) => onChange(e.target.value)}><option value="">-</option>{opts.map((o) => <option key={o.id} value={o.id}>{o.ref} {o.label}</option>)}</select>; }
  else if (f.type === "check") input = <input type="checkbox" {...common} checked={!!value} onChange={(e) => onChange(e.target.checked)} />;
  else if (f.type === "date") input = <input type="text" placeholder="YYYY-MM-DD" {...common} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  else if (f.type === "list") input = <input {...common} placeholder="comma separated" value={Array.isArray(value) ? value.join(", ") : value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  else if (f.type === "number") input = <input type="number" min={0} max={100} {...common} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  else input = <input {...common} value={value ?? ""} onChange={(e) => onChange(e.target.value)} />;
  return <label className={`f block ${f.half ? "" : "col-span-2"}`}><span>{f.label}{f.req && <b className="text-bad"> *</b>}</span>{input}{f.help && !error && <em className="block text-xs text-mute not-italic mt-0.5">{f.help}</em>}{error && <em className="block text-xs text-bad not-italic mt-0.5">{error}</em>}</label>;
}
export const useDebounced = <T,>(v: T, ms = 250) => { const [d, setD] = useState(v); useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t); }, [v, ms]); return d; };
