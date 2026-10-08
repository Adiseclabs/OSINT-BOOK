import { useEffect, useState } from "react";
import { api, Rec } from "../lib";
import { Loading, Mono, PageHead, Panel, Dl } from "../ui";

const KEYS: [string, string][] = [["Ctrl K  or  /", "Global search"], ["Alt 1-9", "Jump to a section"], ["?", "Keyboard shortcuts"], ["Esc", "Close dialog"], ["Double-click row", "Edit record"]];
export default function About() {
  const [a, setA] = useState<Rec | null>(null);
  useEffect(() => { api("/about").then(setA); }, []);
  return <div className="max-w-5xl"><PageHead title="About OSINT BOOK" sub="Open Source Intelligence Investigation & Case Management" />
    <div className="grid md:grid-cols-[1.4fr_1fr] gap-3">
      <div className="space-y-3">
        <Panel title="Author"><div className="flex items-start gap-4"><div className="w-14 h-14 border border-line grid place-items-center font-mono text-lg shrink-0" aria-hidden>AB</div>
          <div><div className="text-base font-semibold">Aditya Bhosale</div><div className="text-xs text-mute">Designer and developer of OSINT BOOK</div></div></div>
          <p className="text-sm mt-3">OSINT BOOK was built to give open-source investigators a single, local workstation where every claim stays tied to its source, every file keeps its hash, and every conclusion states how certain it really is.</p></Panel>
        <Panel title="Principles"><ul className="text-sm space-y-2 list-none">
          {[["Provenance first", "Each finding links to the sources and evidence behind it. Unsupported findings are flagged, never hidden."], ["Say how sure you are", "FACT, OBSERVATION, INFERENCE and HYPOTHESIS are kept apart, and uncertain relationships are drawn as uncertain."], ["Preserve, then analyse", "Evidence is hashed on import, immutable, and has a tamper-evident chain of custody."],
            ["Lawful and minimal", "Public information only, recorded authorization, masked personal identifiers, no collection of credentials or private data."], ["Local by default", "Data stays on this machine. No telemetry, no cloud service."]].map(([t, d]) => <li key={t} className="flex gap-3"><b className="w-36 shrink-0 font-medium">{t}</b><span className="text-mute">{d}</span></li>)}</ul></Panel>
        <Panel title="Standards used"><Dl rows={[["Source grading", "Admiralty system: reliability A-F and information credibility 1-6"], ["Sharing markings", "Traffic Light Protocol (TLP): CLEAR, GREEN, AMBER, AMBER+STRICT, RED"], ["Integrity", "SHA-256 hashes, hash-chained audit log, backup manifests"], ["Workflow", "Discover, collect, preserve, verify, correlate, analyze, assess, report"]]} /></Panel></div>
      <div className="space-y-3">
        <Panel title="This installation">{!a ? <Loading /> : <Dl rows={[["Version", <Mono>{a.version}</Mono>], ["Cases", a.cases], ["Evidence items", a.evidence], ["Audit records", a.audit_records], ["Database", `${(a.db_size / 1024).toFixed(0)} KB`], ["Data folder", <span className="font-mono text-xs break-all">{a.data_dir}</span>]]} />}</Panel>
        <Panel title="Keyboard"><table className="w-full"><tbody>{KEYS.map(([k, d]) => <tr key={k}><td className="font-mono text-xs whitespace-nowrap">{k}</td><td className="text-mute">{d}</td></tr>)}</tbody></table></Panel>
        <Panel title="Built with"><p className="text-xs text-mute">FastAPI, SQLAlchemy, SQLite, React, TypeScript, Tailwind CSS, IBM Plex fonts (SIL OFL).</p></Panel>
        <Panel title="Use responsibly"><p className="text-xs text-mute">For authorized investigations using lawfully obtained, public information. Not affiliated with any government or law-enforcement agency. Outputs are analyst work product, not legal findings.</p></Panel></div></div></div>;
}
