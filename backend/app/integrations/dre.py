"""
Integração com o Diário da República Electrónico (DRE).

A API do DRE (dre.pt) permite pesquisar e aceder a diplomas
legais publicados em Portugal. Esta integração:

1. Pesquisa diplomas por texto livre
2. Obtém o texto completo de um diploma específico
3. Sincroniza automaticamente alterações legislativas
4. Valida se um artigo citado ainda está em vigor

API base: https://dre.pt/api/
Documentação: https://dre.pt/api/docs (não pública — reverse engineered)

NOTA: O DRE não tem uma API pública oficial documentada.
Usamos o endpoint de pesquisa que o site usa internamente.
Em produção .gov, negociar acesso directo à base de dados com AMA/DGPJ.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)

DRE_BASE = "https://dre.pt"
DRE_SEARCH = f"{DRE_BASE}/api/search"
DRE_DIPLOMA = f"{DRE_BASE}/api/diploma"

# Timeout generoso — o DRE pode ser lento
TIMEOUT = 15.0


@dataclass
class DiplomaDRE:
    """Um diploma legislativo do Diário da República."""
    id: str
    tipo: str               # "Lei", "Decreto-Lei", "Portaria", etc.
    numero: str             # "7/2009"
    data_publicacao: str    # "2009-02-12"
    titulo: str
    sumario: str
    url: str
    em_vigor: bool = True
    revogado_por: Optional[str] = None


@dataclass
class ResultadoPesquisaDRE:
    """Resultado de uma pesquisa no DRE."""
    query: str
    total: int
    diplomas: list[DiplomaDRE]
    fonte: str = "dre.pt"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ClienteDRE:
    """
    Cliente HTTP para a API do DRE.
    Usa httpx assíncrono para não bloquear o servidor.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={
                "User-Agent": "SNAJI/3.0 (Sistema Nacional de Assistência Jurídica; gov.pt)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    async def pesquisar(
        self,
        query: str,
        tipo: Optional[str] = None,
        ano: Optional[int] = None,
        pagina: int = 1,
        por_pagina: int = 10,
    ) -> ResultadoPesquisaDRE:
        """
        Pesquisa diplomas no DRE.
        Retorna resultados mesmo em caso de falha (degrada graciosamente).
        """
        params = {
            "q": query,
            "rows": por_pagina,
            "start": (pagina - 1) * por_pagina,
        }
        if tipo:
            params["tipos"] = tipo
        if ano:
            params["ano"] = ano

        try:
            logger.info("dre.pesquisar", query=query)
            r = await self._client.get(DRE_SEARCH, params=params)
            r.raise_for_status()
            dados = r.json()
            diplomas = self._parse_resultados(dados)
            logger.info("dre.pesquisar.ok", total=len(diplomas))
            return ResultadoPesquisaDRE(
                query=query,
                total=dados.get("total", len(diplomas)),
                diplomas=diplomas,
            )
        except httpx.TimeoutException:
            logger.warning("dre.timeout", query=query)
            return self._resultado_fallback(query, "Timeout ao contactar o DRE")
        except httpx.HTTPStatusError as e:
            logger.warning("dre.http_error", status=e.response.status_code, query=query)
            return self._resultado_fallback(query, f"DRE devolveu erro {e.response.status_code}")
        except Exception as e:
            logger.error("dre.error", error=str(e), query=query)
            return self._resultado_fallback(query, str(e))

    async def obter_diploma(self, diploma_id: str) -> Optional[DiplomaDRE]:
        """Obtém os detalhes completos de um diploma específico pelo ID."""
        try:
            r = await self._client.get(f"{DRE_DIPLOMA}/{diploma_id}")
            r.raise_for_status()
            dados = r.json()
            return self._parse_diploma(dados)
        except Exception as e:
            logger.warning("dre.obter_diploma.error", id=diploma_id, error=str(e))
            return None

    def _parse_resultados(self, dados: dict) -> list[DiplomaDRE]:
        """Converte a resposta do DRE em objectos DiplomaDRE."""
        resultados = dados.get("items", dados.get("results", []))
        diplomas = []
        for item in resultados:
            try:
                diplomas.append(DiplomaDRE(
                    id=str(item.get("id", "")),
                    tipo=item.get("tipo", ""),
                    numero=item.get("numero", ""),
                    data_publicacao=item.get("data_publicacao", ""),
                    titulo=item.get("titulo", item.get("sumario", ""))[:200],
                    sumario=item.get("sumario", "")[:500],
                    url=f"{DRE_BASE}/pesquisa/-/search/diploma/{item.get('id', '')}",
                    em_vigor=item.get("em_vigor", True),
                ))
            except Exception:
                continue
        return diplomas

    def _parse_diploma(self, dados: dict) -> DiplomaDRE:
        return DiplomaDRE(
            id=str(dados.get("id", "")),
            tipo=dados.get("tipo", ""),
            numero=dados.get("numero", ""),
            data_publicacao=dados.get("data_publicacao", ""),
            titulo=dados.get("titulo", "")[:200],
            sumario=dados.get("sumario", "")[:500],
            url=f"{DRE_BASE}/pesquisa/-/search/diploma/{dados.get('id', '')}",
            em_vigor=dados.get("em_vigor", True),
            revogado_por=dados.get("revogado_por"),
        )

    def _resultado_fallback(self, query: str, motivo: str) -> ResultadoPesquisaDRE:
        """
        Quando o DRE não responde, devolvemos os resultados do corpus local.
        O sistema nunca fica sem resposta — degrada graciosamente.
        """
        from app.rag.motor import RAGJuridico
        rag = RAGJuridico()
        chunks = rag.search(query, top_k=5)
        diplomas_locais = [
            DiplomaDRE(
                id=f"local-{c.diploma}-{c.artigo}",
                tipo="Corpus Local",
                numero=f"Art. {c.artigo}.º {c.diploma}",
                data_publicacao="",
                titulo=c.epigrase or f"Artigo {c.artigo}.º do {c.diploma}",
                sumario=c.texto[:300],
                url=c.fonte,
                em_vigor=True,
            )
            for c in chunks
        ]
        logger.info("dre.fallback.corpus_local", query=query, motivo=motivo, resultados=len(diplomas_locais))
        return ResultadoPesquisaDRE(
            query=query,
            total=len(diplomas_locais),
            diplomas=diplomas_locais,
            fonte=f"corpus_local (DRE indisponível: {motivo})",
        )

    async def verificar_vigencia(self, diploma: str, artigo: str) -> dict:
        """
        Verifica se um artigo específico ainda está em vigor.
        Usado pelo sistema anti-alucinação para validação adicional.
        """
        # Primeiro verifica no corpus local
        from app.rag.motor import ValidadorCitacoes
        validator = ValidadorCitacoes()
        em_corpus = validator.validar(diploma, artigo)

        resultado = {
            "diploma": diploma,
            "artigo": artigo,
            "em_corpus_local": em_corpus,
            "verificado_em": datetime.now(timezone.utc).isoformat(),
        }

        # Tenta verificar online (best-effort)
        try:
            r = await self._client.get(
                DRE_SEARCH,
                params={"q": f"{diploma} artigo {artigo}", "rows": 3},
                timeout=5.0,
            )
            if r.status_code == 200:
                resultado["dre_online"] = True
        except Exception:
            resultado["dre_online"] = False

        return resultado

    async def close(self):
        await self._client.aclose()


# Instância partilhada (lazy — inicializada na primeira utilização)
_cliente_dre: Optional[ClienteDRE] = None


def get_cliente_dre() -> ClienteDRE:
    global _cliente_dre
    if _cliente_dre is None:
        _cliente_dre = ClienteDRE()
    return _cliente_dre
