"""
Rotas de Workflow e Notificações do SNAJI — Fase 2.

Endpoints:
- POST /processos/{pid}/avancar-workflow  → avança com prazos automáticos
- GET  /processos/{pid}/prazos            → prazos de um processo
- GET  /notificacoes                      → alertas do utilizador
- POST /notificacoes/{id}/lida            → marcar como lida
- GET  /workflow/regras/{tipo}            → consultar regras de prazos
"""

from fastapi import APIRouter, HTTPException, Depends, Form
from pydantic import BaseModel
from typing import Optional
import structlog

from app.security.dependencias import requer_login
from app.db.utilizadores import Utilizador
from app.processes.repositorio import repositorio_processos, TipoProcesso, avancar_com_workflow
from app.workflow.motor import motor_workflow, EstadoProcesso
from app.notifications.gestor import gestor_notificacoes

router = APIRouter(tags=["Workflow & Notificações"])
logger = structlog.get_logger(__name__)


@router.post("/processos/{pid}/avancar-workflow")
async def avancar_com_prazos(
    pid: str,
    nota: str = Form(default=""),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Avança o processo para a próxima fase e gera automaticamente
    os prazos legais correctos (CPC, CPP, CT, etc.).
    """
    try:
        p = avancar_com_workflow(pid, utilizador.id, nota)
        prazos_novos = motor_workflow.calcular_prazos_fase(p.tipo, p.estado)
        alertas = motor_workflow.analisar_urgencia(p.prazos)

        logger.info("workflow.avancou", pid=pid, estado=p.estado.value, prazos=len(prazos_novos))

        return {
            "numero": p.numero,
            "estado_anterior": p.eventos[-1].estado_anterior,
            "estado_novo": p.estado.value,
            "proximo_estado": p.proximo_estado().value if p.proximo_estado() else None,
            "prazos_gerados": [
                {
                    "descricao": pr.descricao,
                    "data_limite": pr.data_limite.isoformat(),
                    "urgente": pr.urgente,
                }
                for pr in p.prazos[-len(prazos_novos):]
            ],
            "alertas": alertas,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/processos/{pid}/prazos")
async def ver_prazos(
    pid: str,
    utilizador: Utilizador = Depends(requer_login),
):
    """Lista todos os prazos de um processo com análise de urgência."""
    p = repositorio_processos.por_id(pid)
    if not p:
        raise HTTPException(status_code=404, detail="Processo não encontrado")

    alertas = motor_workflow.analisar_urgencia(p.prazos)

    return {
        "processo": p.numero,
        "estado": p.estado.value,
        "alertas": alertas,
        "prazos": [
            {
                "descricao": pr.descricao,
                "data_limite": pr.data_limite.isoformat(),
                "urgente": pr.urgente,
                "cumprido": pr.cumprido,
            }
            for pr in sorted(p.prazos, key=lambda x: x.data_limite)
        ],
    }


@router.get("/notificacoes")
async def listar_notificacoes(
    apenas_nao_lidas: bool = False,
    utilizador: Utilizador = Depends(requer_login),
):
    """Lista as notificações de prazos do utilizador."""
    notifs = gestor_notificacoes.listar(
        destinatario_id=utilizador.id,
        apenas_nao_lidas=apenas_nao_lidas,
        limite=50,
    )
    contagem = gestor_notificacoes.contar_nao_lidas(utilizador.id)

    return {
        "contagem": contagem,
        "notificacoes": [
            {
                "id": n.id,
                "processo_numero": n.processo_numero,
                "nivel": n.nivel.value,
                "titulo": n.titulo,
                "mensagem": n.mensagem,
                "criada_em": n.criada_em.isoformat(),
                "lida": n.lida,
            }
            for n in notifs
        ],
    }


@router.post("/notificacoes/{notif_id}/lida")
async def marcar_lida(
    notif_id: str,
    utilizador: Utilizador = Depends(requer_login),
):
    """Marca uma notificação como lida."""
    ok = gestor_notificacoes.marcar_lida(notif_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    return {"ok": True}


@router.get("/workflow/regras/{tipo}")
async def ver_regras_workflow(
    tipo: TipoProcesso,
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Consulta as regras de prazos legais para um tipo de processo.
    Útil para advogados e magistrados planearem a agenda processual.
    """
    from app.workflow.motor import REGRAS_PRAZOS, REGRAS_GENERICAS

    regras_tipo = REGRAS_PRAZOS.get(tipo, {})
    resultado = {}

    for fase in EstadoProcesso:
        regras = regras_tipo.get(fase, REGRAS_GENERICAS.get(fase, []))
        if regras:
            resultado[fase.value] = [
                {
                    "descricao": r.descricao,
                    "dias_uteis": r.dias_uteis,
                    "urgente_em_dias": r.urgente_em_dias,
                    "base_legal": r.base_legal,
                }
                for r in regras
            ]

    return {
        "tipo_processo": tipo.value,
        "fases_com_prazos": len(resultado),
        "regras": resultado,
    }


@router.get("/workflow/dashboard")
async def dashboard_workflow(
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Dashboard de workflow — visão agregada de todos os processos
    com prazos urgentes. Especialmente útil para magistrados.
    """
    processos = repositorio_processos.todos()
    urgentes = []
    expirados = []

    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc)

    for p in processos:
        for pr in p.prazos:
            if pr.cumprido:
                continue
            dias = (pr.data_limite - agora).days
            entrada = {
                "processo_id": p.id,
                "processo_numero": p.numero,
                "tipo": p.tipo.value,
                "estado": p.estado.value,
                "prazo_descricao": pr.descricao,
                "data_limite": pr.data_limite.isoformat(),
                "dias_restantes": dias,
            }
            if dias < 0:
                expirados.append(entrada)
            elif dias <= 7:
                urgentes.append(entrada)

    urgentes.sort(key=lambda x: x["dias_restantes"])
    expirados.sort(key=lambda x: x["dias_restantes"])

    return {
        "total_processos": len(processos),
        "prazos_expirados": len(expirados),
        "prazos_urgentes_7dias": len(urgentes),
        "expirados": expirados[:10],
        "urgentes": urgentes[:10],
    }
