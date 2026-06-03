"""
Rotas completas da API SNAJI — v1.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import structlog

from app.core.schemas import AnalysisRequest, AnalysisResponse
from app.orchestrator.orchestrator import JuridicalOrchestrator
from app.security.dependencias import requer_login, requer_permissao
from app.security.rbac import Permissao
from app.db.utilizadores import Utilizador
from app.documents.processador import ProcessadorDocumentos
from app.processes.repositorio import repositorio_processos, TipoProcesso, Parte
from app.generation.gerador import GeradorDocumentos, TipoDocumento
from app.reasoning.pipeline import ReasoningPipeline

router = APIRouter()
logger = structlog.get_logger(__name__)

_orchestrator: JuridicalOrchestrator | None = None
_doc_processor = ProcessadorDocumentos()
_gerador = GeradorDocumentos()
_reasoning = ReasoningPipeline(llm_client=None)


def get_orchestrator() -> JuridicalOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = JuridicalOrchestrator()
    return _orchestrator


# ── Análise jurídica ──────────────────────────────────────────────────────────

@router.post("/analysis", response_model=AnalysisResponse, tags=["Análise"])
async def analyse_case(
    request: AnalysisRequest,
    utilizador: Utilizador = Depends(requer_permissao(Permissao.SUBMETER_CASO)),
    orchestrator: JuridicalOrchestrator = Depends(get_orchestrator),
) -> AnalysisResponse:
    logger.info("analysis.start", user_id=utilizador.id)
    try:
        return await orchestrator.process(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("analysis.failed", error=str(e))
        raise HTTPException(status_code=500, detail="Erro no pipeline jurídico")


@router.get("/fontes", tags=["Análise"])
async def listar_fontes(_: Utilizador = Depends(requer_login)):
    return {
        "fontes": [
            {"codigo": "CRP",  "nome": "Constituição da República Portuguesa", "artigos": 55},
            {"codigo": "CT",   "nome": "Código do Trabalho", "artigos": 33},
            {"codigo": "CC",   "nome": "Código Civil", "artigos": 58},
            {"codigo": "RGPD", "nome": "RGPD", "artigos": 20},
            {"codigo": "CP",   "nome": "Código Penal", "artigos": 45},
            {"codigo": "CPC",  "nome": "Código de Processo Civil e Penal", "artigos": 35},
        ],
        "total_artigos": 246,
    }


# ── Upload de documentos ──────────────────────────────────────────────────────

@router.post("/documentos/upload", tags=["Documentos"])
async def upload_documento(
    ficheiro: UploadFile = File(...),
    analisar: bool = Form(default=True),
    utilizador: Utilizador = Depends(requer_permissao(Permissao.SUBMETER_CASO)),
):
    if not ficheiro.filename:
        raise HTTPException(status_code=400, detail="Nome de ficheiro inválido")
    ext = ficheiro.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('pdf', 'docx', 'txt'):
        raise HTTPException(status_code=400, detail="Formato não suportado. Use PDF, DOCX ou TXT.")

    conteudo = await ficheiro.read()
    doc = _doc_processor.processar(ficheiro.filename, conteudo)

    resposta: dict = {
        "nome": doc.nome_original,
        "tipo": doc.tipo.value,
        "num_paginas": doc.num_paginas,
        "num_caracteres": doc.num_caracteres,
        "avisos": doc.avisos,
        "texto_extraido": doc.texto[:500] + "..." if len(doc.texto) > 500 else doc.texto,
    }

    if analisar and doc.texto:
        try:
            resultado = _reasoning.analisar(doc.texto[:3000])
            resposta["analise"] = {
                "tipo_processo": resultado.tipo_processo.value,
                "qualificacao": resultado.qualificacao,
                "normas": [{"diploma": n.diploma, "artigo": n.artigo, "epigrase": n.epigrase} for n in resultado.normas[:5]],
                "grounded": resultado.grounded,
            }
        except Exception as e:
            logger.warning("upload.analise.falhou", error=str(e))

    return resposta


# ── Processos jurídicos ───────────────────────────────────────────────────────

class CriarProcessoRequest(BaseModel):
    tipo: TipoProcesso
    descricao: str
    nome_autor: str
    nome_reu: str
    valor_causa: Optional[float] = None
    tribunal: str = "Tribunal Judicial"
    comarca: str = "Lisboa"
    caso_id_analise: Optional[str] = None


@router.get("/processos", tags=["Processos"])
async def listar_processos(utilizador: Utilizador = Depends(requer_login)):
    processos = repositorio_processos.por_utilizador(utilizador.id)
    return {
        "processos": [
            {
                "id": p.id,
                "numero": p.numero,
                "tipo": p.tipo.value,
                "descricao": p.descricao,
                "estado": p.estado.value,
                "partes": [{"nome": pt.nome, "papel": pt.papel} for pt in p.partes],
                "criado_em": p.criado_em.isoformat(),
                "atualizado_em": p.atualizado_em.isoformat(),
                "num_eventos": len(p.eventos),
                "prazos_urgentes": sum(1 for pr in p.prazos if pr.urgente and not pr.cumprido),
            }
            for p in processos
        ],
        "total": len(processos),
    }


@router.post("/processos", tags=["Processos"])
async def criar_processo(
    dados: CriarProcessoRequest,
    utilizador: Utilizador = Depends(requer_permissao(Permissao.SUBMETER_CASO)),
):
    partes = [Parte(dados.nome_autor, "autor"), Parte(dados.nome_reu, "réu")]
    p = repositorio_processos.criar(
        tipo=dados.tipo, descricao=dados.descricao, partes=partes,
        criado_por=utilizador.id, caso_id_analise=dados.caso_id_analise,
        valor_causa=dados.valor_causa, tribunal=dados.tribunal, comarca=dados.comarca,
    )
    return {"id": p.id, "numero": p.numero, "estado": p.estado.value}


@router.get("/processos/{pid}", tags=["Processos"])
async def ver_processo(pid: str, utilizador: Utilizador = Depends(requer_login)):
    p = repositorio_processos.por_id(pid)
    if not p:
        raise HTTPException(status_code=404, detail="Processo não encontrado")
    return {
        "id": p.id, "numero": p.numero, "tipo": p.tipo.value,
        "descricao": p.descricao, "estado": p.estado.value,
        "estado_index": p.fase_index(),
        "proximo_estado": p.proximo_estado().value if p.proximo_estado() else None,
        "partes": [{"nome": pt.nome, "papel": pt.papel} for pt in p.partes],
        "tribunal": p.tribunal, "comarca": p.comarca, "valor_causa": p.valor_causa,
        "criado_em": p.criado_em.isoformat(), "atualizado_em": p.atualizado_em.isoformat(),
        "prazos": [{"descricao": pr.descricao, "data_limite": pr.data_limite.isoformat(),
                    "urgente": pr.urgente, "cumprido": pr.cumprido} for pr in p.prazos],
        "eventos": [{"timestamp": ev.timestamp.isoformat(), "tipo": ev.tipo,
                     "descricao": ev.descricao, "estado_anterior": ev.estado_anterior,
                     "estado_novo": ev.estado_novo} for ev in p.eventos],
        "notas": p.notas, "caso_id_analise": p.caso_id_analise,
    }


@router.post("/processos/{pid}/avancar", tags=["Processos"])
async def avancar_processo(
    pid: str,
    nota: str = Form(default=""),
    utilizador: Utilizador = Depends(requer_login),
):
    try:
        p = repositorio_processos.avancar_estado(pid, utilizador.id, nota)
        return {"numero": p.numero, "estado": p.estado.value,
                "proximo": p.proximo_estado().value if p.proximo_estado() else None}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Geração de documentos ─────────────────────────────────────────────────────

class GerarDocumentoRequest(BaseModel):
    tipo: TipoDocumento
    texto_caso: str
    nome_autor: str = "[AUTOR]"
    nome_reu: str = "[RÉU]"


@router.post("/gerar-documento", tags=["Documentos"])
async def gerar_documento(
    dados: GerarDocumentoRequest,
    utilizador: Utilizador = Depends(requer_permissao(Permissao.SUBMETER_CASO)),
):
    resultado = _reasoning.analisar(dados.texto_caso)
    doc = _gerador.gerar(dados.tipo, resultado, dados.nome_autor, dados.nome_reu)
    return {
        "tipo": doc.tipo.value, "titulo": doc.titulo, "conteudo": doc.conteudo,
        "data_geracao": doc.data_geracao.isoformat(), "caso_id": doc.caso_id,
        "advertencia": doc.advertencia,
        "tipos_recomendados": [t.value for t in _gerador.tipos_disponiveis(resultado.tipo_processo)],
    }
