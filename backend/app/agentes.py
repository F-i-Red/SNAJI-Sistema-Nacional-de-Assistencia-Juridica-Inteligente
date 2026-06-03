"""
Agentes Especializados do SNAJI — Fase 3.

Cada agente tem:
1. Um papel processual bem definido
2. Um sistema de instruções que o mantém nesse papel
3. Acesso às normas relevantes do corpus (via RAG)
4. Capacidade de citar artigos verificados

Os agentes funcionam em modo stub sem LLM.
Com LLM activado, produzem argumentos jurídicos reais.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re

from app.audiencias.modelos import (
    PapelAgente, TipoIntervencao, ConfiguracaoAgente, Intervencao
)
from app.rag.motor import RAGJuridico, ValidadorCitacoes


# ── Instruções de sistema por papel ─────────────────────────────────────────

INSTRUCOES_AGENTES: dict[PapelAgente, str] = {

    PapelAgente.JUIZ: """És o Juiz Presidente nesta audiência do Tribunal Português.

O teu papel é:
- Moderar o debate com imparcialidade absoluta
- Aplicar a lei portuguesa com rigor
- Solicitar esclarecimentos quando necessário
- Manter a ordem e o foco nos factos relevantes
- No final, proferir uma decisão fundamentada

Regras que segues:
- Citas sempre o diploma e artigo exacto das normas que aplicas
- Nunca inventas normas — apenas as que existem no corpus jurídico fornecido
- Tratas todas as partes com igual respeito
- A tua decisão é baseada em factos provados, não em especulação

Formato das tuas intervenções: claro, conciso, autoritário mas justo.""",

    PapelAgente.ACUSACAO: """És o Magistrado do Ministério Público (ou advogado da parte autora) nesta audiência.

O teu papel é:
- Apresentar os factos que fundamentam a acusação/pedido
- Invocar as normas legais que protegem o interesse público ou do cliente
- Contra-argumentar as alegações da defesa com rigor jurídico
- Solicitar as medidas adequadas (pena, indemnização, etc.)

Regras que segues:
- Argumentas com base em factos e normas reais
- Citas sempre o artigo e diploma exactos
- Antecipas os argumentos da defesa e refutas-os preventivamente
- Mantens um tom assertivo mas respeitoso

Formato: argumentativo, directo, fundamentado em lei.""",

    PapelAgente.DEFESA: """És o Advogado de Defesa (ou advogado do réu) nesta audiência.

O teu papel é:
- Proteger os direitos fundamentais do arguido/réu (Art. 32.º CRP)
- Apresentar os factos favoráveis à defesa
- Contestar os argumentos da acusação com rigor jurídico
- Invocar princípios como a presunção de inocência, proporcionalidade, etc.
- Minimizar a responsabilidade ou pedir absolvição

Regras que segues:
- Nunca fazes afirmações de facto que sabes serem falsas
- Usas todas as garantias processuais em benefício do cliente
- Citas sempre artigos reais do corpus jurídico
- Exiges o cumprimento estrito dos direitos do arguido

Formato: persuasivo, técnico, orientado para a protecção dos direitos.""",

    PapelAgente.PERITO: """És um Perito nesta audiência — especialista técnico ou judicial.

O teu papel é:
- Apresentar factos técnicos de forma objectiva e imparcial
- Esclarecer aspectos técnicos que o tribunal precisa de compreender
- Responder a perguntas de forma clara e sem tomar partido
- Fundamentar as tuas conclusões em evidências verificáveis

Regras que segues:
- Distingues claramente factos de opiniões
- Nunca extravagas para além da tua área de competência
- Quando incerto, dizes explicitamente que há limitações
- Usas linguagem técnica mas acessível

Formato: objectivo, técnico, imparcial, fundamentado.""",

    PapelAgente.ASSISTENTE: """És o Assistente do ofendido nesta audiência.

O teu papel é:
- Representar os interesses da vítima ou ofendido
- Apresentar o impacto real do crime ou ilícito na vítima
- Apoiar a acusação pública com perspectiva da vítima
- Solicitar reparação adequada

Formato: empático mas jurídico, centrado no dano sofrido.""",
}


# ── Argumentos stub por tipo de processo e papel ────────────────────────────
# Usados quando o LLM não está disponível — baseados em normas reais

ARGUMENTOS_STUB: dict[str, dict[PapelAgente, list[str]]] = {
    "laboral": {
        PapelAgente.ACUSACAO: [
            "O despedimento é ilícito por ausência de justa causa nos termos do Art. 351.º do Código do Trabalho. Não foi instaurado qualquer procedimento disciplinar, conforme exigido pelo Art. 352.º CT.",
            "O trabalhador tem direito a indemnização mínima de 20 dias de retribuição por cada ano de antiguidade, nos termos do Art. 391.º CT, não podendo ser inferior a três meses.",
            "A proibição constitucional de despedimentos sem justa causa está consagrada no Art. 53.º da CRP, vinculando directamente as entidades privadas por força do Art. 18.º CRP.",
        ],
        PapelAgente.DEFESA: [
            "O empregador alega incumprimento reiterado de ordens, que pode constituir justa causa nos termos do Art. 351.º/2/a CT, dependendo de prova dos factos concretos.",
            "A prescrição de créditos laborais opera ao fim de um ano nos termos do Art. 482.º CT, pelo que parte dos pedidos pode estar prescrita.",
            "O ónus de prova dos factos constitutivos do direito cabe ao trabalhador, conforme Art. 342.º CC, aplicável subsidiariamente.",
        ],
        PapelAgente.JUIZ: [
            "O tribunal toma nota das alegações. Solicita à parte empregadora que apresente prova documental do procedimento disciplinar, se existiu.",
            "Nos termos do Art. 607.º do Código de Processo Civil, a decisão será fundamentada nos factos provados e nas normas aplicáveis.",
        ],
        PapelAgente.PERITO: [
            "Do ponto de vista laboral, a análise do contrato de trabalho e dos registos de assiduidade é determinante para estabelecer a antiguidade e o padrão de comportamento do trabalhador.",
        ],
    },
    "penal": {
        PapelAgente.ACUSACAO: [
            "Os factos imputados ao arguido preenchem o tipo objectivo e subjectivo do crime previsto, com dolo directo nos termos do Art. 14.º/1 do Código Penal.",
            "A existência de prova documental e testemunhal sustenta a acusação. Nos termos do Art. 283.º CPP, há indícios suficientes para julgamento.",
            "As circunstâncias agravantes previstas no Art. 132.º CP justificam uma pena no limite superior da moldura abstracta.",
        ],
        PapelAgente.DEFESA: [
            "O arguido beneficia da presunção de inocência consagrada no Art. 32.º/2 da CRP. O ónus da prova cabe inteiramente à acusação.",
            "A prova produzida é insuficiente para afastar a dúvida razoável. In dubio pro reo é princípio fundamental do processo penal português.",
            "Os direitos de defesa do arguido, incluindo o direito ao silêncio previsto no Art. 61.º/1/b CPP, devem ser plenamente respeitados.",
        ],
        PapelAgente.JUIZ: [
            "O tribunal garante ao arguido todos os direitos processuais previstos no Art. 61.º CPP e Art. 32.º CRP.",
            "A audiência prosseguirá com respeito estrito pelo princípio do contraditório previsto no Art. 32.º/5 CRP.",
        ],
    },
    "civil": {
        PapelAgente.ACUSACAO: [
            "O réu violou as obrigações contratuais assumidas, gerando responsabilidade civil nos termos do Art. 798.º e 799.º do Código Civil.",
            "O autor tem direito à reconstituição natural ou indemnização equivalente nos termos do Art. 562.º CC. Os danos patrimoniais e não patrimoniais estão provados.",
            "A presunção de culpa do devedor prevista no Art. 799.º CC inverte o ónus da prova, cabendo ao réu demonstrar que o incumprimento não lhe é imputável.",
        ],
        PapelAgente.DEFESA: [
            "O autor não logrou provar o nexo de causalidade entre o comportamento do réu e os danos alegados, conforme exige o Art. 563.º CC.",
            "A culpa do próprio lesado, prevista no Art. 487.º CC, pode reduzir ou excluir a indemnização a atribuir.",
            "O prazo de prescrição do direito à indemnização é de três anos a contar do conhecimento do dano, nos termos do Art. 498.º CC.",
        ],
        PapelAgente.JUIZ: [
            "O tribunal analisará a prova documental junta pelas partes para determinar a existência e extensão do dano.",
            "Nos termos do Art. 607.º/4 CPC, o tribunal analisará criticamente todas as provas produzidas.",
        ],
    },
}


class AgenteFabrica:
    """Cria configurações de agentes para diferentes tipos de audiência."""

    @staticmethod
    def criar_agentes_julgamento(
        tipo_processo: str,
        nome_acusacao: str = "Ministério Público",
        nome_defesa: str = "Advogado de Defesa",
        com_perito: bool = False,
    ) -> list[ConfiguracaoAgente]:
        agentes = [
            ConfiguracaoAgente(
                papel=PapelAgente.JUIZ,
                nome="Meritíssimo Juiz",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.JUIZ],
            ),
            ConfiguracaoAgente(
                papel=PapelAgente.ACUSACAO,
                nome=nome_acusacao,
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.ACUSACAO],
            ),
            ConfiguracaoAgente(
                papel=PapelAgente.DEFESA,
                nome=nome_defesa,
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.DEFESA],
            ),
        ]
        if com_perito:
            agentes.append(ConfiguracaoAgente(
                papel=PapelAgente.PERITO,
                nome="Perito Judicial",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.PERITO],
            ))
        return agentes

    @staticmethod
    def criar_agentes_contraditorio(tipo_processo: str) -> list[ConfiguracaoAgente]:
        """Para modo treino/preparação — sem juiz, foco no debate."""
        return [
            ConfiguracaoAgente(
                papel=PapelAgente.ACUSACAO,
                nome="Parte Autora",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.ACUSACAO],
            ),
            ConfiguracaoAgente(
                papel=PapelAgente.DEFESA,
                nome="Parte Ré",
                instrucoes_sistema=INSTRUCOES_AGENTES[PapelAgente.DEFESA],
            ),
        ]


def gerar_argumento_stub(
    tipo_processo: str,
    papel: PapelAgente,
    ronda: int,
) -> str:
    """
    Gera argumento determinístico quando LLM não está disponível.
    Baseado em normas reais do corpus.
    """
    args_tipo = ARGUMENTOS_STUB.get(tipo_processo, ARGUMENTOS_STUB["civil"])
    args_papel = args_tipo.get(papel, [])

    if not args_papel:
        return f"[{papel.value.upper()}] Argumento jurídico — aguarda activação do motor LLM para análise completa."

    idx = min(ronda, len(args_papel) - 1)
    return args_papel[idx]


def extrair_normas_citadas(texto: str) -> list[str]:
    """Extrai referências a normas jurídicas do texto de uma intervenção."""
    padrao = re.compile(
        r"Art\.?\s*(\d+)\.?[°º]?\s*(?:/\d+)?\s*(CP|CT|CC|CRP|RGPD|CPC|CPP)",
        re.IGNORECASE
    )
    normas = []
    vistos = set()
    for m in padrao.finditer(texto):
        chave = f"{m.group(2).upper()}-{m.group(1)}"
        if chave not in vistos:
            vistos.add(chave)
            normas.append(chave)
    return normas
