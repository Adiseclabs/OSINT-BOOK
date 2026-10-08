export type Rec = Record<string, any>;
const KEY = "ob_token";
export const token = () => sessionStorage.getItem(KEY);
export const setToken = (t: string | null) => (t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY));

export class ApiError extends Error {
  status: number; fields: Record<string, string>;
  constructor(status: number, msg: string, fields: Record<string, string> = {}) { super(msg); this.status = status; this.fields = fields; }
}
let onAuthLost: () => void = () => {};
export const setAuthLost = (f: () => void) => (onAuthLost = f);

async function parse(r: Response) {
  const text = await r.text(); let j: any = null;
  try { j = text ? JSON.parse(text) : null; } catch { /* non-json */ }
  if (r.ok) return j;
  if (r.status === 401 && token()) { setToken(null); onAuthLost(); }
  const d = j?.detail;
  if (d?.errors) throw new ApiError(r.status, "Check the highlighted fields", d.errors);
  throw new ApiError(r.status, typeof d === "string" ? d : d?.error || `Request failed (${r.status})`, {});
}
export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const h: Record<string, string> = {}; const t = token(); if (t) h.Authorization = "Bearer " + t;
  let body: any; if (opts.form) body = opts.form; else if (opts.body !== undefined) { h["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  return parse(await fetch("/api" + path, { method: opts.method || (body ? "POST" : "GET"), headers: h, body }));
}
export const qs = (o: Rec) => { const p = new URLSearchParams(); Object.entries(o).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, String(v))); const s = p.toString(); return s ? "?" + s : ""; };
export async function download(path: string, name: string) {
  const r = await fetch("/api" + path, { headers: { Authorization: "Bearer " + token() } });
  if (!r.ok) throw new ApiError(r.status, "Download failed");
  const u = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = u; a.download = name; a.click(); URL.revokeObjectURL(u);
}
export async function blobUrl(path: string) {
  const r = await fetch("/api" + path, { headers: { Authorization: "Bearer " + token() } });
  if (!r.ok) throw new ApiError(r.status, "Preview unavailable"); return URL.createObjectURL(await r.blob());
}
export const fmtTs = (s?: string | null) => (s ? s.replace("T", " ").replace("Z", "").slice(0, 16) : "-");
export const fmtTime = (s?: string | null) => (s ? s.replace("T", " ").replace("Z", "").slice(11, 19) : "-");

export const STAGES = ["DISCOVER", "COLLECT", "PRESERVE", "VERIFY", "CORRELATE", "ANALYZE", "ASSESS", "REPORT"];
export const PRIORITIES = ["Low", "Medium", "High", "Critical"];
export const CASE_STATUS = ["Draft", "Active", "Under Review", "Suspended", "Closed", "Archived"];
export const CASE_TYPES = ["General", "Corporate impersonation", "Threat actor alias research", "Security incident", "Digital due diligence", "Academic", "Online identity"];
export const CONF = ["Low", "Medium", "High", "Confirmed"];
export const ENTITY_TYPES = ["subject", "identifier", "account", "organization", "domain", "evidence", "source"];
export const REL_TYPES = ["USES", "OWNS", "MENTIONS", "ASSOCIATED_WITH", "WORKS_FOR", "LINKED_TO", "OBSERVED_ON", "REFERENCES"];
