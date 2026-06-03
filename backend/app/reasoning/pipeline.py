"""
Pipeline de Reasoning Jurídico do SNAJI.

Em linguagem simples:
  1. Recebe um caso descrito em português
  2. Recupera artigos relevantes (RAG)
  3. Extrai os factos do caso
  4. Qualifica juridicamente (que tipo de problema é este?)
  5. Analisa normas aplicáveis
  6. Produz argumentos de defesa E de acusação (contraditório)
  7. Valida todas as citações (anti-alucinação)
  8. Devolve resultado estruturado e auditável

O LLM é usado apenas nas etapas 3, 4, 5 e 6.
Tudo o resto é código determinístico.
"""

from __future__ import annotations
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import structlog

from app.rag.motor import RAGJuridico, ValidadorCitacoes, Chunk

logger = structlog.get_logger(__name__)


class TipoProcesso(str, Enum):
    LABORAL      = "laboral"
    CIVIL        = "civil"
    PENAL        = "penal"
    ADMINISTRATIVO = "administrativo"
    FAMILIA      = "familia"
    CONSUMO      = "consumo"
    DADOS_PESSOAIS = "dados_pessoais"
    OUTRO        = "outro"


@dataclass
class Facto:
    descricao: str
    relevancia: str  # "alta" | "media" | "baixa"


@dataclass
class NormaAplicada:
    diploma: str
    artigo: str
    epigrase: str
    excerto: str
    relevancia: float
    fonte: str


@dataclass
class ArgumentoJuridico:
    posicao: str        # "acusacao" | "defesa" | "neutro"
    argumento: str
    normas_base: list[str]  # ["CRP-53", "CT-351"]


@dataclass
class ResultadoReasoning:
    caso_id: str
    tipo_processo: TipoProcesso
    factos: list[Facto]
    qualificacao: str
    normas: list[NormaAplicada]
    analise: str
    argumentos_acusacao: list[ArgumentoJuridico]
    argumentos_defesa: list[ArgumentoJuridico]
    vias_processuais: list[str]
    conclusao: str
    grounded: bool
    citacoes_suspeitas: list[dict]
    timestamp: datetime
    tokens_usados: int = 0


# ── Prompts estruturados ────────────────────────────────────────────────────

_SYSTEM = """És um sistema jurídico institucional português especializado em análise processual.
Respondes SEMPRE em JSON válido, sem markdown, sem texto exterior ao JSON.
Citas APENAS artigos que existam nas NORMAS fornecidas.
Quando não tens certeza, dizes explicitamente na conclusão.
A tua análise deve ser equilibrada: apresentas argumentos de ambas as partes."""

_PROMPT_ANALISE = """
TIPO DE PROCESSO IDENTIFICADO: {tipo_processo}

NORMAS RECUPERADAS (usa APENAS estas, com diploma e artigo exactos):
{normas_rag}

CASO:
{caso}

Responde EXCLUSIVAMENTE com este JSON:
{{
  "factos": [
    {{"descricao": "facto relevante 1", "relevancia": "alta"}},
    {{"descricao": "facto relevante 2", "relevancia": "media"}}
  ],
  "qualificacao": "qualificação jurídica do problema em 1-2 frases",
  "analise": "análise jurídica detalhada citando os artigos exactos das normas acima",
  "argumentos_acusacao": [
    {{"argumento": "argumento 1 da parte autora/acusação", "normas_base": ["DIPLOMA-ARTIGO"]}}
  ],
  "argumentos_defesa": [
    {{"argumento": "argumento 1 da defesa/réu", "normas_base": ["DIPLOMA-ARTIGO"]}}
  ],
  "vias_processuais": ["via processual 1", "via processual 2"],
  "conclusao": "conclusão fundamentada, indicando qual a posição juridicamente mais sólida e porquê"
}}
"""

_KEYWORDS_TIPO = {
    TipoProcesso.LABORAL:       ["despedimento","trabalho","salário","férias","trabalhador","empregador","contrato de trabalho","justa causa","indemnização laboral"],
    TipoProcesso.PENAL:       ["suborno","corrupção","crime","furto","roubo","homicídio","ofensa","ameaça","corrupção","burla","coação","arguido","pena","prisão","detenção"],
    TipoProcesso.DADOS_PESSOAIS:["dados pessoais","rgpd","privacidade","consentimento","tratamento de dados","apagamento","portabilidade"],
    TipoProcesso.FAMILIA:       ["divórcio","filhos","alimentos","custódia","casamento","adoção","família","menores","separação"],
    TipoProcesso.CONSUMO:       ["consumidor","produto","garantia","devolução","compra","venda","defeito","fornecedor"],
    TipoProcesso.CIVIL:         ["contrato","propriedade","indemnização","danos","responsabilidade","arrendamento","herança","divida"],
    TipoProcesso.ADMINISTRATIVO:["Estado","administração","município","licença","imposto","multa","recurso administrativo","funcionário público"],
}


def classificar_tipo_processo(texto: str) -> TipoProcesso:
    """
    Classifica o tipo de processo com base em palavras-chave.
    Palavras de alta relevância penal têm peso 3.
    Determinístico — sem LLM. Rápido e auditável.
    """
    texto_lower = texto.lower()
    PESO_ALTO = {"suborno", "corrupção", "crime", "arguido", "prisão", "pena", "homicídio", "furto", "roubo"}
    pontuacao: dict[TipoProcesso, int] = {t: 0 for t in TipoProcesso}
    for tipo, keywords in _KEYWORDS_TIPO.items():
        for kw in keywords:
            if kw in texto_lower:
                pontuacao[tipo] += 3 if kw in PESO_ALTO else 1
    melhor = max(pontuacao, key=lambda t: pontuacao[t])
    return melhor if pontuacao[melhor] > 0 else TipoProcesso.OUTRO


def _formatar_normas_para_prompt(chunks: list[Chunk]) -> str:
    if not chunks:
        return "Nenhuma norma específica recuperada. Indica isso na conclusão."
    linhas = []
    for c in chunks:
        epigrase = f" ({c.epigrase})" if c.epigrase else ""
        excerto = c.texto[:300] + "..." if len(c.texto) > 300 else c.texto
        linhas.append(f"• Art. {c.artigo}.º {c.diploma}{epigrase}: {excerto}")
    return "\n".join(linhas)


def _parse_argumentos(raw: list[dict], posicao: str) -> list[ArgumentoJuridico]:
    resultado = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        resultado.append(ArgumentoJuridico(
            posicao=posicao,
            argumento=item.get("argumento", ""),
            normas_base=item.get("normas_base", []),
        ))
    return resultado


class ReasoningPipeline:
    """
    Pipeline determinístico de análise jurídica.
    Pode correr sem LLM (modo stub) para testes.
    Liga ao LLM quando a chave API estiver configurada.
    """

    def __init__(self, llm_client=None):
        self._rag = RAGJuridico()
        self._validator = ValidadorCitacoes()
        self._llm = llm_client  # None = modo sem LLM (testes)
        logger.info("reasoning.pipeline.init", artigos=self._rag.total_artigos, llm=llm_client is not None)

    def analisar(self, texto: str, fontes: list[str] | None = None) -> ResultadoReasoning:
        caso_id = str(uuid.uuid4())
        log = logger.bind(caso_id=caso_id)
        log.info("reasoning.start", texto_len=len(texto))

        # Etapa 1: Classificação determinística
        tipo = classificar_tipo_processo(texto)
        log.info("reasoning.classificado", tipo=tipo.value)

        # Etapa 2: RAG — recupera normas relevantes
        chunks = self._rag.search(texto, top_k=8)
        log.info("reasoning.rag.done", chunks=len(chunks))

        normas_prompt = _formatar_normas_para_prompt(chunks)

        # Etapa 3: LLM ou stub
        if self._llm is not None:
            dados = self._chamar_llm(texto, tipo, normas_prompt, log)
            tokens = dados.pop("_tokens", 0)
        else:
            dados = self._stub_sem_llm(texto, chunks)
            tokens = 0

        # Etapa 4: Anti-alucinação
        texto_para_validar = dados.get("analise","") + " " + dados.get("conclusao","")
        validas, suspeitas = self._validator.extrair_e_validar(texto_para_validar)
        if suspeitas:
            log.warning("reasoning.hallucination", suspeitas=suspeitas)

        # Etapa 5: Construir normas estruturadas
        normas = []
        for c in chunks[:6]:
            normas.append(NormaAplicada(
                diploma=c.diploma,
                artigo=c.artigo,
                epigrase=c.epigrase,
                excerto=c.texto[:200] + "..." if len(c.texto) > 200 else c.texto,
                relevancia=min(c.score / 10.0, 1.0),
                fonte=c.fonte,
            ))

        resultado = ResultadoReasoning(
            caso_id=caso_id,
            tipo_processo=tipo,
            factos=[Facto(**f) for f in dados.get("factos", []) if isinstance(f, dict)],
            qualificacao=dados.get("qualificacao", ""),
            normas=normas,
            analise=dados.get("analise", ""),
            argumentos_acusacao=_parse_argumentos(dados.get("argumentos_acusacao", []), "acusacao"),
            argumentos_defesa=_parse_argumentos(dados.get("argumentos_defesa", []), "defesa"),
            vias_processuais=dados.get("vias_processuais", []),
            conclusao=dados.get("conclusao", ""),
            grounded=len(suspeitas) == 0,
            citacoes_suspeitas=suspeitas,
            timestamp=datetime.now(timezone.utc),
            tokens_usados=tokens,
        )

        log.info("reasoning.done", grounded=resultado.grounded, normas=len(normas))
        return resultado

    def _chamar_llm(self, texto, tipo, normas_prompt, log) -> dict:
        """Chama o LLM com o prompt estruturado."""
        prompt = _PROMPT_ANALISE.format(
            tipo_processo=tipo.value,
            normas_rag=normas_prompt,
            caso=texto,
        )
        log.info("reasoning.llm.call")
        msg = self._llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        tokens = msg.usage.input_tokens + msg.usage.output_tokens
        try:
            dados = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            dados = json.loads(m.group()) if m else {}
        dados["_tokens"] = tokens
        log.info("reasoning.llm.done", tokens=tokens)
        return dados

    def _stub_sem_llm(self, texto: str, chunks: list[Chunk]) -> dict:
        """
        Modo sem LLM — para testes e desenvolvimento.
        Produz uma resposta estruturada baseada apenas no RAG.
        Não inventa artigos. Não alucina.
        """
        normas_txt = ", ".join(f"Art. {c.artigo}.º {c.diploma}" for c in chunks[:3])
        return {
            "factos": [
                {"descricao": "Caso submetido para análise jurídica", "relevancia": "alta"},
                {"descricao": "Normas relevantes identificadas pelo motor RAG", "relevancia": "media"},
            ],
            "qualificacao": f"Caso classificado como matéria de tipo '{classificar_tipo_processo(texto).value}'. Aguarda análise LLM.",
            "analise": f"Com base nas normas recuperadas ({normas_txt}), o caso requer análise detalhada. "
                       f"Active o motor LLM para obter análise completa com citações verificadas.",
            "argumentos_acusacao": [
                {"argumento": "Argumentos da parte autora — requer LLM para análise completa.", "normas_base": []},
            ],
            "argumentos_defesa": [
                {"argumento": "Argumentos da defesa — requer LLM para análise completa.", "normas_base": []},
            ],
            "vias_processuais": ["Consulte um advogado para determinar a via processual adequada."],
            "conclusao": "Análise preliminar com base em RAG. Para análise completa, active o motor LLM.",
        }
