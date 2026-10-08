import { useCallback, useEffect, useState } from "react";
import { FileDown } from "lucide-react";
import { api, qs, Rec, download, fmtTs } from "../lib";
import { useApp } from "../ctx";
import { Btn, Empty, Hash, Loading, Mono, PageHead, Panel, Tag } from "../ui";

export default function Reports() {
  const { caseId, activeCase, canWrite, toast } = useApp();
  const [list, setList] = useState<Rec[] | null>(null); const [fmt, setFmt] = useState("html"); const [title, setTitle] = useState(""); const [concl, setConcl] = useState(""); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { if (caseId) setList(await api("/reports" + qs({ case_id: caseId }))); else setList([]); }, [caseId]);
  useEffect(() => { setList(null); load(); }, [load]);
  const gen = async () => { setBusy(true); try { const r = await api("/reports", { body: { case_id: caseId, format: fmt, title, conclusion: concl } }); toast(`${r.ref} generated`); load(); } catch (e: any) { toast(e.message, "err"); } setBusy(false); };
  return <div><PageHead title="Reports" sub={activeCase ? <>Case <Mono>{activeCase.ref}</Mono></> : "Select a case to generate a report"} />
    {!caseId ? <Empty title="No case selected" hint="Choose a case in the top bar." /> : <div className="grid lg:grid-cols-[360px_1fr] gap-3">
      {canWrite && <Panel title="Generate report"><div className="space-y-2.5">
        <label className="f block"><span>Title</span><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={`${activeCase?.ref} investigation report`} /></label>
        <label className="f block"><span>Format</span><select value={fmt} onChange={(e) => setFmt(e.target.value)}><option value="html">HTML</option><option value="pdf">PDF</option><option value="json">JSON</option></select></label>
        <label className="f block"><span>Analyst conclusion (section 13)</span><textarea rows={5} value={concl} onChange={(e) => setConcl(e.target.value)} /></label>
        <p className="text-xs text-mute">Findings are labelled FACT / OBSERVATION / INFERENCE / HYPOTHESIS. Inferences and hypotheses are never described as confirmed, and findings without a source or evidence are flagged UNSUPPORTED.</p>
        <Btn kind="primary" disabled={busy} onClick={gen}><FileDown size={13} /> {busy ? "Generating..." : "Generate"}</Btn></div></Panel>}
      <Panel title="Generated reports" pad={false}>{!list ? <Loading /> : list.length === 0 ? <Empty title="No reports yet" /> :
        <table className="w-full"><thead><tr><th>ID</th><th>Title</th><th>Format</th><th>Created</th><th>SHA-256</th><th /></tr></thead><tbody>{list.map((r) => <tr key={r.id}><td><Mono>{r.ref}</Mono></td><td>{r.title}</td><td><Tag>{r.fmt.toUpperCase()}</Tag></td><td className="text-mute">{fmtTs(r.created_at)}</td><td><Hash v={r.sha256.slice(0, 16) + "..."} /></td>
          <td><Btn small onClick={() => download(`/reports/${r.id}/download`, `${r.ref}.${r.fmt}`).catch((e) => toast(e.message, "err"))}>Download</Btn></td></tr>)}</tbody></table>}</Panel></div>}</div>;
}
