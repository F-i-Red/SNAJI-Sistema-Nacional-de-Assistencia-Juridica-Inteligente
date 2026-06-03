"""
Gerador de Documentos Jurídicos do SNAJI.

Gera documentos jurídicos estruturados com base no resultado do reasoning.
Sem LLM: gera templates preenchidos com os dados do caso.
Com LLM: gera texto profissional completo.

Tipos suportados:
- Petição inicial
- Contestação
- Recurso
- Requerimento
- Queixa-crime
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.reasoning.pipeline import ResultadoReasoning, TipoProcesso


class TipoDocumento(str, Enum):
    PETICAO_INICIAL  = "peticao_inicial"
    CONTESTACAO      = "contestacao"
    RECURSO          = "recurso"
    REQUERIMENTO     = "requerimento"
    QUEIXA_CRIME     = "queixa_crime"
    EXPOSICAO        = "exposicao"


@dataclass
class DocumentoGerado:
    tipo: TipoDocumento
    titulo: str
    conteudo: str
    data_geracao: datetime
    caso_id: str
    advertencia: str = (
        "DOCUMENTO GERADO POR SISTEMA DE IA — PARA FINS DE APOIO E RASCUNHO. "
        "Deve ser revisto e validado por advogado antes de ser submetido a qualquer tribunal."
    )


# Templates por tipo de documento
_TEMPLATES: dict[TipoDocumento, str] = {

TipoDocumento.PETICAO_INICIAL: """
EXMO(A). SENHOR(A) JUIZ(A) DE DIREITO DO TRIBUNAL COMPETENTE

{nome_autor}, [nacionalidade, estado civil, profissão], residente em [morada completa],
vem, mui respeitosamente, intentar a presente

ACÇÃO [DECLARATIVA / EXECUTIVA] DE [PROCESSO COMUM / ESPECIAL]

contra

{nome_reu}, [identificação do réu], com domicílio em [morada],

com os seguintes fundamentos:

I. DOS FACTOS

{factos_numerados}

II. DO DIREITO APLICÁVEL

{normas_aplicadas}

III. DA ANÁLISE JURÍDICA

{analise}

IV. DO PEDIDO

Nestes termos e nos mais de direito que V. Exa. suprirá, requer-se que seja a presente acção
julgada procedente por provada, e em consequência:

{pedidos}

V. DO VALOR DA CAUSA

O valor da causa é de € [VALOR], nos termos do artigo 296.º do Código de Processo Civil.

VI. DOS MEIOS DE PROVA

Requer-se a inquirição das seguintes testemunhas: [identificação das testemunhas]
Juntam-se os seguintes documentos: [lista de documentos]

[Localidade], {data}

O(A) Mandatário(a) / O(A) Autor(a)
[Assinatura]
""",

TipoDocumento.QUEIXA_CRIME: """
EXMO(A). SENHOR(A) PROCURADOR(A) DO MINISTÉRIO PÚBLICO / ÓRGÃO DE POLÍCIA CRIMINAL

{nome_autor}, [nacionalidade, estado civil, profissão], portador(a) do Bilhete de Identidade / Cartão de Cidadão n.º [número], residente em [morada],

vem apresentar

QUEIXA-CRIME

contra

{nome_reu}, [identificação do arguido], por factos que constituem ilícito criminal, nos seguintes termos:

I. DOS FACTOS

{factos_numerados}

II. DO ENQUADRAMENTO JURÍDICO-CRIMINAL

{normas_aplicadas}

{analise}

III. DO PEDIDO

Requer-se que, com base nos factos acima expostos, seja instaurado o competente procedimento criminal contra o arguido, pugnando-se pelo seu julgamento e consequente condenação nos termos legais aplicáveis.

IV. DOS MEIOS DE PROVA

[Indicação dos meios de prova disponíveis]

[Localidade], {data}

O(A) Queixoso(a)
[Assinatura]
""",

TipoDocumento.CONTESTACAO: """
EXMO(A). SENHOR(A) JUIZ(A) DE DIREITO

{nome_autor} (Réu/Ré), já identificado(a) nos autos, vem, nos termos do artigo 569.º do Código de Processo Civil, apresentar a sua

CONTESTAÇÃO

com os seguintes fundamentos:

I. DA IMPUGNAÇÃO DOS FACTOS

{factos_numerados}

II. DO DIREITO APLICÁVEL EM DEFESA

{normas_aplicadas}

III. DA ANÁLISE DA DEFESA

{analise}

IV. DA EXCEPÇÃO / RECONVENÇÃO (se aplicável)

[Indicar excepções ou pedido reconvencional]

V. DO PEDIDO

Nestes termos, requer-se que a presente contestação seja julgada procedente, absolvendo-se o(a) Réu/Ré do pedido.

[Localidade], {data}

O(A) Mandatário(a) / O(A) Réu(Ré)
[Assinatura]
""",

TipoDocumento.RECURSO: """
EXMO(A). SENHOR(A) JUIZ(A) DESEMBARGADOR(A) / CONSELHEIRO(A)

{nome_autor}, Recorrente, vem interpor o presente

RECURSO [DE APELAÇÃO / DE REVISTA]

da decisão proferida, com os seguintes fundamentos:

I. DO OBJECTO DO RECURSO

A decisão recorrida incorreu em erro de julgamento, nos seguintes termos:

II. DOS FACTOS INCORRECTAMENTE JULGADOS

{factos_numerados}

III. DO DIREITO VIOLADO

{normas_aplicadas}

{analise}

IV. DAS CONCLUSÕES

[Conclusões numeradas — obrigatório para recurso]

V. DO PEDIDO

Requer-se que o presente recurso seja julgado procedente, revogando-se a decisão recorrida.

[Localidade], {data}

O(A) Mandatário(a)
[Assinatura]
""",
}


class GeradorDocumentos:
    """
    Gera documentos jurídicos estruturados.
    Funciona sem LLM usando templates profissionais.
    """

    def gerar(
        self,
        tipo: TipoDocumento,
        resultado: ResultadoReasoning,
        nome_autor: str = "[NOME DO AUTOR]",
        nome_reu: str = "[NOME DO RÉU/ARGUIDO]",
    ) -> DocumentoGerado:

        template = _TEMPLATES.get(tipo, _TEMPLATES[TipoDocumento.PETICAO_INICIAL])

        # Formata factos numerados
        factos_num = "\n".join(
            f"{i+1}. {f.descricao}"
            for i, f in enumerate(resultado.factos)
        ) or "1. [Descrever os factos relevantes do caso]"

        # Formata normas aplicadas
        normas_txt = "\n".join(
            f"• Artigo {n.artigo}.º do {n.diploma}"
            + (f" — {n.epigrase}" if n.epigrase else "")
            for n in resultado.normas[:5]
        ) or "[Indicar as normas aplicáveis]"

        # Selecciona análise conforme posição
        if tipo == TipoDocumento.CONTESTACAO:
            analise_txt = "\n".join(
                f"• {a.argumento}"
                for a in resultado.argumentos_defesa[:3]
            ) or resultado.analise
        elif tipo == TipoDocumento.QUEIXA_CRIME:
            analise_txt = "\n".join(
                f"• {a.argumento}"
                for a in resultado.argumentos_acusacao[:3]
            ) or resultado.analise
        else:
            analise_txt = resultado.analise or "[Análise jurídica a completar]"

        conteudo = template.format(
            nome_autor=nome_autor,
            nome_reu=nome_reu,
            factos_numerados=factos_num,
            normas_aplicadas=normas_txt,
            analise=analise_txt,
            pedidos=resultado.conclusao or "[Formular os pedidos concretos]",
            data=datetime.now(timezone.utc).strftime("%d de %B de %Y"),
        )

        return DocumentoGerado(
            tipo=tipo,
            titulo=f"{tipo.value.replace('_', ' ').title()} — Caso {resultado.caso_id[:8]}",
            conteudo=conteudo.strip(),
            data_geracao=datetime.now(timezone.utc),
            caso_id=resultado.caso_id,
        )

    def tipos_disponiveis(self, tipo_processo: TipoProcesso) -> list[TipoDocumento]:
        """Sugere tipos de documento adequados para o tipo de processo."""
        mapa = {
            TipoProcesso.LABORAL:       [TipoDocumento.PETICAO_INICIAL, TipoDocumento.CONTESTACAO],
            TipoProcesso.PENAL:         [TipoDocumento.QUEIXA_CRIME, TipoDocumento.CONTESTACAO],
            TipoProcesso.CIVIL:         [TipoDocumento.PETICAO_INICIAL, TipoDocumento.CONTESTACAO, TipoDocumento.RECURSO],
            TipoProcesso.DADOS_PESSOAIS:[TipoDocumento.EXPOSICAO, TipoDocumento.REQUERIMENTO],
            TipoProcesso.FAMILIA:       [TipoDocumento.PETICAO_INICIAL, TipoDocumento.REQUERIMENTO],
            TipoProcesso.ADMINISTRATIVO:[TipoDocumento.REQUERIMENTO, TipoDocumento.RECURSO],
        }
        return mapa.get(tipo_processo, [TipoDocumento.REQUERIMENTO, TipoDocumento.PETICAO_INICIAL])
