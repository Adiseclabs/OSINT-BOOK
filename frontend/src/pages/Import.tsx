import { useRef, useState } from "react";
import { Upload } from "lucide-react";
import { api, Rec } from "../lib";
import { useApp } from "../ctx";
import { Btn, Modal } from "../ui";

const COLS: Rec = { identifiers: "id_type,value,observed_date,confidence,notes", accounts: "platform,username,profile_url,display_name,bio,public_website,status,first_observed,last_observed", sources: "title,url,source_type,publisher,author,publication_date,access_date,reliability,credibility,notes" };
export function ImportButton({ kind, onDone }: { kind: string; onDone: () => void }) {
  const { caseId, canWrite, toast } = useApp(); const [open, setOpen] = useState(false); const [file, setFile] = useState<File | null>(null); const [ack, setAck] = useState(false); const [res, setRes] = useState<Rec | null>(null); const [busy, setBusy] = useState(false); const ref = useRef<HTMLInputElement>(null);
  if (!canWrite || !caseId) return null;
  const go = async () => { setBusy(true); const f = new FormData(); f.append("case_id", caseId); f.append("file", file!); f.append("acknowledge_sensitive", String(ack)); try { const r = await api(`/import/${kind}`, { form: f }); setRes(r); if (r.imported) { toast(`${r.imported} record(s) imported`); onDone(); } } catch (e: any) { toast(e.message, "err"); } setBusy(false); };
  return <><Btn onClick={() => { setOpen(true); setRes(null); setFile(null); }}><Upload size={13} /> Import CSV</Btn>
    {open && <Modal title={`Import ${kind} from CSV`} onClose={() => setOpen(false)}><div className="space-y-2.5 text-sm">
      <p className="text-xs text-mute">Header row required. Columns: <code className="font-mono">{COLS[kind]}</code>. Max 500 rows. Every row is validated like manual entry; invalid rows are reported and skipped. Import public information only.</p>
      <input ref={ref} type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)} aria-label="CSV file" />
      {kind === "identifiers" && <label className="flex gap-2 text-xs items-start"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /><span>The file may contain emails or phone numbers. I confirm they are public, relevant and within my authorization.</span></label>}
      {res && <div className="border border-line p-2 text-xs"><b>{res.imported}</b> imported, <b>{res.rejected}</b> rejected{res.errors.slice(0, 8).map((x: Rec) => <div key={x.row} className="text-bad">Row {x.row}: {typeof x.error === "string" ? x.error : JSON.stringify(x.error)}</div>)}</div>}
      <div className="flex justify-end gap-2"><Btn onClick={() => setOpen(false)}>Close</Btn><Btn kind="primary" disabled={!file || busy} onClick={go}>{busy ? "Importing..." : "Import"}</Btn></div></div></Modal>}</>;
}
