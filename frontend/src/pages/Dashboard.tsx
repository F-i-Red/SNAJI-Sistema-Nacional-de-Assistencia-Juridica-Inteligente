
import CaseUpload from "../components/CaseUpload";
import ProcessTimeline from "../components/ProcessTimeline";
import ContradictoryPanel from "../components/ContradictoryPanel";
import ExplainabilityPanel from "../components/ExplainabilityPanel";

export default function Dashboard() {

  return (
    <div style={{ padding: "20px" }}>
      <h1>SNAJI — Sistema Nacional de Assistência Jurídica Inteligente</h1>

      <CaseUpload />

      <ProcessTimeline />

      <ContradictoryPanel />

      <ExplainabilityPanel />
    </div>
  );
}
