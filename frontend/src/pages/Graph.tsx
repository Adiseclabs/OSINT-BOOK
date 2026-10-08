import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus, Trash2, ZoomIn, ZoomOut, Maximize } from "lucide-react";
import { api, qs, Rec, ApiError, ENTITY_TYPES, REL_TYPES } from "../lib";
import { useApp } from "../ctx";
import { useRefs } from "../EntityPage";
import { Btn, Certainty, Confirm, Empty, Field, Loading, Modal, Mono, PageHead, Panel, Tag } from "../ui";

type P = { x: number; y: number };
function layout(nodes: Rec[], edges: Rec[], W: number, H: number): Record<string, P> {
  const pos: Record<string, P> = {}; const n = nodes.length || 1;
  nodes.forEach((nd, i) => { const a = (i / n) * Math.PI * 2; pos[nd.id] = { x: W / 2 + Math.cos(a) * W * 0.3, y: H / 2 + Math.sin(a) * H * 0.3 }; });
  const k = Math.sqrt((W * H) / n) * 0.7;
  for (let it = 0; it < 260; it++) {
    const f: Record<string, P> = Object.fromEntries(nodes.map((x) => [x.id, { x: 0, y: 0 }]));
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = pos[nodes[i].id], b = pos[nodes[j].id]; let dx = a.x - b.x, dy = a.y - b.y; const d = Math.max(Math.hypot(dx, dy), 1); const r = (k * k) / d; dx /= d; dy /= d;
      f[nodes[i].id].x += dx * r; f[nodes[i].id].y += dy * r; f[nodes[j].id].x -= dx * r; f[nodes[j].id].y -= dy * r;
    }
    edges.forEach((e) => { const a = pos[e.from], b = pos[e.to]; if (!a || !b) return; let dx = b.x - a.x, dy = b.y - a.y; const d = Math.max(Math.hypot(dx, dy), 1); const s = (d * d) / k * 0.12; dx /= d; dy /= d;
      f[e.from].x += dx * s; f[e.from].y += dy * s; f[e.to].x -= dx * s; f[e.to].y -= dy * s; });
    const t = 12 * (1 - it / 260);
    nodes.forEach((nd) => { const p = pos[nd.id], fo = f[nd.id]; const d = Math.max(Math.hypot(fo.x, fo.y), 1); p.x = Math.min(W - 60, Math.max(60, p.x + (fo.x / d) * Math.min(d, t) + (W / 2 - p.x) * 0.004)); p.y = Math.min(H - 30, Math.max(30, p.y + (fo.y / d) * Math.min(d, t) + (H / 2 - p.y) * 0.004)); });
  }
  return pos;
}
const SHAPE: Rec = { subject: "circle", account: "circle", identifier: "rect", organization: "rect", domain: "diamond", source: "tri", evidence: "tri" };
function NodeShape({ type, sel }: { type: string; sel: boolean }) {
  const s = SHAPE[type] || "circle"; const p = { fill: "rgb(var(--panel))", stroke: sel ? "rgb(var(--accent))" : "rgb(var(--ink))", strokeWidth: sel ? 2.5 : 1.5 };
  if (s === "circle") return <circle r={11} {...p} />; if (s === "rect") return <rect x={-11} y={-9} width={22} height={18} rx={2} {...p} />;
  if (s === "diamond") return <path d="M0,-13 L13,0 L0,13 L-13,0 Z" {...p} />; return <path d="M0,-12 L12,9 L-12,9 Z" {...p} />;
}
const dash = (c: string) => (c === "CONFIRMED" ? undefined : c === "LIKELY" ? "7 4" : "2 4");

function RelForm({ caseId, refs, onClose, onSaved }: { caseId: string; refs: Rec; onClose: () => void; onSaved: () => void }) {
  const { toast } = useApp(); const have = ENTITY_TYPES.filter((t) => (refs[t] || []).length);
  const [v, setV] = useState<Rec>({ from_type: have[0] || "subject", to_type: have[1] || have[0] || "account", rel_type: "ASSOCIATED_WITH", certainty: "POSSIBLE", confidence_pct: 30 }); const [errs, setErrs] = useState<Rec>({});
  const opts = (t: string) => (refs[t] || []) as Rec[];
  const save = async () => { try { await api(`/relationships?case_id=${caseId}`, { body: { ...v, confidence_pct: Number(v.confidence_pct) } }); toast("Relationship recorded"); onSaved(); } catch (e: any) { if (e instanceof ApiError && Object.keys(e.fields).length) setErrs(e.fields); else toast(e.message, "err"); } };
  const sel = (label: string, k: string, o: string[]) => <Field f={{ name: k, label, type: "select", options: o, req: true, half: true }} value={v[k]} onChange={(x) => setV({ ...v, [k]: x, ...(k.endsWith("_type") && k !== "rel_type" ? { [k.replace("_type", "_id")]: "" } : {}) })} error={errs[k]} />;
  const pick = (label: string, k: string, t: string) => { const o = opts(t); return <label className="f block"><span>{label}<b className="text-bad"> *</b></span><select value={v[k] || ""} disabled={!o.length} onChange={(e) => setV({ ...v, [k]: e.target.value })}><option value="">{o.length ? "Select..." : `No ${t} records in this case - add one first or change the type`}</option>{o.map((x) => <option key={x.id} value={x.id}>{x.ref} {x.label}</option>)}</select>{errs[k] && <em className="text-xs text-bad not-italic">{errs[k]}</em>}</label>; };
  return <Modal wide title="New relationship" onClose={onClose}><form onSubmit={(e) => { e.preventDefault(); save(); }}><div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
    {sel("From type", "from_type", ENTITY_TYPES)}{sel("Relationship", "rel_type", REL_TYPES)}<div className="col-span-2">{pick("From", "from_id", v.from_type)}</div>{sel("To type", "to_type", ENTITY_TYPES)}{sel("Certainty", "certainty", ["POSSIBLE", "LIKELY", "CONFIRMED"])}<div className="col-span-2">{pick("To", "to_id", v.to_type)}</div>
    <Field f={{ name: "confidence_pct", label: "Confidence %", type: "number", half: true }} value={v.confidence_pct} onChange={(x) => setV({ ...v, confidence_pct: x })} error={errs.confidence_pct} />
    <label className="f block"><span>Supporting evidence</span><select value={v.evidence_id || ""} onChange={(e) => setV({ ...v, evidence_id: e.target.value })}><option value="">-</option>{opts("evidence").map((o) => <option key={o.id} value={o.id}>{o.ref} {o.label}</option>)}</select></label>
    <label className="f block"><span>Source</span><select value={v.source_id || ""} onChange={(e) => setV({ ...v, source_id: e.target.value })}><option value="">-</option>{opts("source").map((o) => <option key={o.id} value={o.id}>{o.ref} {o.label}</option>)}</select></label>
    <Field f={{ name: "reasoning", label: "Analyst reasoning", type: "textarea", req: false, help: "Why do you believe this? CONFIRMED requires a source or evidence." }} value={v.reasoning} onChange={(x) => setV({ ...v, reasoning: x })} error={errs.reasoning} />
    {errs.certainty && <div className="col-span-2 text-xs text-bad">{errs.certainty}</div>}</div>
    <div className="flex justify-end gap-2 mt-4"><Btn type="button" onClick={onClose}>Cancel</Btn><Btn kind="primary" type="submit" disabled={!v.from_id || !v.to_id}>Save</Btn></div></form></Modal>;
}

const TYPE_LABEL: Rec = { subject: "Subjects", account: "Accounts", identifier: "Identifiers", organization: "Organizations", domain: "Domains", source: "Sources", evidence: "Evidence" };
export default function Relationships() {
  const { caseId, activeCase, canWrite, toast } = useApp(); const { refs, reload } = useRefs(caseId);
  const [g, setG] = useState<Rec | null>(null); const [sel, setSel] = useState<Rec | null>(null); const [focus, setFocus] = useState<string | null>(null); const [form, setForm] = useState(false); const [del, setDel] = useState<Rec | null>(null);
  const [minPct, setMinPct] = useState(0); const [hidden, setHidden] = useState<Set<string>>(new Set(["source", "evidence"])); const [pos, setPos] = useState<Record<string, P>>({}); const [tf, setTf] = useState({ x: 0, y: 0, k: 1 });
  const drag = useRef<{ kind: "pan" | "node"; id?: string; sx: number; sy: number; ox: number; oy: number } | null>(null);
  const load = useCallback(async () => { if (caseId) setG(await api("/graph" + qs({ case_id: caseId }))); else setG({ nodes: [], edges: [] }); }, [caseId]);
  useEffect(() => { setG(null); setSel(null); setFocus(null); load(); }, [load]);
  const W = 900, H = 460;
  const nodes = useMemo(() => (g?.nodes || []).filter((n: Rec) => !hidden.has(n.type)), [g, hidden]);
  const ids = useMemo(() => new Set(nodes.map((n: Rec) => n.id)), [nodes]);
  const edges = useMemo(() => (g?.edges || []).filter((e: Rec) => e.pct >= minPct && ids.has(e.from) && ids.has(e.to)), [g, minPct, ids]);
  useEffect(() => { setPos(layout(nodes, edges, W, H)); setTf({ x: 0, y: 0, k: 1 }); }, [nodes, edges.length]); // eslint-disable-line
  const nb = useMemo(() => { if (!focus) return null; const s = new Set([focus]); edges.forEach((e: Rec) => { if (e.from === focus) s.add(e.to); if (e.to === focus) s.add(e.from); }); return s; }, [focus, edges]);
  const label = (id: string) => g?.nodes.find((n: Rec) => n.id === id)?.label || id;
  const pt = (e: React.PointerEvent) => { const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect(); return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H }; };
  const down = (e: React.PointerEvent<SVGSVGElement>, id?: string) => { e.stopPropagation(); (e.currentTarget as Element).setPointerCapture?.(e.pointerId); const p = pt(e); drag.current = id ? { kind: "node", id, sx: p.x, sy: p.y, ox: pos[id].x, oy: pos[id].y } : { kind: "pan", sx: p.x, sy: p.y, ox: tf.x, oy: tf.y }; };
  const move = (e: React.PointerEvent<SVGSVGElement>) => { const d = drag.current; if (!d) return; const p = pt(e);
    if (d.kind === "pan") setTf((t) => ({ ...t, x: d.ox + (p.x - d.sx), y: d.oy + (p.y - d.sy) })); else setPos((s) => ({ ...s, [d.id!]: { x: d.ox + (p.x - d.sx) / tf.k, y: d.oy + (p.y - d.sy) / tf.k } })); };
  const zoom = (f: number) => setTf((t) => ({ ...t, k: Math.min(3, Math.max(0.4, t.k * f)) }));
  const present = Array.from(new Set<string>((g?.nodes || []).map((n: Rec) => n.type)));
  return <div><PageHead title="Relationships" sub={activeCase ? <>Case <Mono>{activeCase.ref}</Mono> - line style shows certainty, not just colour</> : "Select a case to view its graph"} actions={canWrite && <Btn kind="primary" disabled={!caseId} onClick={() => setForm(true)}><Plus size={14} /> New relationship</Btn>} />
    {!caseId ? <Empty title="No case selected" hint="Choose a case in the top bar." /> : !g ? <Loading /> : g.nodes.length === 0 ? <Empty title="Nothing to graph yet" hint="Add subjects, accounts and domains, then record how they relate. Every relationship carries confidence and reasoning." /> : <>
      <Panel pad={false} title="Link chart" actions={<div className="flex items-center gap-2"><label className="text-xs text-mute flex items-center gap-1.5">Min confidence <input type="range" className="!w-20" min={0} max={90} step={10} value={minPct} onChange={(e) => setMinPct(+e.target.value)} />{minPct}%</label>
        <Btn small onClick={() => zoom(1.2)} aria-label="Zoom in"><ZoomIn size={12} /></Btn><Btn small onClick={() => zoom(1 / 1.2)} aria-label="Zoom out"><ZoomOut size={12} /></Btn><Btn small onClick={() => { setTf({ x: 0, y: 0, k: 1 }); setPos(layout(nodes, edges, W, H)); }}><Maximize size={12} /> Reset</Btn></div>}>
        <div className="flex flex-wrap gap-1.5 px-3 py-1.5 border-b border-line items-center"><span className="label mr-1">Show</span>{present.map((t) => { const off = hidden.has(t); return <button key={t} onClick={() => { const s = new Set(hidden); off ? s.delete(t) : s.add(t); setHidden(s); }} aria-pressed={!off} className={`text-xs px-1.5 border ${off ? "border-line text-mute line-through" : "border-accent text-ink"}`}>{TYPE_LABEL[t] || t}</button>; })}<span className="text-xs text-mute ml-auto">Drag nodes or background, wheel to zoom, click a node to focus its neighbours</span></div>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[480px] bg-bg touch-none cursor-grab select-none" role="img" aria-label="Relationship link chart" onPointerDown={(e) => { down(e); }} onPointerMove={move} onPointerUp={() => (drag.current = null)} onWheel={(e) => zoom(e.deltaY < 0 ? 1.1 : 1 / 1.1)} onClick={() => { setSel(null); setFocus(null); }}>
          <g transform={`translate(${tf.x},${tf.y}) scale(${tf.k})`}>
          {edges.map((e: Rec) => { const a = pos[e.from], b = pos[e.to]; if (!a || !b) return null; const on = sel?.id === e.id; const dim = nb && !(nb.has(e.from) && nb.has(e.to) && (e.from === focus || e.to === focus)); return <g key={e.id} opacity={dim ? 0.12 : 1} onClick={(ev) => { ev.stopPropagation(); setSel(e); }} onPointerDown={(ev) => ev.stopPropagation()} className="cursor-pointer">
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={12} /><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={on ? "rgb(var(--accent))" : e.certainty === "CONFIRMED" ? "rgb(var(--ink))" : "rgb(var(--warn))"} strokeWidth={e.certainty === "CONFIRMED" ? 2 : 1.4} strokeDasharray={dash(e.certainty)} />
            <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 3} textAnchor="middle" fontSize="9.5" fill="rgb(var(--mute))" stroke="rgb(var(--bg))" strokeWidth="3" paintOrder="stroke">{e.type} {e.pct}%</text></g>; })}
          {nodes.map((n: Rec) => { const p = pos[n.id]; if (!p) return null; const dim = nb && !nb.has(n.id); return <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.2 : 1} className="cursor-move" onPointerDown={(e) => down(e as any, n.id)} onClick={(e) => { e.stopPropagation(); setFocus(focus === n.id ? null : n.id); }}><NodeShape type={n.type} sel={focus === n.id} /><text y={26} textAnchor="middle" fontSize="11" fill="rgb(var(--ink))" stroke="rgb(var(--bg))" strokeWidth="3" paintOrder="stroke" pointerEvents="none">{n.label.length > 24 ? n.label.slice(0, 23) + "..." : n.label}</text></g>; })}</g>
        </svg>
        <div className="flex flex-wrap gap-x-5 gap-y-1 px-3 py-2 border-t border-line text-xs text-mute items-center">
          {[["CONFIRMED", undefined], ["LIKELY", "7 4"], ["POSSIBLE", "2 4"]].map(([c, d]) => <span key={c as string} className="flex items-center gap-1.5"><svg width="30" height="6"><line x1="0" y1="3" x2="30" y2="3" stroke={c === "CONFIRMED" ? "rgb(var(--ink))" : "rgb(var(--warn))"} strokeWidth="2" strokeDasharray={d as string | undefined} /></svg>{c}</span>)}
          <span className="ml-3">Shapes:</span>{[["subject / account", "subject"], ["identifier / organization", "organization"], ["domain", "domain"], ["source / evidence", "source"]].map(([l, t]) => <span key={l} className="flex items-center gap-1"><svg width="22" height="22" viewBox="-14 -14 28 28"><NodeShape type={t} sel={false} /></svg>{l}</span>)}</div></Panel>
      {sel && <Panel title={<span className="flex gap-2 items-center normal-case tracking-normal"><Mono>{sel.ref}</Mono> {label(sel.from)} <Tag>{sel.type}</Tag> {label(sel.to)}</span>} className="mt-3" actions={canWrite && <Btn small kind="ghost" aria-label="Delete relationship" onClick={() => setDel(sel)}><Trash2 size={13} /></Btn>}><div className="flex gap-3 items-start"><Certainty v={sel.certainty} pct={sel.pct} /><p className="text-sm">{sel.reasoning || <span className="text-mute">No reasoning recorded.</span>}</p></div></Panel>}
      <Panel title="All relationships" className="mt-3" pad={false}><table className="w-full"><thead><tr><th>ID</th><th>From</th><th>Relationship</th><th>To</th><th>Certainty</th><th>Reasoning</th></tr></thead><tbody>{(g.edges as Rec[]).map((e) => <tr key={e.id} className="cursor-pointer" onClick={() => setSel(e)}><td><Mono>{e.ref}</Mono></td><td>{label(e.from)}</td><td><Tag>{e.type}</Tag></td><td>{label(e.to)}</td><td><Certainty v={e.certainty} pct={e.pct} /></td><td className="text-mute">{e.reasoning}</td></tr>)}</tbody></table></Panel></>}
    {form && <RelForm caseId={caseId} refs={refs} onClose={() => setForm(false)} onSaved={() => { setForm(false); load(); reload(); }} />}
    {del && <Confirm danger title={`Delete ${del.ref}?`} confirm="Delete" body="The relationship is removed from the graph. The deletion is audit-logged." onYes={async () => { await api(`/relationships/${del.id}`, { method: "DELETE" }); toast("Relationship deleted"); setSel(null); load(); }} onClose={() => setDel(null)} />}</div>;
}
