
from app.agents.fact_agent import FactAgent
from app.agents.constitutional_agent import ConstitutionalAgent
from app.agents.contradiction_agent import ContradictionAgent
from app.audit.audit_engine import AuditEngine

class LegalOrchestrator:

    def __init__(self):
        self.fact_agent = FactAgent()
        self.constitutional_agent = ConstitutionalAgent()
        self.contradiction_agent = ContradictionAgent()
        self.audit_engine = AuditEngine()

    def process(self, texto: str):

        state = {}

        factos = self.fact_agent.extract(texto)

        constitutional = self.constitutional_agent.analyse(factos)

        contraditorio = self.contradiction_agent.challenge(factos)

        result = {
            "factos": factos,
            "constitutional_analysis": constitutional,
            "contraditorio": contraditorio
        }

        audit = self.audit_engine.validate(result)

        return {
            "result": result,
            "audit": audit
        }
