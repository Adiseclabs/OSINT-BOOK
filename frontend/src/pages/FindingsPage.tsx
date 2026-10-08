import { PageHead, Mono } from "../ui";
import { useApp } from "../ctx";
import { FindingsPanel } from "./Findings";
import { Empty } from "../ui";
export default function FindingsPage() {
  const { caseId, activeCase } = useApp();
  return <div><PageHead title="Findings" sub={activeCase ? <>Case <Mono>{activeCase.ref}</Mono> - every finding states its type, confidence and provenance</> : "Select a case"} />
    {caseId ? <FindingsPanel /> : <Empty title="No case selected" hint="Findings belong to a case. Choose one in the top bar." />}</div>;
}
