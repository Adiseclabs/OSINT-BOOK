import { useState } from "react";
import { EntityPage, refLabel } from "../EntityPage";
import { FieldDef, Mono, Status, Tabs, Kind, Tag, Certainty, PageHead } from "../ui";
import { Rec, CONF, PRIORITIES } from "../lib";
import { Link } from "react-router-dom";
import { ImportButton } from "./Import";

const CONF3 = ["Low", "Medium", "High", "Confirmed"];
export const subjectFields: FieldDef[] = [
  { name: "display_name", label: "Display name", req: true }, { name: "subject_type", label: "Type", type: "select", options: ["Person", "Organization", "Group", "Unknown"], half: true },
  { name: "confidence", label: "Identity confidence", type: "select", options: CONF3, half: true }, { name: "aliases", label: "Known aliases", type: "list" },
  { name: "role", label: "Investigation role" }, { name: "description", label: "Description", type: "textarea", help: "Describe what is observed. Do not assume two identities are the same person." }];

export function Subjects() {
  const [tab, setTab] = useState("subjects");
  const common = { searchHint: "Search" };
  return <div><PageHead title="Subjects" sub="People and organizations under investigation, with the public identifiers and accounts observed for them." />
    <Tabs value={tab} onChange={setTab} tabs={[{ id: "subjects", label: "Subjects" }, { id: "identifiers", label: "Identifiers" }, { id: "accounts", label: "Accounts / profiles" }, { id: "organizations", label: "Organizations" }, { id: "domains", label: "Domains" }]} />
    {tab === "subjects" && <EntityPage hideHead endpoint="subjects" title="Subjects" singular="Subject" fields={subjectFields} {...common} cols={[
      { key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "80px" }, { key: "display_name", label: "Name", render: (r) => <b className="font-medium">{r.display_name}</b> },
      { key: "subject_type", label: "Type" }, { key: "aliases", label: "Aliases", render: (r) => (r.aliases || []).map((a: string) => <Tag key={a}>{a}</Tag>) }, { key: "role", label: "Role" }, { key: "confidence", label: "Confidence", render: (r) => <Status v={r.confidence} /> }]} />}
    {tab === "identifiers" && <EntityPage hideHead endpoint="identifiers" title="Identifiers" singular="Identifier" {...common} filters={[{ key: "id_type", label: "Type", options: ["Username", "Email", "Phone", "Website", "Domain", "Profile URL", "Organization", "IP address", "Other"] }]}
      defaults={{ id_type: "Username", confidence: "Medium" }} toolbar={(re) => <ImportButton kind="identifiers" onDone={re} />} fields={[
        { name: "id_type", label: "Type", type: "select", req: true, options: ["Username", "Email", "Phone", "Website", "Domain", "Profile URL", "Organization", "IP address", "Other"], half: true }, { name: "value", label: "Identifier", req: true, half: true },
        { name: "subject_id", label: "Subject", type: "ref", ref: "subject", half: true }, { name: "source_id", label: "Source", type: "ref", ref: "source", half: true, help: "Where was it observed?" },
        { name: "observed_date", label: "Date observed", type: "date", half: true }, { name: "confidence", label: "Confidence", type: "select", options: CONF3, half: true },
        { name: "sensitive", label: "Treat as sensitive (mask in UI)", type: "check" }, { name: "notes", label: "Notes", type: "textarea" }]}
      cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "70px" }, { key: "id_type", label: "Type" }, { key: "value", label: "Identifier", render: (r) => <span className="font-mono text-xs">{r.value}{r.masked && <Tag>masked</Tag>}</span> },
        { key: "subject_id", label: "Subject", render: (r, c) => refLabel(c.refs, "subject", r.subject_id) }, { key: "source_id", label: "Source", render: (r, c) => refLabel(c.refs, "source", r.source_id) }, { key: "observed_date", label: "Observed" }, { key: "confidence", label: "Confidence", render: (r) => <Status v={r.confidence} /> }]} />}
    {tab === "accounts" && <EntityPage hideHead endpoint="accounts" title="Accounts" singular="Account" {...common} filters={[{ key: "status", label: "Status", options: ["Active", "Inactive", "Unknown", "Deleted", "Suspended"] }]} defaults={{ status: "Unknown", confidence: "Medium" }} toolbar={(re) => <ImportButton kind="accounts" onDone={re} />} fields={[
      { name: "platform", label: "Platform", req: true, half: true }, { name: "username", label: "Username", req: true, half: true }, { name: "profile_url", label: "Profile URL" }, { name: "display_name", label: "Display name", half: true },
      { name: "public_website", label: "Public website", half: true }, { name: "bio", label: "Bio (as shown publicly)", type: "textarea" }, { name: "subject_id", label: "Subject", type: "ref", ref: "subject", half: true, help: "Leave empty until attribution is justified." },
      { name: "evidence_id", label: "Evidence reference", type: "ref", ref: "evidence", half: true }, { name: "first_observed", label: "First observed", type: "date", half: true }, { name: "last_observed", label: "Last observed", type: "date", half: true },
      { name: "status", label: "Status", type: "select", options: ["Active", "Inactive", "Unknown", "Deleted", "Suspended"], half: true }, { name: "confidence", label: "Confidence", type: "select", options: CONF3, half: true }]}
      cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "70px" }, { key: "platform", label: "Platform" }, { key: "username", label: "Username", render: (r) => <span className="font-mono text-xs">{r.username}</span> },
        { key: "subject_id", label: "Subject", render: (r, c) => refLabel(c.refs, "subject", r.subject_id) }, { key: "status", label: "Status", render: (r) => <Status v={r.status} /> }, { key: "first_observed", label: "First seen" }, { key: "last_observed", label: "Last seen" },
        { key: "evidence_id", label: "Evidence", render: (r, c) => refLabel(c.refs, "evidence", r.evidence_id) }, { key: "confidence", label: "Confidence", render: (r) => <Status v={r.confidence} /> }]} />}
    {tab === "organizations" && <EntityPage hideHead endpoint="organizations" title="Organizations" singular="Organization" {...common} fields={[{ name: "name", label: "Name", req: true }, { name: "org_type", label: "Type", half: true }, { name: "jurisdiction", label: "Jurisdiction", half: true }, { name: "website", label: "Website" }, { name: "description", label: "Description", type: "textarea" }]}
      cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "70px" }, { key: "name", label: "Name" }, { key: "org_type", label: "Type" }, { key: "jurisdiction", label: "Jurisdiction" }, { key: "website", label: "Website" }]} />}
    {tab === "domains" && <EntityPage hideHead endpoint="domains" title="Domains" singular="Domain" {...common} fields={[{ name: "name", label: "Domain", req: true, half: true }, { name: "registrar", label: "Registrar", half: true }, { name: "registered_on", label: "Registered on", type: "date", half: true },
      { name: "subject_id", label: "Subject", type: "ref", ref: "subject", half: true }, { name: "source_id", label: "Source", type: "ref", ref: "source" }, { name: "notes", label: "Notes", type: "textarea" }]}
      cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "70px" }, { key: "name", label: "Domain", render: (r) => <span className="font-mono text-xs">{r.name}</span> }, { key: "registrar", label: "Registrar" }, { key: "registered_on", label: "Registered" }, { key: "source_id", label: "Source", render: (r, c) => refLabel(c.refs, "source", r.source_id) }]} />}
  </div>;
}

export const sourceFields: FieldDef[] = [
  { name: "title", label: "Title", req: true }, { name: "source_type", label: "Source type", type: "select", options: ["Web page", "Social profile", "News article", "Public record", "Document", "Domain record", "Security disclosure", "Other"], half: true },
  { name: "reliability", label: "Source reliability", type: "select", options: ["High", "Medium", "Low", "Unknown"], half: true, help: "A = High, C = Medium, E = Low, F = Unknown" }, { name: "credibility", label: "Information credibility", type: "select", options: ["1", "2", "3", "4", "5", "6"], req: true, half: true, help: "1 confirmed ... 5 improbable, 6 cannot be judged" }, { name: "url", label: "URL" }, { name: "archived_url", label: "Archived URL" },
  { name: "publisher", label: "Publisher", half: true }, { name: "author", label: "Author", half: true }, { name: "publication_date", label: "Publication date", type: "date", half: true }, { name: "access_date", label: "Access date", type: "date", half: true },
  { name: "confidence", label: "Confidence in source", type: "select", options: CONF3, half: true }, { name: "tags", label: "Tags", half: true }, { name: "notes", label: "Notes", type: "textarea" }];

export function Sources() {
  return <EntityPage endpoint="sources" title="Sources" singular="Source" fields={sourceFields} defaults={{ source_type: "Web page", reliability: "Unknown", credibility: "6", confidence: "Medium", access_date: new Date().toISOString().slice(0, 10) }}
    searchHint="Search title, URL, publisher" filters={[{ key: "reliability", label: "Reliability", options: ["High", "Medium", "Low", "Unknown"] }, { key: "source_type", label: "Type", options: ["Web page", "Social profile", "News article", "Public record", "Document", "Domain record", "Security disclosure", "Other"] }]}
    cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "80px" }, { key: "title", label: "Title", render: (r) => <div><div>{r.title}</div><div className="font-mono text-xs text-mute break-all">{r.url}</div></div> }, { key: "source_type", label: "Type" },
      { key: "publisher", label: "Publisher" }, { key: "publication_date", label: "Published" }, { key: "access_date", label: "Accessed" }, { key: "reliability", label: "Reliability", render: (r) => <Status v={r.reliability} /> }, { key: "credibility", label: "Admiralty", render: (r) => <span className="font-mono text-xs" title="Source reliability + information credibility">{({ High: "A", Medium: "C", Low: "E" } as Rec)[r.reliability] || "F"}{r.credibility || "6"}</span> }, { key: "confidence", label: "Confidence", render: (r) => <Status v={r.confidence} /> }]} toolbar={(re) => <ImportButton kind="sources" onDone={re} />} />;
}

export const findingFields: FieldDef[] = [
  { name: "title", label: "Title (state the claim)", req: true }, { name: "kind", label: "Type", type: "select", req: true, options: ["FACT", "OBSERVATION", "INFERENCE", "HYPOTHESIS"], half: true, help: "FACT = directly shown by evidence. INFERENCE/HYPOTHESIS are never reported as confirmed." },
  { name: "subject_id", label: "Affected subject", type: "ref", ref: "subject", half: true }, { name: "severity", label: "Severity", type: "select", options: ["Informational", "Low", "Medium", "High", "Critical"], half: true },
  { name: "confidence", label: "Confidence", type: "select", options: CONF3, half: true }, { name: "status", label: "Status", type: "select", options: ["Draft", "Under Review", "Approved", "Rejected"], half: true },
  { name: "description", label: "Description", type: "textarea" }, { name: "analyst_assessment", label: "Analyst assessment / reasoning", type: "textarea" }, { name: "recommendation", label: "Recommendation", type: "textarea" }];

export function tasksCols() { return []; }
export function Tasks() {
  return <EntityPage endpoint="tasks" title="Tasks" singular="Task" defaults={{ status: "Open", priority: "Medium", stage: "COLLECT" }} searchHint="Search tasks"
    filters={[{ key: "status", label: "Status", options: ["Open", "In Progress", "Blocked", "Done"] }, { key: "priority", label: "Priority", options: PRIORITIES }, { key: "stage", label: "Stage", options: ["DISCOVER", "COLLECT", "PRESERVE", "VERIFY", "CORRELATE", "ANALYZE", "ASSESS", "REPORT"] }]}
    fields={[{ name: "title", label: "Task", req: true }, { name: "status", label: "Status", type: "select", options: ["Open", "In Progress", "Blocked", "Done"], half: true }, { name: "priority", label: "Priority", type: "select", options: PRIORITIES, half: true },
      { name: "stage", label: "Workflow stage", type: "select", options: ["DISCOVER", "COLLECT", "PRESERVE", "VERIFY", "CORRELATE", "ANALYZE", "ASSESS", "REPORT"], half: true }, { name: "due_date", label: "Due", type: "date", half: true }, { name: "description", label: "Details", type: "textarea" }]}
    cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "80px" }, { key: "title", label: "Task" }, { key: "stage", label: "Stage", render: (r) => <Tag>{r.stage}</Tag> }, { key: "priority", label: "Priority", render: (r) => <Status v={r.priority} /> },
      { key: "status", label: "Status", render: (r) => <Status v={r.status} /> }, { key: "due_date", label: "Due" }]} />;
}
export const FindingsTable = ({ prefill, onChanged }: { prefill?: Rec | null; onChanged?: () => void }) => (
  <EntityPage hideHead endpoint="findings" title="Findings" singular="Finding" fields={findingFields} defaults={{ kind: "OBSERVATION", severity: "Informational", confidence: "Low", status: "Draft" }} prefill={prefill} onChanged={onChanged}
    filters={[{ key: "kind", label: "Type", options: ["FACT", "OBSERVATION", "INFERENCE", "HYPOTHESIS"] }, { key: "severity", label: "Severity", options: ["Informational", "Low", "Medium", "High", "Critical"] }, { key: "status", label: "Status", options: ["Draft", "Under Review", "Approved", "Rejected"] }]}
    cols={[{ key: "ref", label: "ID", render: (r) => <Mono>{r.ref}</Mono>, w: "60px" }, { key: "kind", label: "Type", render: (r) => <Kind v={r.kind} /> }, { key: "title", label: "Finding", render: (r) => <span>{r.title}{r.ai_generated && <span className="ml-1.5 text-xs text-accent font-mono">AI-ASSISTED</span>}</span> },
      { key: "severity", label: "Severity", render: (r) => <Status v={r.severity} /> }, { key: "confidence", label: "Confidence", render: (r) => <Status v={r.confidence} /> }, { key: "status", label: "Status", render: (r) => <Status v={r.status} /> }]} />
);
