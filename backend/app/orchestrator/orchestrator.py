"""
Orquestrador jurídico real.
Pipeline: RAG → qualificação → análise LLM → validação anti-alucinação → auditoria.
O LLM é apenas a camada linguística. A lógica estrutural é código determinístico.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
import anthropic
import structlog

from app.core.config import get_settings
from app.core.schemas import (
    AnalysisRequest, AnalysisResponse,
    NormaIdentificada, AuditInfo, AreaJuridica,
)
from app.rag.motor import RAGJuridico, ValidadorCitacoes

logger = structlog.get_logger(__name__)


SYSTEM_PROMPT = """És um sistema jurídico institucional português.
Respondes SEMPRE em JSON válido com a estrutura exacta indicada.
Nunca inventas artigos ou diplomas que não existam nas fontes fornecidas.
Quando não tens certeza, diz explicitamente na conclusão.
Todos os artigos citados devem constar nas NORMAS RELEVANTES fornecidas."""

PROMPT_TEMPLATE = """
FONTES ACTIVAS: {fontes}

NORMAS RELEVANTES RECUPERADAS (usa apenas estas):
{normas_rag}

CASO:
{caso}

Responde EXCLUSIVAMENTE com este JSON (sem markdown, sem texto extra):
{{
  "factos": ["facto 1", "facto 2"],
  "qualificacao_juridica": "string com qualificação",
  "analise": "análise jurídica detalhada com citações exactas dos artigos acima",
  "vias_processuais": ["via 1", "via 2"],
  "conclusao": "conclusão fundamentada",
  "contraditorio": "argumentos que a parte contrária poderia usar"
}}
"""


class JuridicalOrchestrator:
    """
    Orquestrador com pipeline determinístico.
    Cada etapa é independente e auditável.
    """

    def __init__(self):
        self._settings = get_settings()
        self._rag = RAGJuridico()
        self._validator = ValidadorCitacoes()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    async def process(self, request: AnalysisRequest) -> AnalysisResponse:
        caso_id = str(uuid.uuid4())
        log = logger.bind(caso_id=caso_id)

        log.info("pipeline.start", texto_len=len(request.texto))

        # Etapa 1: RAG — retrieval de normas relevantes
        chunks = self._rag.search(request.texto, top_k=6)
        normas_rag_texto = "\n".join(
            f"- Art. {c.artigo}.º {c.diploma} (score={c.score}): {c.texto[:200]}..."
            for c in chunks
        )
        log.info("rag.done", chunks_found=len(chunks))

        # Etapa 2: LLM — análise jurídica estruturada
        prompt = PROMPT_TEMPLATE.format(
            fontes=", ".join(request.fontes),
            normas_rag=normas_rag_texto if chunks else "Nenhuma norma específica recuperada.",
            caso=request.texto,
        )

        log.info("llm.call.start", model=self._settings.anthropic_model)
        message = self._client.messages.create(
            model=self._settings.anthropic_model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        resposta_raw = message.content[0].text
        log.info(
            "llm.call.done",
            tokens_in=message.usage.input_tokens,
            tokens_out=message.usage.output_tokens,
        )

        # Etapa 3: Parse estruturado
        try:
            dados = json.loads(resposta_raw)
        except json.JSONDecodeError:
            # Fallback: tenta extrair JSON do texto
            import re
            match = re.search(r"\{.*\}", resposta_raw, re.DOTALL)
            if match:
                dados = json.loads(match.group())
            else:
                log.error("llm.parse.failed", raw=resposta_raw[:200])
                raise ValueError("LLM não devolveu JSON válido")

        # Etapa 4: Validação anti-alucinação
        texto_completo = dados.get("analise", "") + " " + dados.get("conclusao", "")
        citacoes_validas, citacoes_suspeitas = self._validator.extrair_e_validar(texto_completo)

        if citacoes_suspeitas:
            log.warning("hallucination.detected", suspeitas=citacoes_suspeitas)

        # Etapa 5: Construir normas estruturadas
        normas = []
        for chunk in chunks[:5]:
            normas.append(NormaIdentificada(
                diploma=chunk.diploma,
                artigo=chunk.artigo,
                relevancia=min(chunk.score / 10.0, 1.0),
                excerto=chunk.texto[:150] + "...",
            ))

        # Etapa 6: Auditoria
        audit = AuditInfo(
            timestamp=datetime.now(timezone.utc),
            normas_citadas=len(citacoes_validas),
            fontes_utilizadas=request.fontes,
            modelo=self._settings.anthropic_model,
            tokens_input=message.usage.input_tokens,
            tokens_output=message.usage.output_tokens,
            grounded=len(citacoes_suspeitas) == 0,
        )

        log.info(
            "pipeline.done",
            normas=len(normas),
            grounded=audit.grounded,
            suspeitas=len(citacoes_suspeitas),
        )

        return AnalysisResponse(
            caso_id=caso_id,
            factos=dados.get("factos", []),
            qualificacao_juridica=dados.get("qualificacao_juridica", ""),
            normas=normas,
            analise=dados.get("analise", ""),
            vias_processuais=dados.get("vias_processuais", []),
            conclusao=dados.get("conclusao", ""),
            contraditorio=dados.get("contraditorio"),
            audit=audit,
        )
