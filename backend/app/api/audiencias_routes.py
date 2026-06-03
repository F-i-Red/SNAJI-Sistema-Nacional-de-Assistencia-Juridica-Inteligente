"""
Rotas das Audiências do SNAJI — Fase 3.

API completa para gestão de audiências judiciais:

POST /audiencias                           → criar audiência
GET  /audiencias                           → listar audiências do utilizador
GET  /audiencias/{id}                      → detalhe completo
POST /audiencias/{id}/intervencao          → submeter intervenção (humana)
POST /audiencias/{id}/intervencao-ia       → gerar intervenção automática (IA)
POST /audiencias/{id}/prova                → apresentar prova
POST /audiencias/{id}/decidir              → juiz profere decisão
GET  /audiencias/{id}/fases                → estado das fases e quem deve falar
POST /audiencias/{id}/avancar-fase         → juiz avança para próxima fase
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import structlog

from app.security.dependencias import requer_login
from app.db.utilizadores import Utilizador
from app.audiencias.motor import (
    motor_audiencias, FaseAudiencia, ORDEM_FASES_AUDIENCIA,
    DESCRICAO_FASES, PAPEIS_POR_FASE
)
from app.audiencias.modelos import (
    TipoAudiencia, PapelAgente, TipoIntervencao, EstadoAudiencia
)
from app.documents.processador import ProcessadorDocumentos

router = APIRouter(prefix="/audiencias", tags=["Audiências — Fase 3"])
logger = structlog.get_logger(__name__)
_doc_processor = ProcessadorDocumentos()


# ── Schemas ──────────────────────────────────────────────────────────────────

class CriarAudienciaRequest(BaseModel):
    descricao_caso: str
    tipo_processo: str                    # laboral | penal | civil | etc.
    tipo_audiencia: TipoAudiencia = TipoAudiencia.JULGAMENTO
    papel_criador: PapelAgente            # qual o papel de quem cria
    processo_id: Optional[str] = None
    com_perito: bool = False
    max_loops_contraditorio: int = 3      # quantas rondas o juiz pode pedir


class IntervencaoRequest(BaseModel):
    papel: PapelAgente
    conteudo: str
    tipo: TipoIntervencao = TipoIntervencao.ALEGACAO


class IntervencaoIARequest(BaseModel):
    papel: PapelAgente


class ProvaTextoRequest(BaseModel):
    papel: PapelAgente
    tipo_prova: str   # documento | pericia | testemunho | video | imagem
    descricao: str
    conteudo_texto: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("")
async def criar_audiencia(
    dados: CriarAudienciaRequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Cria uma nova audiência.
    Qualquer utilizador autenticado pode criar — vítima, arguido, advogado, etc.
    O papel_criador define a posição processual de quem cria.
    """
    a = motor_audiencias.criar_audiencia(
        descricao_caso=dados.descricao_caso,
        tipo_processo=dados.tipo_processo,
        tipo_audiencia=dados.tipo_audiencia,
        criado_por=utilizador.id,
        papel_criador=dados.papel_criador,
        processo_id=dados.processo_id,
        com_perito=dados.com_perito,
        max_loops=dados.max_loops_contraditorio,
    )
    logger.info("audiencia.criada.api", id=a.id, user=utilizador.id, papel=dados.papel_criador.value)
    return _serializar_audiencia(a)


@router.get("")
async def listar_audiencias(utilizador: Utilizador = Depends(requer_login)):
    """Lista todas as audiências criadas pelo utilizador."""
    audiencias = motor_audiencias.listar_audiencias(criado_por=utilizador.id)
    return {
        "audiencias": [_serializar_resumo(a) for a in audiencias],
        "total": len(audiencias),
    }


@router.get("/{aid}")
async def ver_audiencia(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """Detalhe completo de uma audiência com todas as intervenções e provas."""
    try:
        a = motor_audiencias.obter_audiencia(aid)
        return _serializar_audiencia(a)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{aid}/fases")
async def estado_fases(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """
    Mostra o estado actual das fases, quem deve falar a seguir,
    e o que acontecerá em cada fase futura.
    """
    try:
        a = motor_audiencias.obter_audiencia(aid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    fases = []
    idx_actual = ORDEM_FASES_AUDIENCIA.index(a.fase_actual) if a.fase_actual in ORDEM_FASES_AUDIENCIA else -1

    for i, fase in enumerate(ORDEM_FASES_AUDIENCIA):
        papeis = [p.value for p in PAPEIS_POR_FASE.get(fase, [])]
        fases.append({
            "fase": fase.value,
            "descricao": DESCRICAO_FASES.get(fase, ""),
            "papeis_permitidos": papeis,
            "estado": "concluida" if i < idx_actual else "actual" if i == idx_actual else "futura",
        })

    return {
        "audiencia_id": aid,
        "fase_actual": a.fase_actual.value,
        "estado_audiencia": a.estado.value,
        "aguarda_intervencao_de": a.aguarda_intervencao_de.value if a.aguarda_intervencao_de else None,
        "loops_contraditorio": f"{a.num_loops_contraditorio}/{a.max_loops_contraditorio}",
        "fases": fases,
    }


@router.post("/{aid}/intervencao")
async def submeter_intervencao(
    aid: str,
    dados: IntervencaoRequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Submete uma intervenção humana numa audiência.
    O conteúdo é escrito pelo utilizador — não gerado por IA.
    """
    try:
        iv, orientacao = motor_audiencias.processar_intervencao(
            audiencia_id=aid,
            papel=dados.papel,
            conteudo=dados.conteudo,
            tipo=dados.tipo,
        )
        return {
            "intervencao_id": iv.id,
            "papel": iv.papel.value,
            "tipo": iv.tipo.value,
            "normas_citadas": iv.normas_citadas,
            "hash_integridade": iv.hash_integridade,
            "timestamp": iv.timestamp.isoformat(),
            "orientacao_proximo_passo": orientacao,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/intervencao-ia")
async def gerar_intervencao_ia(
    aid: str,
    dados: IntervencaoIARequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Gera automaticamente uma intervenção para um papel usando IA.
    Útil para simular a parte contrária ou treinar.
    """
    try:
        iv = motor_audiencias.gerar_intervencao_automatica(aid, dados.papel)
        return {
            "intervencao_id": iv.id,
            "papel": iv.papel.value,
            "conteudo": iv.conteudo,
            "normas_citadas": iv.normas_citadas,
            "hash_integridade": iv.hash_integridade,
            "gerado_por_ia": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/prova-texto")
async def apresentar_prova_texto(
    aid: str,
    dados: ProvaTextoRequest,
    utilizador: Utilizador = Depends(requer_login),
):
    """Apresenta uma prova em formato texto (testemunho, descrição, etc.)."""
    try:
        prova = motor_audiencias.apresentar_prova(
            audiencia_id=aid,
            papel=dados.papel,
            tipo_prova=dados.tipo_prova,
            descricao=dados.descricao,
            conteudo_texto=dados.conteudo_texto,
        )
        return {
            "prova_id": prova.id,
            "tipo": prova.tipo,
            "hash_integridade": prova.hash_integridade,
            "timestamp": prova.timestamp.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/prova-ficheiro")
async def apresentar_prova_ficheiro(
    aid: str,
    papel: str = Form(...),
    tipo_prova: str = Form(...),
    descricao: str = Form(...),
    ficheiro: UploadFile = File(...),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Apresenta uma prova como ficheiro (PDF, imagem, vídeo descrito em texto).
    O sistema extrai o texto do ficheiro para análise jurídica.
    """
    try:
        papel_enum = PapelAgente(papel)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Papel inválido: {papel}")

    conteudo = await ficheiro.read()
    doc = _doc_processor.processar(ficheiro.filename or "ficheiro", conteudo)

    texto_prova = doc.texto if doc.texto else f"[Ficheiro: {ficheiro.filename} — {doc.num_paginas} página(s)]"
    if doc.avisos:
        texto_prova += f"\n[Avisos: {'; '.join(doc.avisos)}]"

    try:
        prova = motor_audiencias.apresentar_prova(
            audiencia_id=aid,
            papel=papel_enum,
            tipo_prova=tipo_prova,
            descricao=descricao,
            conteudo_texto=texto_prova,
            nome_ficheiro=ficheiro.filename,
        )
        return {
            "prova_id": prova.id,
            "tipo": prova.tipo,
            "nome_ficheiro": prova.nome_ficheiro,
            "caracteres_extraidos": len(doc.texto),
            "avisos": doc.avisos,
            "hash_integridade": prova.hash_integridade,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{aid}/decidir")
async def proferir_decisao(aid: str, utilizador: Utilizador = Depends(requer_login)):
    """
    O juiz profere a decisão final.
    Só possível na fase de Decisão, após todas as partes terem falado.
    """
    try:
        decisao = motor_audiencias.proferir_decisao(aid)
        return {
            "sumario": decisao.sumario,
            "fundamentacao": decisao.fundamentacao,
            "normas_aplicadas": decisao.normas_aplicadas,
            "dispositivo": decisao.dispositivo,
            "recursos_possiveis": decisao.recursos_possiveis,
            "timestamp": decisao.timestamp.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Serialização ─────────────────────────────────────────────────────────────

def _serializar_audiencia(a) -> dict:
    return {
        "id": a.id,
        "processo_id": a.processo_id,
        "tipo": a.tipo.value,
        "tipo_processo": a.tipo_processo,
        "descricao_caso": a.descricao_caso,
        "estado": a.estado.value,
        "fase_actual": a.fase_actual.value,
        "fase_descricao": DESCRICAO_FASES.get(a.fase_actual, ""),
        "papel_criador": a.papel_criador.value,
        "aguarda_intervencao_de": a.aguarda_intervencao_de.value if a.aguarda_intervencao_de else None,
        "loops_contraditorio": a.num_loops_contraditorio,
        "max_loops": a.max_loops_contraditorio,
        "criada_em": a.criada_em.isoformat(),
        "participantes": [
            {"papel": p.papel.value, "nome": p.nome, "activo": p.activo}
            for p in a.participantes
        ],
        "intervencoes": [
            {
                "id": iv.id,
                "ronda": iv.ronda,
                "papel": iv.papel.value,
                "tipo": iv.tipo.value,
                "conteudo": iv.conteudo,
                "normas_citadas": iv.normas_citadas,
                "timestamp": iv.timestamp.isoformat(),
                "hash_integridade": iv.hash_integridade,
            }
            for iv in a.intervencoes
        ],
        "provas": [
            {
                "id": pr.id,
                "apresentada_por": pr.apresentada_por.value,
                "tipo": pr.tipo,
                "descricao": pr.descricao,
                "nome_ficheiro": pr.nome_ficheiro,
                "timestamp": pr.timestamp.isoformat(),
                "hash_integridade": pr.hash_integridade,
            }
            for pr in a.provas
        ],
        "decisao": {
            "sumario": a.decisao.sumario,
            "fundamentacao": a.decisao.fundamentacao,
            "normas_aplicadas": a.decisao.normas_aplicadas,
            "dispositivo": a.decisao.dispositivo,
            "recursos_possiveis": a.decisao.recursos_possiveis,
        } if a.decisao else None,
    }


def _serializar_resumo(a) -> dict:
    return {
        "id": a.id,
        "tipo": a.tipo.value,
        "tipo_processo": a.tipo_processo,
        "descricao_caso": a.descricao_caso[:100],
        "estado": a.estado.value,
        "fase_actual": a.fase_actual.value,
        "num_intervencoes": len(a.intervencoes),
        "num_provas": len(a.provas),
        "criada_em": a.criada_em.isoformat(),
        "tem_decisao": a.decisao is not None,
    }
