"""
Motor de Audiências do SNAJI — Fase 3.

Implementa o processo judicial português real:

MODELO PROCESSUAL:
─────────────────
Qualquer pessoa pode iniciar (vítima, lesado, advogado, MP).
O processo tem fases ordenadas com loop de contraditório.
Cada fase tem prazo e participantes definidos.
As provas (documentos, etc.) são apresentadas em momentos próprios.
O juiz só decide quando TODAS as partes tiveram oportunidade de falar.

FASES DA AUDIÊNCIA:
───────────────────
1. ABERTURA          — Juiz abre, identifica partes, define objecto
2. ACUSAÇÃO/PEDIDO   — Quem iniciou apresenta os factos e pedidos
3. DEFESA            — A parte contrária responde e contesta
4. RÉPLICA           — Quem acusou pode responder à defesa (1 vez)
5. PRODUÇÃO DE PROVA — Documentos, perícias, testemunhas de ambos os lados
6. PERGUNTAS DO JUIZ — Juiz esclarece dúvidas (loop até estar satisfeito)
7. ALEGAÇÕES FINAIS  — Cada parte resume o seu caso (última palavra)
8. DELIBERAÇÃO       — Juiz delibera (internamente)
9. DECISÃO           — Sentença/acórdão fundamentado

O loop contraditório acontece nas fases 3→4→5→6 quantas vezes
o juiz considerar necessário para esclarecimento.
"""

from __future__ import annotations
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
import structlog

from app.audiencias.modelos import (
    Audiencia, TipoAudiencia, EstadoAudiencia, PapelAgente,
    TipoIntervencao, Intervencao, DecisaoFinal, ConfiguracaoAgente
)
from app.agents.agentes import (
    AgenteFabrica, gerar_argumento_stub, extrair_normas_citadas,
    INSTRUCOES_AGENTES
)
from app.rag.motor import RAGJuridico, ValidadorCitacoes

logger = structlog.get_logger(__name__)


class FaseAudiencia(str, Enum):
    """Fases reais de uma audiência portuguesa."""
    ABERTURA         = "abertura"
    ACUSACAO_PEDIDO  = "acusacao_pedido"
    DEFESA           = "defesa"
    REPLICA          = "replica"
    PROVA            = "prova"
    PERGUNTAS_JUIZ   = "perguntas_juiz"
    ALEGACOES_FINAIS = "alegacoes_finais"
    DELIBERACAO      = "deliberacao"
    DECISAO          = "decisao"


# Ordem legal das fases (não pode saltar)
ORDEM_FASES_AUDIENCIA = [
    FaseAudiencia.ABERTURA,
    FaseAudiencia.ACUSACAO_PEDIDO,
    FaseAudiencia.DEFESA,
    FaseAudiencia.REPLICA,
    FaseAudiencia.PROVA,
    FaseAudiencia.PERGUNTAS_JUIZ,
    FaseAudiencia.ALEGACOES_FINAIS,
    FaseAudiencia.DELIBERACAO,
    FaseAudiencia.DECISAO,
]

# Quais papéis podem falar em cada fase
PAPEIS_POR_FASE: dict[FaseAudiencia, list[PapelAgente]] = {
    FaseAudiencia.ABERTURA:         [PapelAgente.JUIZ],
    FaseAudiencia.ACUSACAO_PEDIDO:  [PapelAgente.ACUSACAO, PapelAgente.ASSISTENTE],
    FaseAudiencia.DEFESA:           [PapelAgente.DEFESA],
    FaseAudiencia.REPLICA:          [PapelAgente.ACUSACAO],
    FaseAudiencia.PROVA:            [PapelAgente.ACUSACAO, PapelAgente.DEFESA, PapelAgente.PERITO],
    FaseAudiencia.PERGUNTAS_JUIZ:   [PapelAgente.JUIZ, PapelAgente.ACUSACAO, PapelAgente.DEFESA, PapelAgente.PERITO],
    FaseAudiencia.ALEGACOES_FINAIS: [PapelAgente.ACUSACAO, PapelAgente.DEFESA, PapelAgente.ASSISTENTE],
    FaseAudiencia.DELIBERACAO:      [PapelAgente.JUIZ],
    FaseAudiencia.DECISAO:          [PapelAgente.JUIZ],
}

# Descrição das fases para o utilizador
DESCRICAO_FASES: dict[FaseAudiencia, str] = {
    FaseAudiencia.ABERTURA:         "O juiz abre a audiência, identifica as partes e define o objecto do litígio.",
    FaseAudiencia.ACUSACAO_PEDIDO:  "A parte que iniciou o processo apresenta os factos e os seus pedidos.",
    FaseAudiencia.DEFESA:           "A parte contrária responde, contesta os factos e apresenta a sua versão.",
    FaseAudiencia.REPLICA:          "A parte autora pode responder aos argumentos da defesa (uma única vez).",
    FaseAudiencia.PROVA:            "Ambas as partes apresentam provas — documentos, perícias, testemunhos.",
    FaseAudiencia.PERGUNTAS_JUIZ:   "O juiz esclarece dúvidas. Pode dirigir questões a qualquer parte ou perito.",
    FaseAudiencia.ALEGACOES_FINAIS: "Cada parte faz o seu resumo final. É a última palavra antes da decisão.",
    FaseAudiencia.DELIBERACAO:      "O juiz delibera internamente sobre os factos provados e o direito aplicável.",
    FaseAudiencia.DECISAO:          "O juiz profere a sentença fundamentada nos factos e nas normas aplicadas.",
}


@dataclass
class Prova:
    """Uma prova apresentada por uma das partes."""
    id: str
    audiencia_id: str
    apresentada_por: PapelAgente
    tipo: str           # "documento" | "pericia" | "testemunho" | "video" | "imagem"
    descricao: str
    conteudo_texto: str  # texto extraído ou descrição
    nome_ficheiro: Optional[str]
    timestamp: datetime
    hash_integridade: str

    @classmethod
    def criar(
        cls,
        audiencia_id: str,
        apresentada_por: PapelAgente,
        tipo: str,
        descricao: str,
        conteudo_texto: str,
        nome_ficheiro: Optional[str] = None,
    ) -> "Prova":
        pid = str(uuid.uuid4())
        ts = datetime.now(timezone.utc)
        h = hashlib.sha256(f"{pid}|{conteudo_texto}".encode()).hexdigest()
        return cls(
            id=pid, audiencia_id=audiencia_id,
            apresentada_por=apresentada_por, tipo=tipo,
            descricao=descricao, conteudo_texto=conteudo_texto,
            nome_ficheiro=nome_ficheiro, timestamp=ts, hash_integridade=h,
        )


@dataclass
class AudienciaCompleta:
    """
    Audiência completa com fases, provas e loop contraditório.
    Esta é a estrutura central da Fase 3.
    """
    id: str
    processo_id: Optional[str]
    tipo: TipoAudiencia
    descricao_caso: str
    tipo_processo: str
    estado: EstadoAudiencia
    fase_actual: FaseAudiencia
    criada_por: str            # user_id de quem criou
    papel_criador: PapelAgente # papel processual de quem criou (vítima, advogado, etc.)
    criada_em: datetime
    iniciada_em: Optional[datetime]
    concluida_em: Optional[datetime]
    participantes: list[ConfiguracaoAgente]
    intervencoes: list[Intervencao]
    provas: list[Prova]
    decisao: Optional[DecisaoFinal]
    num_loops_contraditorio: int       # quantas vezes o loop já ocorreu
    max_loops_contraditorio: int       # máximo permitido pelo juiz
    aguarda_intervencao_de: Optional[PapelAgente]  # quem deve falar a seguir
    notas_juiz: list[str]              # notas internas do juiz

    def papeis_activos(self) -> list[PapelAgente]:
        return [p.papel for p in self.participantes if p.activo]

    def pode_apresentar_prova(self, papel: PapelAgente) -> bool:
        return (
            self.fase_actual in (FaseAudiencia.PROVA, FaseAudiencia.PERGUNTAS_JUIZ)
            and papel in self.papeis_activos()
        )

    def provas_de(self, papel: PapelAgente) -> list[Prova]:
        return [p for p in self.provas if p.apresentada_por == papel]

    def resumo_provas(self) -> str:
        if not self.provas:
            return "Nenhuma prova apresentada até ao momento."
        linhas = []
        for p in self.provas:
            linhas.append(f"[PROVA — {p.apresentada_por.value.upper()}] {p.tipo}: {p.descricao}")
        return "\n".join(linhas)

    def contexto_completo(self) -> str:
        """Gera contexto completo da audiência para os agentes."""
        partes = []
        partes.append(f"CASO: {self.descricao_caso}")
        partes.append(f"TIPO: {self.tipo_processo}")
        partes.append(f"FASE ACTUAL: {DESCRICAO_FASES.get(self.fase_actual, '')}")
        if self.provas:
            partes.append(f"\nPROVAS APRESENTADAS:\n{self.resumo_provas()}")
        if self.intervencoes:
            ultimas = self.intervencoes[-8:]
            partes.append("\nÚLTIMAS INTERVENÇÕES:")
            for iv in ultimas:
                partes.append(f"[{iv.papel.value.upper()}] {iv.conteudo[:250]}")
        return "\n\n".join(partes)


class MotorAudiencias:
    """
    Gere o ciclo de vida completo de uma audiência.

    Responsabilidades:
    - Criar audiências com participantes correctos
    - Gerir transições entre fases
    - Processar intervenções de cada parte
    - Processar provas (documentos, etc.)
    - Decidir quando o loop contraditório deve continuar ou terminar
    - Gerar a decisão final fundamentada
    """

    def __init__(self, llm_client=None):
        self._audiencias: dict[str, AudienciaCompleta] = {}
        self._llm = llm_client
        self._rag = RAGJuridico()
        self._validator = ValidadorCitacoes()
        logger.info("motor.audiencias.init", llm=llm_client is not None)

    # ── Criação ─────────────────────────────────────────────────────────────

    def criar_audiencia(
        self,
        descricao_caso: str,
        tipo_processo: str,
        tipo_audiencia: TipoAudiencia,
        criado_por: str,
        papel_criador: PapelAgente,
        processo_id: Optional[str] = None,
        com_perito: bool = False,
        max_loops: int = 3,
    ) -> AudienciaCompleta:
        """
        Cria uma audiência. Qualquer papel pode iniciar —
        vítima, lesado, arguido, advogado, MP.
        """
        aid = str(uuid.uuid4())

        # Configura participantes conforme o tipo
        if tipo_audiencia in (TipoAudiencia.JULGAMENTO, TipoAudiencia.AUDIENCIA_PRELIMINAR):
            participantes = AgenteFabrica.criar_agentes_julgamento(
                tipo_processo, com_perito=com_perito
            )
        else:
            participantes = AgenteFabrica.criar_agentes_contraditorio(tipo_processo)
            # Adiciona juiz se for simulação completa
            participantes.insert(0, ConfiguracaoAgente(
                papel=PapelAgente.JUIZ, nome="Juiz Presidente",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.JUIZ],
            ))

        a = AudienciaCompleta(
            id=aid, processo_id=processo_id,
            tipo=tipo_audiencia, descricao_caso=descricao_caso,
            tipo_processo=tipo_processo,
            estado=EstadoAudiencia.PENDENTE,
            fase_actual=FaseAudiencia.ABERTURA,
            criada_por=criado_por, papel_criador=papel_criador,
            criada_em=datetime.now(timezone.utc),
            iniciada_em=None, concluida_em=None,
            participantes=participantes,
            intervencoes=[], provas=[],
            decisao=None,
            num_loops_contraditorio=0,
            max_loops_contraditorio=max_loops,
            aguarda_intervencao_de=PapelAgente.JUIZ,
            notas_juiz=[],
        )
        self._audiencias[aid] = a
        logger.info("audiencia.criada", id=aid, tipo=tipo_audiencia.value, papel_criador=papel_criador.value)
        return a

    # ── Intervenções ─────────────────────────────────────────────────────────

    def processar_intervencao(
        self,
        audiencia_id: str,
        papel: PapelAgente,
        conteudo: str,
        tipo: TipoIntervencao = TipoIntervencao.ALEGACAO,
    ) -> tuple[Intervencao, Optional[str]]:
        """
        Processa uma intervenção de um participante.
        Retorna a intervenção registada e uma mensagem de orientação para o próximo passo.
        """
        a = self._get_audiencia(audiencia_id)

        # Valida que este papel pode falar agora
        papeis_permitidos = PAPEIS_POR_FASE.get(a.fase_actual, [])
        if papel not in papeis_permitidos:
            raise ValueError(
                f"O papel '{papel.value}' não pode intervir na fase '{a.fase_actual.value}'. "
                f"Papéis permitidos nesta fase: {[p.value for p in papeis_permitidos]}"
            )

        # Extrai normas citadas
        normas = extrair_normas_citadas(conteudo)

        # Cria intervenção com hash de integridade
        iv = Intervencao.criar(
            audiencia_id=audiencia_id,
            ronda=a.num_loops_contraditorio,
            papel=papel,
            tipo=tipo,
            conteudo=conteudo,
            normas_citadas=normas,
        )
        a.intervencoes.append(iv)

        # Inicia a audiência se ainda estava pendente
        if a.estado == EstadoAudiencia.PENDENTE:
            a.estado = EstadoAudiencia.EM_CURSO
            a.iniciada_em = datetime.now(timezone.utc)

        # Determina próximo passo
        orientacao = self._determinar_proximo_passo(a, papel)
        logger.info("intervencao.processada", audiencia_id=audiencia_id, papel=papel.value, fase=a.fase_actual.value)

        return iv, orientacao

    def _determinar_proximo_passo(self, a: AudienciaCompleta, ultimo_papel: PapelAgente) -> str:
        """
        Decide quem deve falar a seguir e se a fase deve avançar.
        Implementa o loop contraditório.
        """
        fase = a.fase_actual

        if fase == FaseAudiencia.ABERTURA:
            a.fase_actual = FaseAudiencia.ACUSACAO_PEDIDO
            a.aguarda_intervencao_de = PapelAgente.ACUSACAO
            return "O juiz abriu a audiência. A acusação/parte autora pode agora apresentar os seus factos e pedidos."

        if fase == FaseAudiencia.ACUSACAO_PEDIDO:
            a.fase_actual = FaseAudiencia.DEFESA
            a.aguarda_intervencao_de = PapelAgente.DEFESA
            return "A acusação apresentou o seu caso. A defesa pode agora responder."

        if fase == FaseAudiencia.DEFESA:
            a.fase_actual = FaseAudiencia.REPLICA
            a.aguarda_intervencao_de = PapelAgente.ACUSACAO
            return "A defesa respondeu. A acusação pode apresentar réplica (uma vez) antes da produção de prova."

        if fase == FaseAudiencia.REPLICA:
            a.fase_actual = FaseAudiencia.PROVA
            a.aguarda_intervencao_de = None  # ambas as partes podem apresentar provas
            return "Fase de produção de prova. Qualquer das partes pode apresentar documentos, perícias ou testemunhos."

        if fase == FaseAudiencia.PROVA:
            a.fase_actual = FaseAudiencia.PERGUNTAS_JUIZ
            a.aguarda_intervencao_de = PapelAgente.JUIZ
            return "O juiz pode agora colocar questões a qualquer das partes para esclarecimento."

        if fase == FaseAudiencia.PERGUNTAS_JUIZ:
            # O juiz decide se quer mais um loop ou avança
            if a.num_loops_contraditorio < a.max_loops_contraditorio and ultimo_papel == PapelAgente.JUIZ:
                a.num_loops_contraditorio += 1
                a.fase_actual = FaseAudiencia.DEFESA  # volta ao contraditório
                a.aguarda_intervencao_de = PapelAgente.DEFESA
                return f"O juiz solicitou mais esclarecimentos (loop {a.num_loops_contraditorio}/{a.max_loops_contraditorio}). A defesa pode complementar os seus argumentos."
            else:
                a.fase_actual = FaseAudiencia.ALEGACOES_FINAIS
                a.aguarda_intervencao_de = PapelAgente.ACUSACAO
                return "O juiz está satisfeito com os esclarecimentos. Passamos às alegações finais. A acusação fala primeiro."

        if fase == FaseAudiencia.ALEGACOES_FINAIS:
            if ultimo_papel == PapelAgente.ACUSACAO:
                a.aguarda_intervencao_de = PapelAgente.DEFESA
                return "A acusação fez as suas alegações finais. A defesa tem agora a última palavra."
            else:
                a.fase_actual = FaseAudiencia.DELIBERACAO
                a.aguarda_intervencao_de = PapelAgente.JUIZ
                return "Todas as partes falaram. O juiz vai deliberar. Aguarde a decisão."

        if fase == FaseAudiencia.DELIBERACAO:
            a.fase_actual = FaseAudiencia.DECISAO
            a.aguarda_intervencao_de = PapelAgente.JUIZ
            return "O juiz está pronto para proferir a decisão."

        return "Audiência em curso."

    # ── Geração automática de intervenções (modo IA) ─────────────────────────

    def gerar_intervencao_automatica(
        self,
        audiencia_id: str,
        papel: PapelAgente,
    ) -> Intervencao:
        """
        Gera automaticamente uma intervenção para um papel.
        Usa LLM se disponível, stub caso contrário.
        """
        a = self._get_audiencia(audiencia_id)
        contexto = a.contexto_completo()

        if self._llm is not None:
            conteudo = self._gerar_com_llm(a, papel, contexto)
        else:
            conteudo = gerar_argumento_stub(a.tipo_processo, papel, a.num_loops_contraditorio)

        iv, _ = self.processar_intervencao(audiencia_id, papel, conteudo)
        return iv

    def _gerar_com_llm(self, a: AudienciaCompleta, papel: PapelAgente, contexto: str) -> str:
        """Chama o LLM com o papel e contexto correctos."""
        from app.agents.agentes import INSTRUCOES_AGENTES
        normas_rag = self._rag.search(a.descricao_caso, top_k=5)
        normas_txt = "\n".join(
            f"• Art. {c.artigo}.º {c.diploma} — {c.texto[:150]}"
            for c in normas_rag
        )
        prompt = f"""CONTEXTO DA AUDIÊNCIA:
{contexto}

NORMAS RELEVANTES DO CORPUS JURÍDICO PORTUGUÊS:
{normas_txt}

FASE ACTUAL: {DESCRICAO_FASES.get(a.fase_actual, a.fase_actual.value)}

Produz a tua intervenção como {papel.value}. Sê conciso (máx. 300 palavras).
Cita sempre os artigos exactos das normas fornecidas acima."""

        msg = self._llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=INSTRUCOES_AGENTES.get(papel, ""),
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    # ── Provas ───────────────────────────────────────────────────────────────

    def apresentar_prova(
        self,
        audiencia_id: str,
        papel: PapelAgente,
        tipo_prova: str,
        descricao: str,
        conteudo_texto: str,
        nome_ficheiro: Optional[str] = None,
    ) -> Prova:
        """
        Regista uma prova apresentada por uma das partes.
        Qualquer parte pode apresentar provas na fase de prova
        ou nas perguntas do juiz.
        """
        a = self._get_audiencia(audiencia_id)

        if not a.pode_apresentar_prova(papel):
            raise ValueError(
                f"Provas só podem ser apresentadas nas fases de Produção de Prova "
                f"ou Perguntas do Juiz. Fase actual: {a.fase_actual.value}"
            )

        prova = Prova.criar(
            audiencia_id=audiencia_id,
            apresentada_por=papel,
            tipo=tipo_prova,
            descricao=descricao,
            conteudo_texto=conteudo_texto,
            nome_ficheiro=nome_ficheiro,
        )
        a.provas.append(prova)

        # Regista a apresentação da prova como intervenção
        iv = Intervencao.criar(
            audiencia_id=audiencia_id,
            ronda=a.num_loops_contraditorio,
            papel=papel,
            tipo=TipoIntervencao.PROVA,
            conteudo=f"[PROVA APRESENTADA] {tipo_prova}: {descricao}",
            normas_citadas=[],
        )
        a.intervencoes.append(iv)

        logger.info("prova.apresentada", audiencia_id=audiencia_id, papel=papel.value, tipo=tipo_prova)
        return prova

    # ── Decisão final ────────────────────────────────────────────────────────

    def proferir_decisao(self, audiencia_id: str) -> DecisaoFinal:
        """
        O juiz profere a decisão final.
        Analisa todas as intervenções e provas e produz sentença fundamentada.
        """
        a = self._get_audiencia(audiencia_id)

        if a.fase_actual != FaseAudiencia.DECISAO:
            raise ValueError(f"A decisão só pode ser proferida na fase de Decisão. Fase actual: {a.fase_actual.value}")

        if self._llm is not None:
            decisao = self._gerar_decisao_llm(a)
        else:
            decisao = self._gerar_decisao_stub(a)

        a.decisao = decisao
        a.estado = EstadoAudiencia.CONCLUIDA
        a.concluida_em = datetime.now(timezone.utc)
        a.fase_actual = FaseAudiencia.DECISAO

        # Regista a decisão como intervenção
        iv = Intervencao.criar(
            audiencia_id=audiencia_id,
            ronda=a.num_loops_contraditorio,
            papel=PapelAgente.JUIZ,
            tipo=TipoIntervencao.DECISAO_FINAL,
            conteudo=decisao.dispositivo,
            normas_citadas=decisao.normas_aplicadas,
        )
        a.intervencoes.append(iv)

        logger.info("decisao.proferida", audiencia_id=audiencia_id, estado="concluida")
        return decisao

    def _gerar_decisao_llm(self, a: AudienciaCompleta) -> DecisaoFinal:
        normas_rag = self._rag.search(a.descricao_caso, top_k=6)
        normas_txt = "\n".join(f"• Art. {c.artigo}.º {c.diploma} — {c.texto[:200]}" for c in normas_rag)
        prompt = f"""AUDIÊNCIA COMPLETA:
{a.contexto_completo()}

PROVAS APRESENTADAS:
{a.resumo_provas()}

NORMAS APLICÁVEIS:
{normas_txt}

Profere a SENTENÇA final. Responde em JSON:
{{
  "sumario": "sumário da decisão em 1 frase",
  "fundamentacao": "fundamentação jurídica completa com citações",
  "normas_aplicadas": ["CRP-53", "CT-351"],
  "dispositivo": "texto exacto do dispositivo (condenatório/absolutório/procedente/improcedente)",
  "recursos_possiveis": ["recurso de apelação", "revista"]
}}"""
        import json, re as _re
        msg = self._llm.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=1000,
            system=INSTRUCOES_AGENTES[PapelAgente.JUIZ],
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text
        try:
            dados = json.loads(raw)
        except Exception:
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            dados = json.loads(m.group()) if m else {}
        return DecisaoFinal(
            sumario=dados.get("sumario", ""),
            fundamentacao=dados.get("fundamentacao", ""),
            normas_aplicadas=dados.get("normas_aplicadas", []),
            dispositivo=dados.get("dispositivo", ""),
            recursos_possiveis=dados.get("recursos_possiveis", []),
        )

    def _gerar_decisao_stub(self, a: AudienciaCompleta) -> DecisaoFinal:
        """Decisão stub quando LLM não está disponível."""
        normas_rag = self._rag.search(a.descricao_caso, top_k=3)
        normas_citadas = [f"{c.diploma}-{c.artigo}" for c in normas_rag]
        tipo = a.tipo_processo

        dispositivos = {
            "laboral": "O tribunal julga a acção PROCEDENTE. O despedimento é declarado ilícito por ausência de justa causa (Art. 351.º CT). A entidade empregadora é condenada a pagar indemnização nos termos do Art. 391.º CT. [NOTA: Decisão gerada em modo stub — activar LLM para análise real dos factos provados]",
            "penal": "O tribunal, após análise da prova produzida, delibera sobre a culpa do arguido. A decisão fundamenta-se nos factos provados e nas normas do Código Penal. [NOTA: Decisão gerada em modo stub — activar LLM para análise real]",
            "civil": "O tribunal julga a acção conforme os factos provados e o direito aplicável, nos termos dos artigos invocados do Código Civil e do Código de Processo Civil. [NOTA: Decisão gerada em modo stub]",
        }

        return DecisaoFinal(
            sumario=f"Decisão na audiência de {tipo} — modo demonstração",
            fundamentacao=(
                f"Com base nas intervenções produzidas ({len(a.intervencoes)} no total), "
                f"nas {len(a.provas)} prova(s) apresentada(s), e nas normas jurídicas identificadas "
                f"pelo motor RAG ({len(normas_rag)} normas relevantes), o tribunal profere a seguinte decisão. "
                f"[Para fundamentação completa, activar motor LLM]"
            ),
            normas_aplicadas=normas_citadas,
            dispositivo=dispositivos.get(tipo, dispositivos["civil"]),
            recursos_possiveis=["Recurso de apelação (Art. 638.º CPC)", "Recurso de revista (Art. 671.º CPC)"],
        )

    # ── Consultas ────────────────────────────────────────────────────────────

    def obter_audiencia(self, audiencia_id: str) -> AudienciaCompleta:
        return self._get_audiencia(audiencia_id)

    def listar_audiencias(self, criado_por: Optional[str] = None) -> list[AudienciaCompleta]:
        todas = list(self._audiencias.values())
        if criado_por:
            todas = [a for a in todas if a.criado_por == criado_por]
        return sorted(todas, key=lambda a: a.criada_em, reverse=True)

    def _get_audiencia(self, aid: str) -> AudienciaCompleta:
        a = self._audiencias.get(aid)
        if not a:
            raise ValueError(f"Audiência {aid} não encontrada")
        return a


# Instância partilhada
motor_audiencias = MotorAudiencias(llm_client=None)
