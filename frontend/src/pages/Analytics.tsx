import { useEffect, useState } from "react";
import { Check, Circle } from "lucide-react";
import { api, Rec } from "../lib";
import { Loading, Panel, Kind } from "../ui";

const Bars = ({ data, render }: { data: Rec; render?: (k: string) => any }) => { const max = Math.max(1, ...Object.values<number>(data)); const e = Object.entries<number>(data);
  return e.length === 0 ? <div className="text-xs text-mute">No data yet.</div> : <div className="space-y-1">{e.map(([k, v]) => <div key={k} className="flex items-center gap-2 text-xs"><span className="w-28 shrink-0">{render ? render(k) : k}</span><div className="flex-1 h-1.5 bg-raised"><div className="h-full bg-accent" style={{ width: `${(v / max) * 100}%` }} /></div><b className="font-mono w-5 text-right">{v}</b></div>)}</div>; };

export default function Analytics({ caseId }: { caseId: string }) {
  const [a, setA] = useState<Rec | null>(null);
  useEffect(() => { api(`/cases/${caseId}/analytics`).then(setA); }, [caseId]);
  if (!a) return <Loading />;
  const ready = a.checks.filter((c: Rec) => c.ok).length;
  return <div className="grid lg:grid-cols-2 gap-3">
    <Panel title={`Report readiness  ${ready}/${a.checks.length}`} className="lg:row-span-2"><ul className="space-y-2">{a.checks.map((c: Rec) => <li key={c.name} className="flex gap-2 text-sm">{c.ok ? <Check size={15} className="text-ok shrink-0 mt-0.5" /> : <Circle size={15} className="text-warn shrink-0 mt-0.5" />}<div><div className={c.ok ? "" : "font-medium"}>{c.name}</div>{!c.ok && <div className="text-xs text-mute">{c.hint}</div>}</div></li>)}</ul></Panel>
    <Panel title="Findings by epistemic type"><Bars data={a.findings_by_kind} render={(k) => <Kind v={k} />} /><div className="label mt-3 mb-1">By confidence</div><Bars data={a.findings_by_confidence} /></Panel>
    <Panel title="Source grading (Admiralty)"><table className="w-full text-xs"><thead><tr><th /><>{[1, 2, 3, 4, 5, 6].map((n) => <th key={n} className="text-center">{n}</th>)}</></tr></thead><tbody>{["A", "B", "C", "D", "E", "F"].map((l) => <tr key={l}><td className="font-mono font-medium">{l}</td>{[1, 2, 3, 4, 5, 6].map((n) => { const v = a.admiralty_grid[`${l}${n}`]; return <td key={n} className={`text-center font-mono ${v ? "bg-accent/20 text-ink" : "text-mute/40"}`}>{v || "·"}</td>; })}</tr>)}</tbody></table>
      <div className="text-xs text-mute mt-2">Rows: source reliability (A reliable ... F cannot be judged). Columns: information credibility (1 confirmed ... 6 cannot be judged). High, Medium and Low map to A, C and E.</div></Panel>
    <Panel title="Evidence by type"><Bars data={a.evidence_by_type} /></Panel>
    <Panel title="Task progress"><Bars data={a.tasks} /></Panel></div>;
}
