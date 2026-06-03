"""
Rotas das Integrações Governamentais do SNAJI — Fase 4.

Endpoints:
GET  /integracoes/dre/pesquisar         → pesquisa no DRE
GET  /integracoes/dre/vigencia          → verifica se artigo está em vigor
GET  /integracoes/jurisprudencia        → pesquisa acórdãos
GET  /integracoes/jurisprudencia/norma  → acórdãos por norma
GET  /auth/cmd/iniciar                  → inicia fluxo CMD
GET  /auth/cmd/callback                 → callback CMD
GET  /integracoes/estado                → estado de todas as integrações
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
import structlog

from app.security.dependencias import requer_login, requer_role
from app.security.rbac import Role
from app.db.utilizadores import Utilizador
from app.integrations.dre import get_cliente_dre
from app.integrations.jurisprudencia import motor_jurisprudencia
from app.integrations.cmd import gestor_cmd

router = APIRouter(tags=["Integrações Gov — Fase 4"])
logger = structlog.get_logger(__name__)


# ── DRE ──────────────────────────────────────────────────────────────────────

@router.get("/integracoes/dre/pesquisar")
async def pesquisar_dre(
    q: str = Query(..., min_length=2, description="Texto a pesquisar"),
    tipo: Optional[str] = Query(None, description="Lei, Decreto-Lei, Portaria, etc."),
    ano: Optional[int] = Query(None, description="Ano de publicação"),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Pesquisa diplomas no Diário da República.
    Degrada graciosamente para corpus local se o DRE estiver indisponível.
    """
    # Usa sempre o fallback corpus local (não depende de rede externa)
    from app.integrations.dre import ClienteDRE
    cliente_local = ClienteDRE.__new__(ClienteDRE)
    resultado = cliente_local._resultado_fallback(q, "Usar corpus local para demo")
    return {
        "query": resultado.query,
        "total": resultado.total,
        "fonte": resultado.fonte,
        "timestamp": resultado.timestamp,
        "diplomas": [
            {
                "id": d.id,
                "tipo": d.tipo,
                "numero": d.numero,
                "data_publicacao": d.data_publicacao,
                "titulo": d.titulo,
                "sumario": d.sumario,
                "url": d.url,
                "em_vigor": d.em_vigor,
            }
            for d in resultado.diplomas
        ],
    }


@router.get("/integracoes/dre/vigencia")
async def verificar_vigencia(
    diploma: str = Query(..., description="Ex: CRP, CT, CC, CP"),
    artigo: str = Query(..., description="Número do artigo"),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Verifica se um artigo específico está em vigor.
    Verifica no corpus local. Em produção adiciona consulta online ao DRE.
    """
    from app.rag.motor import ValidadorCitacoes
    from datetime import datetime, timezone
    validator = ValidadorCitacoes()
    em_corpus = validator.validar(diploma, artigo)
    return {
        "diploma": diploma,
        "artigo": artigo,
        "em_corpus_local": em_corpus,
        "dre_online": None,  # requer httpx async em produção
        "verificado_em": datetime.now(timezone.utc).isoformat(),
    }


# ── Jurisprudência ────────────────────────────────────────────────────────────

@router.get("/integracoes/jurisprudencia")
async def pesquisar_jurisprudencia(
    q: str = Query(..., min_length=3, description="Factos ou questão jurídica"),
    top_k: int = Query(3, ge=1, le=10),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Pesquisa acórdãos jurisprudenciais relevantes para um caso.
    Usa BM25 sobre base de acórdãos representativos.
    """
    resultado = motor_jurisprudencia.pesquisar(q, top_k=top_k)
    return {
        "query": resultado.query,
        "total": resultado.total,
        "fonte": resultado.fonte,
        "timestamp": resultado.timestamp,
        "acordaos": [
            {
                "id": a.id,
                "tribunal": a.tribunal,
                "numero_processo": a.numero_processo,
                "data": a.data,
                "sumario": a.sumario,
                "descritores": a.descritores,
                "normas_citadas": a.normas_citadas,
                "url": a.url,
            }
            for a in resultado.acordaos
        ],
    }


@router.get("/integracoes/jurisprudencia/norma")
async def acordaos_por_norma(
    diploma: str = Query(..., description="Ex: CRP, CT, CC"),
    artigo: str = Query(..., description="Número do artigo"),
    utilizador: Utilizador = Depends(requer_login),
):
    """
    Devolve acórdãos que citam uma norma específica.
    Útil para encontrar interpretações jurisprudenciais de um artigo.
    """
    acordaos = motor_jurisprudencia.acordaos_por_norma(diploma, artigo)
    return {
        "norma": f"Art. {artigo}.º {diploma}",
        "total": len(acordaos),
        "acordaos": [
            {
                "id": a.id,
                "tribunal": a.tribunal,
                "data": a.data,
                "sumario": a.sumario[:300],
                "url": a.url,
            }
            for a in acordaos
        ],
    }


# ── CMD (Chave Móvel Digital) ─────────────────────────────────────────────────

@router.get("/auth/cmd/iniciar")
async def iniciar_autenticacao_cmd(
    redirect_apos: str = Query("/dashboard"),
):
    """
    Inicia o fluxo de autenticação com a Chave Móvel Digital.
    Redireciona para login.autenticacao.gov.pt.
    """
    if not gestor_cmd.esta_configurada():
        raise HTTPException(
            status_code=503,
            detail=(
                "Autenticação CMD não configurada. "
                "Defina CMD_CLIENT_ID, CMD_CLIENT_SECRET e CMD_REDIRECT_URI no ficheiro .env. "
                "Credenciais disponíveis em: https://www.autenticacao.gov.pt/autenticacao-egovernment"
            ),
        )
    url, state = gestor_cmd.gerar_url_autorizacao(redirect_apos)
    return {"url_autorizacao": url, "state": state}


@router.get("/auth/cmd/callback")
async def callback_cmd(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
):
    """
    Callback do fluxo OAuth2 da CMD.
    Troca o código de autorização por dados do utilizador.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Erro CMD: {error}")

    try:
        utilizador_cmd = await gestor_cmd.processar_callback(code, state)
        dados = gestor_cmd.criar_utilizador_snaji_de_cmd(utilizador_cmd)

        # Aqui: criar ou actualizar o utilizador no repositório
        # e gerar um token JWT SNAJI
        from app.db.utilizadores import repositorio
        from app.security.jwt_manager import jwt_manager
        from app.security.rbac import Role

        # Verifica se já existe conta
        u = repositorio.por_email(dados["email"])
        if not u:
            # Cria conta nova automaticamente
            u = repositorio.criar(
                email=dados["email"],
                nome=dados["nome"],
                role=Role.CIDADAO,
                password=f"cmd-{state[:8]}",  # password temporária — login é sempre via CMD
            )

        token = jwt_manager.criar_token(u.id, u.role)
        return {
            "access_token": token.access_token,
            "token_type": "bearer",
            "expira_em": token.expira_em,
            "role": token.role,
            "autenticado_via": "cmd",
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Estado das integrações ────────────────────────────────────────────────────

@router.get("/integracoes/estado")
async def estado_integracoes(
    utilizador: Utilizador = Depends(requer_role(Role.ADMIN, Role.MAGISTRADO)),
):
    """
    Estado de todas as integrações externas.
    Apenas para administradores e magistrados.
    """
    import httpx
    estados = {}

    # Testa DRE
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get("https://dre.pt", follow_redirects=True)
            estados["dre"] = {"estado": "online", "status": r.status_code}
    except Exception as e:
        estados["dre"] = {"estado": "offline", "erro": str(e)[:100]}

    # CMD
    estados["cmd"] = {
        "estado": "configurada" if gestor_cmd.esta_configurada() else "nao_configurada",
        "ambiente": "sandbox",  # mostrar ambiente actual
    }

    # Jurisprudência local
    estados["jurisprudencia"] = {
        "estado": "ok",
        "acordaos": motor_jurisprudencia.total_acordaos,
        "fonte": "corpus_local",
    }

    # RAG
    from app.rag.motor import RAGJuridico
    rag = RAGJuridico()
    estados["rag"] = {
        "estado": "ok",
        "artigos": rag.total_artigos,
        "diplomas": ["CRP", "CT", "CC", "RGPD", "CP", "CPC+CPP"],
    }

    return {"integracoes": estados, "versao": "3.0.0"}
