import { ReactNode, useCallback, useEffect, useState } from "react";
import { Plus, Search, Trash2, Eye } from "lucide-react";
import { api, qs, Rec, ApiError, fmtTs } from "./lib";
import { useApp } from "./ctx";
import { Btn, Empty, Field, FieldDef, Loading, Modal, Confirm, Pager, Panel, useDebounced, Mono } from "./ui";

export type Col = { key: string; label: string; render?: (r: Rec, ctx: { refs: Rec }) => ReactNode; w?: string };
export type Filter = { key: string; label: string; options: string[] };

export function useRefs(caseId: string) {
  const [refs, setRefs] = useState<Rec>({});
  const load = useCallback(async () => {
    if (!caseId) return setRefs({});
    try {
      const [ents, f] = await Promise.all([api("/entities" + qs({ case_id: caseId })), api("/findings" + qs({ case_id: caseId, size: 200 }))]);
      const g: Rec = { finding: f.items.map((x: Rec) => ({ id: x.id, ref: x.ref, label: x.title })) };
      ents.forEach((e: Rec) => (g[e.type] ||= []).push(e)); setRefs(g);
    } catch { /* ignore */ }
  }, [caseId]);
  useEffect(() => { load(); }, [load]);
  return { refs, reload: load };
}
export const refLabel = (refs: Rec, type: string, id?: string) => { const o = (refs[type] || []).find((x: Rec) => x.id === id); return o ? <><Mono>{o.ref}</Mono> {o.label}</> : <span className="text-mute">-</span>; };

export function EntityPage({ endpoint, title, singular, cols, fields, filters = [], searchHint = "Search", defaults = {}, canCreate = true, rowExtra, onChanged, prefill, hideHead, toolbar }: {
  endpoint: string; title: string; singular: string; cols: Col[]; fields: FieldDef[]; filters?: Filter[]; searchHint?: string; defaults?: Rec; canCreate?: boolean;
  rowExtra?: (r: Rec, reload: () => void) => ReactNode; onChanged?: () => void; prefill?: Rec | null; hideHead?: boolean; toolbar?: (reload: () => void) => ReactNode;
}) {
  const { caseId, activeCase, canWrite, toast, cases } = useApp();
  const { refs, reload: reloadRefs } = useRefs(caseId);
  const [data, setData] = useState<{ items: Rec[]; total: number } | null>(null);
  const [q, setQ] = useState(""); const dq = useDebounced(q);
  const [page, setPage] = useState(1); const size = 40;
  const [fv, setFv] = useState<Rec>({});
  const [edit, setEdit] = useState<Rec | null>(null);
  const [del, setDel] = useState<Rec | null>(null);
  const load = useCallback(async () => {
    try { setData(await api(`/${endpoint}` + qs({ case_id: caseId, q: dq, page, size, ...fv }))); } catch (e: any) { toast(e.message, "err"); setData({ items: [], total: 0 }); }
  }, [endpoint, caseId, dq, page, fv, toast]);
  useEffect(() => { setPage(1); }, [caseId, dq, fv]);
  useEffect(() => { setData(null); load(); }, [load]);
  useEffect(() => { if (prefill) setEdit({ ...defaults, ...prefill }); }, [prefill]); // eslint-disable-line
  const caseRef = (id: string) => cases.find((c) => c.id === id)?.ref || "";
  const done = () => { load(); reloadRefs(); onChanged?.(); };

  return (
    <div>
      {!hideHead && <div className="flex items-end justify-between mb-3"><div><h1 className="text-lg font-semibold leading-tight">{title}</h1><div className="text-xs text-mute">{activeCase ? <>Case <Mono>{activeCase.ref}</Mono> {activeCase.title}</> : "All cases you can access"}</div></div>
        {canWrite && canCreate && <Btn kind="primary" disabled={!caseId} title={caseId ? "" : "Select a case in the top bar first"} onClick={() => setEdit({ ...defaults })}><Plus size={14} /> New {singular}</Btn>}</div>}
      <Panel pad={false}>
        <div className="flex gap-2 p-2 border-b border-line flex-wrap">
          <div className="relative flex-1 min-w-[180px]"><Search size={13} className="absolute left-2 top-2 text-mute" /><input className="pl-7" placeholder={searchHint} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter list" /></div>
          {filters.map((f) => <select key={f.key} className="w-auto" aria-label={f.label} value={fv[f.key] || ""} onChange={(e) => setFv({ ...fv, [f.key]: e.target.value })}><option value="">{f.label}: any</option>{f.options.map((o) => <option key={o}>{o}</option>)}</select>)}
        {toolbar?.(done)}</div>
        {!data ? <Loading /> : data.items.length === 0 ? (
          <Empty title={dq || Object.values(fv).some(Boolean) ? `No ${title.toLowerCase()} match these filters` : `No ${title.toLowerCase()} yet`} hint={caseId ? `Record ${singular.toLowerCase()} entries as you find them; each links back to its source.` : "Select a case from the top bar to add records."}
            action={canWrite && canCreate && caseId && !dq ? <Btn kind="primary" onClick={() => setEdit({ ...defaults })}><Plus size={14} /> New {singular}</Btn> : undefined} />
        ) : (
          <div className="overflow-auto max-h-[calc(100vh-250px)]"><table className="w-full"><thead><tr>{!caseId && <th>Case</th>}{cols.map((c) => <th key={c.key} style={{ width: c.w }}>{c.label}</th>)}<th /></tr></thead><tbody>
            {data.items.map((r) => (
              <tr key={r.id} className="cursor-pointer" onDoubleClick={() => canWrite && setEdit(r)}>
                {!caseId && <td><Mono className="text-mute">{caseRef(r.case_id)}</Mono></td>}
                {cols.map((c) => <td key={c.key}>{c.render ? c.render(r, { refs }) : r[c.key] ?? "-"}</td>)}
                <td className="whitespace-nowrap text-right">{rowExtra?.(r, done)}
                  <Btn small kind="ghost" aria-label={`Open ${r.ref}`} onClick={() => setEdit(r)}><Eye size={13} /></Btn>
                  {canWrite && <Btn small kind="ghost" aria-label={`Delete ${r.ref}`} onClick={() => setDel(r)}><Trash2 size={13} /></Btn>}</td></tr>))}
          </tbody></table></div>)}
        {data && <div className="px-2 pb-2"><Pager page={page} size={size} total={data.total} onPage={setPage} /></div>}
      </Panel>
      {edit && <RecordForm singular={singular} endpoint={endpoint} fields={fields} rec={edit} refs={refs} readOnly={!canWrite} caseId={edit.case_id || caseId} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); done(); }} />}
      {del && <Confirm danger title={`Delete ${del.ref}?`} confirm="Delete" body={<>This permanently removes {singular.toLowerCase()} <Mono>{del.ref}</Mono> and unlinks it from findings. The deletion is recorded in the audit log.</>}
        onYes={async () => { try { await api(`/${endpoint}/${del.id}`, { method: "DELETE" }); toast(`${del.ref} deleted`); done(); } catch (e: any) { toast(e.message, "err"); } }} onClose={() => setDel(null)} />}
    </div>
  );
}

export function RecordForm({ singular, endpoint, fields, rec, refs, caseId, onClose, onSaved, readOnly }: { singular: string; endpoint: string; fields: FieldDef[]; rec: Rec; refs: Rec; caseId: string; onClose: () => void; onSaved: () => void; readOnly?: boolean }) {
  const { toast } = useApp();
  const isNew = !rec.id;
  const [v, setV] = useState<Rec>(() => ({ ...rec }));
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [warn, setWarn] = useState(false);
  const sensitive = endpoint === "identifiers" && (["Email", "Phone"].includes(v.id_type) || v.sensitive) && isNew;
  const save = async (ack = false) => {
    setBusy(true); setErrs({});
    const body: Rec = {}; fields.forEach((f) => { if (v[f.name] !== undefined) body[f.name] = f.type === "number" ? (v[f.name] === "" ? null : Number(v[f.name])) : v[f.name]; });
    if (ack) body.sensitive_ack = true;
    if (endpoint === "identifiers" && !isNew && v.masked) delete body.value;
    try {
      if (isNew) await api(`/${endpoint}?case_id=${caseId}`, { body }); else await api(`/${endpoint}/${rec.id}`, { method: "PATCH", body });
      toast(`${singular} saved`); onSaved();
    } catch (e: any) { if (e instanceof ApiError) { setErrs(e.fields); if (!Object.keys(e.fields).length) toast(e.message, "err"); } else toast(e.message, "err"); }
    setBusy(false);
  };
  const reveal = async () => { try { const r = await api(`/${endpoint}/${rec.id}?reveal=true`); setV({ ...v, value: r.value, masked: false }); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <Modal title={`${isNew ? "New" : readOnly ? "View" : "Edit"} ${singular.toLowerCase()}${rec.ref ? " - " + rec.ref : ""}`} onClose={onClose} wide>
      <form onSubmit={(e) => { e.preventDefault(); if (readOnly) return; sensitive ? setWarn(true) : save(); }}>
        <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
          {fields.map((f) => <Field key={f.name} f={f} value={v[f.name]} refs={refs} error={errs[f.name]} onChange={(x) => setV({ ...v, [f.name]: x })} />)}
        </div>
        {errs.sensitive_ack && <div className="text-xs text-bad mt-2">{errs.sensitive_ack}</div>}
        <div className="flex justify-between mt-4">
          <div>{endpoint === "identifiers" && !isNew && v.masked && <Btn type="button" onClick={reveal}><Eye size={13} /> Reveal value (logged)</Btn>}</div>
          <div className="flex gap-2"><Btn type="button" onClick={onClose}>{readOnly ? "Close" : "Cancel"}</Btn>{!readOnly && <Btn kind="primary" type="submit" disabled={busy}>{busy ? "Saving..." : "Save"}</Btn>}</div></div>
      </form>
      {warn && <Confirm title="Sensitive personal information" confirm="I have a lawful basis - save" body={<>You are recording a personal identifier (email / phone / flagged sensitive). Only store what the investigation requires, from public sources, within your authorization scope. The value will be masked by default and every reveal is audit-logged.</>}
        onYes={() => save(true)} onClose={() => setWarn(false)} />}
    </Modal>
  );
}
