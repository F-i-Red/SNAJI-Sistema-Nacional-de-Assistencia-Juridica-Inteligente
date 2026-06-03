"""
Repositório de Processos Jurídicos do SNAJI.

Gestiona o ciclo de vida completo de um processo:
  Apresentação → Citação → Contestação → Instrução → Julgamento → Sentença → [Recurso]

Desenvolvimento: memória.
Produção: substituir por PostgreSQL (a interface pública não muda).
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class TipoProcesso(str, Enum):
    LABORAL        = "laboral"
    PENAL          = "penal"
    CIVIL          = "civil"
    ADMINISTRATIVO = "administrativo"
    FAMILIA        = "familia"
    CONSUMO        = "consumo"
    DADOS_PESSOAIS = "dados_pessoais"


class EstadoProcesso(str, Enum):
    APRESENTACAO = "Apresentação"
    CITACAO      = "Citação"
    CONTESTACAO  = "Contestação"
    INSTRUCAO    = "Instrução"
    JULGAMENTO   = "Julgamento"
    SENTENCA     = "Sentença"
    RECURSO      = "Recurso"
    CONCLUIDO    = "Concluído"
    ARQUIVADO    = "Arquivado"


# Ordem legal das fases (não pode saltar fases)
ORDEM_FASES = [
    EstadoProcesso.APRESENTACAO,
    EstadoProcesso.CITACAO,
    EstadoProcesso.CONTESTACAO,
    EstadoProcesso.INSTRUCAO,
    EstadoProcesso.JULGAMENTO,
    EstadoProcesso.SENTENCA,
    EstadoProcesso.RECURSO,
    EstadoProcesso.CONCLUIDO,
]


@dataclass
class Parte:
    nome: str
    papel: str          # "autor" | "réu" | "arguido" | "assistente"
    email: Optional[str] = None
    nif: Optional[str] = None


@dataclass
class EventoProcesso:
    """Registo imutável de cada transição ou acção no processo."""
    id: str
    timestamp: datetime
    tipo: str           # "criacao" | "transicao" | "documento" | "nota"
    descricao: str
    utilizador_id: str
    estado_anterior: Optional[str] = None
    estado_novo: Optional[str] = None


@dataclass
class Prazo:
    descricao: str
    data_limite: datetime
    urgente: bool = False
    cumprido: bool = False


@dataclass
class Processo:
    id: str
    numero: str
    tipo: TipoProcesso
    descricao: str
    estado: EstadoProcesso
    partes: list[Parte]
    criado_por: str         # utilizador_id
    criado_em: datetime
    atualizado_em: datetime
    eventos: list[EventoProcesso] = field(default_factory=list)
    prazos: list[Prazo] = field(default_factory=list)
    caso_id_analise: Optional[str] = None   # ligação à análise RAG
    notas: list[str] = field(default_factory=list)
    valor_causa: Optional[float] = None
    tribunal: str = "Tribunal Judicial"
    comarca: str = "Lisboa"

    def fase_index(self) -> int:
        try:
            return ORDEM_FASES.index(self.estado)
        except ValueError:
            return -1

    def pode_avancar(self) -> bool:
        return self.estado not in (EstadoProcesso.CONCLUIDO, EstadoProcesso.ARQUIVADO)

    def proximo_estado(self) -> Optional[EstadoProcesso]:
        idx = self.fase_index()
        if idx < 0 or idx >= len(ORDEM_FASES) - 1:
            return None
        return ORDEM_FASES[idx + 1]


def _gerar_numero(tipo: TipoProcesso) -> str:
    """Gera número de processo no formato português: ANO/NÚMERO-TIPO"""
    ano = datetime.now().year
    num = str(uuid.uuid4().int)[:4]
    sigla = {"laboral":"L","penal":"P","civil":"C","administrativo":"A","familia":"F","consumo":"C","dados_pessoais":"D"}.get(tipo.value, "X")
    return f"{ano}/{num}-{sigla}"


class RepositorioProcessos:
    """
    CRUD de processos com histórico imutável de eventos.
    """

    def __init__(self):
        self._processos: dict[str, Processo] = {}
        self._por_utilizador: dict[str, list[str]] = {}  # user_id → [processo_id]
        self._seed_demo()

    def _seed_demo(self) -> None:
        """Cria processos de demonstração realistas."""
        agora = datetime.now(timezone.utc)
        demos = [
            {
                "tipo": TipoProcesso.LABORAL,
                "descricao": "Despedimento sem justa causa — 8 anos de serviço",
                "estado": EstadoProcesso.INSTRUCAO,
                "partes": [Parte("Ana Costa","autor"), Parte("Empresa XYZ Lda","réu")],
                "criado_por": "cidadao-demo",
                "dias_atras": 45,
                "prazos": [("Submissão de documentos adicionais", 5, True), ("Audiência preliminar", 20, False)],
            },
            {
                "tipo": TipoProcesso.CIVIL,
                "descricao": "Incumprimento contratual — arrendamento",
                "estado": EstadoProcesso.CITACAO,
                "partes": [Parte("Ana Costa","autor"), Parte("João Senhorio","réu")],
                "criado_por": "cidadao-demo",
                "dias_atras": 120,
                "prazos": [("Prazo de contestação do réu", 15, False)],
            },
            {
                "tipo": TipoProcesso.PENAL,
                "descricao": "Corrupção — funcionário público",
                "estado": EstadoProcesso.JULGAMENTO,
                "partes": [Parte("Ministério Público","acusação"), Parte("Arguido A","arguido")],
                "criado_por": "magistrado-demo",
                "dias_atras": 180,
                "prazos": [("Audiência de julgamento", 2, True)],
            },
            {
                "tipo": TipoProcesso.LABORAL,
                "descricao": "Despedimento colectivo — 23 trabalhadores",
                "estado": EstadoProcesso.CONTESTACAO,
                "partes": [Parte("Sindicato dos Trabalhadores","autor"), Parte("Fábrica Beta SA","réu")],
                "criado_por": "advogado-demo",
                "dias_atras": 60,
                "prazos": [("Resposta ao Ministério Público", 3, True), ("Audiência de partes", 25, False)],
            },
        ]
        for d in demos:
            pid = str(uuid.uuid4())
            agora_menos = agora - timedelta(days=d["dias_atras"])
            p = Processo(
                id=pid,
                numero=_gerar_numero(d["tipo"]),
                tipo=d["tipo"],
                descricao=d["descricao"],
                estado=d["estado"],
                partes=d["partes"],
                criado_por=d["criado_por"],
                criado_em=agora_menos,
                atualizado_em=agora - timedelta(days=1),
                tribunal="Tribunal Judicial de Lisboa",
                comarca="Lisboa",
            )
            for desc, dias, urgente in d.get("prazos", []):
                p.prazos.append(Prazo(desc, agora + timedelta(days=dias), urgente))
            p.eventos.append(EventoProcesso(
                id=str(uuid.uuid4()),
                timestamp=agora_menos,
                tipo="criacao",
                descricao="Processo criado",
                utilizador_id=d["criado_por"],
                estado_novo=d["estado"].value,
            ))
            self._processos[pid] = p
            uid = d["criado_por"]
            self._por_utilizador.setdefault(uid, []).append(pid)

    # ── CRUD ────────────────────────────────────────────────────────────────

    def criar(
        self,
        tipo: TipoProcesso,
        descricao: str,
        partes: list[Parte],
        criado_por: str,
        caso_id_analise: Optional[str] = None,
        valor_causa: Optional[float] = None,
        tribunal: str = "Tribunal Judicial",
        comarca: str = "Lisboa",
    ) -> Processo:
        pid = str(uuid.uuid4())
        agora = datetime.now(timezone.utc)
        p = Processo(
            id=pid,
            numero=_gerar_numero(tipo),
            tipo=tipo,
            descricao=descricao,
            estado=EstadoProcesso.APRESENTACAO,
            partes=partes,
            criado_por=criado_por,
            criado_em=agora,
            atualizado_em=agora,
            caso_id_analise=caso_id_analise,
            valor_causa=valor_causa,
            tribunal=tribunal,
            comarca=comarca,
        )
        p.eventos.append(EventoProcesso(
            id=str(uuid.uuid4()),
            timestamp=agora,
            tipo="criacao",
            descricao=f"Processo criado: {descricao}",
            utilizador_id=criado_por,
            estado_novo=EstadoProcesso.APRESENTACAO.value,
        ))
        self._processos[pid] = p
        self._por_utilizador.setdefault(criado_por, []).append(pid)
        logger.info("processo.criado", id=pid, numero=p.numero, tipo=tipo.value)
        return p

    def por_id(self, pid: str) -> Optional[Processo]:
        return self._processos.get(pid)

    def por_utilizador(self, uid: str) -> list[Processo]:
        ids = self._por_utilizador.get(uid, [])
        # Todos os processos demo são visíveis a todos (para demonstração)
        todos = list(self._processos.values())
        return sorted(todos, key=lambda p: p.atualizado_em, reverse=True)

    def todos(self) -> list[Processo]:
        return sorted(self._processos.values(), key=lambda p: p.atualizado_em, reverse=True)

    def avancar_estado(self, pid: str, utilizador_id: str, nota: str = "") -> Processo:
        """Avança o processo para a próxima fase processual."""
        p = self._processos.get(pid)
        if not p:
            raise ValueError(f"Processo {pid} não encontrado")
        if not p.pode_avancar():
            raise ValueError(f"Processo {p.numero} já está concluído ou arquivado")
        proximo = p.proximo_estado()
        if not proximo:
            raise ValueError("Não há próxima fase para este processo")

        estado_anterior = p.estado
        p.estado = proximo
        p.atualizado_em = datetime.now(timezone.utc)
        p.eventos.append(EventoProcesso(
            id=str(uuid.uuid4()),
            timestamp=p.atualizado_em,
            tipo="transicao",
            descricao=nota or f"Transição para {proximo.value}",
            utilizador_id=utilizador_id,
            estado_anterior=estado_anterior.value,
            estado_novo=proximo.value,
        ))
        logger.info("processo.avancou", id=pid, de=estado_anterior.value, para=proximo.value)
        return p

    def adicionar_nota(self, pid: str, nota: str, utilizador_id: str) -> Processo:
        p = self._processos.get(pid)
        if not p:
            raise ValueError(f"Processo {pid} não encontrado")
        p.notas.append(nota)
        p.atualizado_em = datetime.now(timezone.utc)
        p.eventos.append(EventoProcesso(
            id=str(uuid.uuid4()),
            timestamp=p.atualizado_em,
            tipo="nota",
            descricao=nota,
            utilizador_id=utilizador_id,
        ))
        return p


# Instância partilhada
repositorio_processos = RepositorioProcessos()


# ── Integração com o motor de workflow ───────────────────────────────────────
# Importação lazy para evitar ciclos

def avancar_com_workflow(pid: str, utilizador_id: str, nota: str = "") -> "Processo":
    """
    Avança o processo e gera automaticamente os prazos legais da nova fase.
    Usa o motor de workflow para calcular prazos correctos por tipo de processo.
    """
    from app.workflow.motor import motor_workflow
    from app.notifications.gestor import gestor_notificacoes

    p = repositorio_processos.por_id(pid)
    if not p:
        raise ValueError(f"Processo {pid} não encontrado")

    # Valida a transição
    proximo = p.proximo_estado()
    if not proximo:
        raise ValueError("Não há próxima fase")

    valido, motivo = motor_workflow.validar_transicao(p.estado, proximo)
    if not valido:
        raise ValueError(motivo)

    # Avança o estado
    p = repositorio_processos.avancar_estado(pid, utilizador_id, nota)

    # Gera prazos legais da nova fase
    novos_prazos = motor_workflow.calcular_prazos_fase(p.tipo, p.estado)
    p.prazos.extend(novos_prazos)

    # Gera notificações para os prazos urgentes
    gestor_notificacoes.gerar_alertas_processo(
        processo_id=p.id,
        processo_numero=p.numero,
        prazos=novos_prazos,
    )

    return p
