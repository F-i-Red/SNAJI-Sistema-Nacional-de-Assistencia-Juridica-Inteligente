"""
Motor RAG jurídico real.
BM25 sobre 166 artigos reais de 4 diplomas portugueses.
Corpus construído a partir de fontes oficiais (parlamento.pt, pgdlisboa.pt, eur-lex.europa.eu).
"""
import json
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass
from rank_bm25 import BM25Okapi


@dataclass
class Chunk:
    diploma: str
    artigo: str
    epigrase: str
    texto: str
    fonte: str
    score: float = 0.0


def _carregar_corpus() -> list[dict]:
    caminho = Path(__file__).parent / "corpus" / "corpus.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Corpus não encontrado em {caminho}.\n"
            "Corre: python app/rag/corpus/processador.py"
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


def _normalizar(texto: str) -> list[str]:
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    return texto.split()


# Mapeamento de aliases para o código do diploma
ALIAS_DIPLOMA = {
    "crp": "CRP", "constituição": "CRP", "constituicao": "CRP",
    "ct": "CT", "código do trabalho": "CT", "codigo do trabalho": "CT",
    "cc": "CC", "código civil": "CC", "codigo civil": "CC",
    "rgpd": "RGPD", "protecção de dados": "RGPD",
}

# Normas válidas para anti-alucinação (preenchido dinamicamente)
NORMAS_VALIDAS: dict[str, set[str]] = {}


class RAGJuridico:
    """BM25 sobre corpus jurídico real. Sem dados hardcoded."""

    def __init__(self):
        self._chunks = _carregar_corpus()
        # Preenche normas válidas para o validador
        for c in self._chunks:
            NORMAS_VALIDAS.setdefault(c["diploma"], set()).add(c["artigo"])
        # Indexa: texto + epígrafe + diploma para melhor recall
        textos = [
            _normalizar(f"{c['epigrase']} {c['texto']} {c['diploma']}")
            for c in self._chunks
        ]
        self._bm25 = BM25Okapi(textos)

    def search(self, query: str, top_k: int = 6, diploma: str | None = None) -> list[Chunk]:
        tokens = _normalizar(query)
        scores = self._bm25.get_scores(tokens)
        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        resultados = []
        for i in indices:
            if len(resultados) >= top_k:
                break
            c = self._chunks[i]
            if diploma and c["diploma"] != diploma.upper():
                continue
            if scores[i] <= 0.0:
                continue
            resultados.append(Chunk(
                diploma=c["diploma"],
                artigo=c["artigo"],
                epigrase=c.get("epigrase", ""),
                texto=c["texto"],
                fonte=c.get("fonte", ""),
                score=round(float(scores[i]), 4),
            ))
        return resultados

    def get_artigo(self, diploma: str, artigo: str) -> Chunk | None:
        """Recupera um artigo específico pelo diploma e número."""
        for c in self._chunks:
            if c["diploma"] == diploma.upper() and c["artigo"] == artigo:
                return Chunk(**{k: c.get(k, "") for k in
                               ["diploma","artigo","epigrase","texto","fonte"]})
        return None

    @property
    def total_artigos(self) -> int:
        return len(self._chunks)


class ValidadorCitacoes:
    """Anti-alucinação determinístico baseado no corpus real."""

    PADRAO = re.compile(
        r"[Aa]rt(?:igo)?\.?\s*(\d+[A-Z]?)\.?[°º]?\s*"
        r"(?:do|da|n\.?[°º]?)?\s*"
        r"(CRP|Constituição|Código do Trabalho|CT|Código Civil|CC|RGPD|"
        r"Código Penal|CP|Código de Processo Civil|CPC)",
        re.IGNORECASE | re.UNICODE,
    )
    MAPA = {
        "crp": "CRP", "constituição": "CRP",
        "código do trabalho": "CT", "ct": "CT",
        "código civil": "CC", "cc": "CC",
        "rgpd": "RGPD",
        "código penal": "CP", "cp": "CP",
        "código de processo civil": "CPC", "cpc": "CPC",
    }

    def validar(self, diploma: str, artigo: str) -> bool:
        normas = NORMAS_VALIDAS.get(diploma.upper(), set())
        return artigo in normas

    def extrair_e_validar(self, texto: str) -> tuple[list[dict], list[dict]]:
        validas, suspeitas, vistos = [], [], set()
        for m in self.PADRAO.finditer(texto):
            artigo = m.group(1)
            raw = m.group(2).strip().lower()
            diploma = self.MAPA.get(raw, raw.upper())
            chave = f"{diploma}-{artigo}"
            if chave in vistos:
                continue
            vistos.add(chave)
            entrada = {"diploma": diploma, "artigo": artigo}
            (validas if self.validar(diploma, artigo) else suspeitas).append(entrada)
        return validas, suspeitas
