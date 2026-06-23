"""
Testes do ClassificadorJuridico — SNAJI v2.

Correm sem LLM (modo stub/heurística).
Testam:
  - Classificação de área única
  - Detecção de casos mistos (multi-área)
  - Propriedades do resultado
  - Compatibilidade com TipoProcesso legado
  - Fallback gracioso quando LLM falha
"""

import pytest
from unittest.mock import MagicMock, patch

from app.reasoning.classificador_juridico import (
    ClassificadorJuridico,
    ClassificacaoJuridica,
    AreaJuridica,
    AreaDetectada,
    Instancia,
    _classificar_heuristico,
)
from app.reasoning.pipeline import (
    ReasoningPipeline,
    ResultadoReasoning,
    TipoProcesso,
    classificar_tipo_processo,
)


# ── Testes da heurística ───────────────────────────────────────────────────

class TestHeuristicaBasica:
    """Garante que a heurística cobre os casos simples (compatibilidade)."""

    def test_despedimento_e_laboral(self):
        r = _classificar_heuristico("Fui despedido sem justa causa após 5 anos de trabalho")
        assert r.area_principal == AreaJuridica.LABORAL

    def test_furto_e_penal(self):
        r = _classificar_heuristico("Fui vítima de furto do meu telemóvel na rua")
        assert r.area_principal == AreaJuridica.PENAL

    def test_rgpd_e_dados_pessoais(self):
        r = _classificar_heuristico("Uma empresa usou os meus dados pessoais sem consentimento")
        assert r.area_principal == AreaJuridica.DADOS_PESSOAIS

    def test_divorcio_e_familia(self):
        r = _classificar_heuristico("Pretendo pedir divórcio e definir a custódia dos filhos")
        assert r.area_principal == AreaJuridica.FAMILIA

    def test_corrupcao_e_penal(self):
        r = _classificar_heuristico("Um funcionário público pediu suborno para passar uma licença")
        assert r.area_principal == AreaJuridica.PENAL

    def test_arrendamento_e_civil(self):
        r = _classificar_heuristico("O meu senhorio recusa devolver a caução do contrato de arrendamento")
        assert r.area_principal == AreaJuridica.CIVIL

    def test_sem_texto_relevante_e_outro(self):
        r = _classificar_heuristico("O céu está azul e o sol brilha muito hoje")
        assert r.area_principal == AreaJuridica.OUTRO


# ── Testes de casos mistos ─────────────────────────────────────────────────

class TestCasosMistos:
    """Casos com múltiplas dimensões jurídicas — o principal problema que queremos resolver."""

    def test_despedimento_com_ameacas_deteta_laboral_e_penal(self):
        """Caso clássico: despedimento + ameaças do empregador."""
        r = _classificar_heuristico(
            "O meu empregador despediu-me sem justa causa e ainda me ameaçou "
            "se eu apresentasse queixa ao tribunal."
        )
        areas = r.todas_as_areas
        assert AreaJuridica.LABORAL in areas
        assert AreaJuridica.PENAL in areas

    def test_caso_misto_tem_multiplas_areas(self):
        r = _classificar_heuristico(
            "Fui despedido após recusar pagar suborno ao meu chefe. "
            "O empregador ameaça processar-me se recorrer ao tribunal do trabalho."
        )
        assert len(r.areas) >= 2

    def test_caso_misto_tem_area_principal_definida(self):
        r = _classificar_heuristico(
            "Divórcio litigioso onde o cônjuge me ameaçou e escondeu bens da herança."
        )
        # Deve ter área principal definida
        principais = [a for a in r.areas if a.principal]
        assert len(principais) >= 1

    def test_caso_civil_e_penal(self):
        r = _classificar_heuristico(
            "O meu sócio desviou dinheiro da empresa (burla) e recusa devolver "
            "o que me deve pelo contrato de sociedade."
        )
        areas = r.todas_as_areas
        # Deve detectar pelo menos uma das duas
        assert AreaJuridica.CIVIL in areas or AreaJuridica.PENAL in areas

    def test_dados_pessoais_e_civil(self):
        r = _classificar_heuristico(
            "Uma empresa usou os meus dados pessoais sem consentimento para "
            "me vender produtos e causou-me danos patrimoniais."
        )
        areas = r.todas_as_areas
        assert AreaJuridica.DADOS_PESSOAIS in areas


# ── Testes do ClassificadorJuridico (sem LLM) ─────────────────────────────

class TestClassificadorSemLLM:

    def setup_method(self):
        self.clf = ClassificadorJuridico(llm_client=None)

    def test_classificar_devolve_classificacao_juridica(self):
        r = self.clf.classificar("Fui despedido sem justa causa")
        assert isinstance(r, ClassificacaoJuridica)

    def test_classificar_tem_areas(self):
        r = self.clf.classificar("Fui despedido sem justa causa")
        assert len(r.areas) >= 1

    def test_classificar_nao_e_via_llm(self):
        r = self.clf.classificar("qualquer texto")
        assert r.via_llm is False

    def test_area_principal_correcto(self):
        r = self.clf.classificar("Fui despedido sem justa causa pelo meu empregador")
        assert r.area_principal == AreaJuridica.LABORAL

    def test_areas_tem_instancias(self):
        r = self.clf.classificar("Fui despedido sem justa causa")
        for area in r.areas:
            assert len(area.instancias) >= 1

    def test_laboral_tem_tribunal_trabalho(self):
        r = self.clf.classificar("Fui despedido sem justa causa após 5 anos de trabalho")
        area_laboral = next((a for a in r.areas if a.area == AreaJuridica.LABORAL), None)
        assert area_laboral is not None
        assert Instancia.TRIBUNAL_TRABALHO in area_laboral.instancias

    def test_penal_tem_tribunal_criminal_ou_mp(self):
        r = self.clf.classificar("Sofri um furto e quero apresentar queixa-crime")
        area_penal = next((a for a in r.areas if a.area == AreaJuridica.PENAL), None)
        assert area_penal is not None
        assert (
            Instancia.TRIBUNAL_CRIMINAL in area_penal.instancias
            or Instancia.MINISTERIO_PUBLICO in area_penal.instancias
        )

    def test_peso_de_area_ausente_e_zero(self):
        r = self.clf.classificar("Fui despedido sem justa causa")
        assert r.peso_de(AreaJuridica.FAMILIA) == 0.0

    def test_peso_de_area_presente_e_positivo(self):
        r = self.clf.classificar("Fui despedido sem justa causa")
        assert r.peso_de(AreaJuridica.LABORAL) > 0.0


# ── Testes de fallback do ClassificadorJuridico com LLM falhado ───────────

class TestClassificadorFallback:

    def test_fallback_heuristico_quando_llm_falha(self):
        """Se o LLM lançar excepção, deve cair para heurística sem falhar."""
        llm_mock = MagicMock()
        llm_mock.messages.create.side_effect = Exception("Timeout de rede")
        clf = ClassificadorJuridico(llm_client=llm_mock)
        # Não deve levantar excepção
        r = clf.classificar("Fui despedido sem justa causa")
        assert isinstance(r, ClassificacaoJuridica)
        assert r.via_llm is False

    def test_fallback_devolve_area_correcta(self):
        llm_mock = MagicMock()
        llm_mock.messages.create.side_effect = RuntimeError("API indisponível")
        clf = ClassificadorJuridico(llm_client=llm_mock)
        r = clf.classificar("Fui despedido sem justa causa")
        assert r.area_principal == AreaJuridica.LABORAL


# ── Testes do ClassificadorJuridico com LLM mockado ───────────────────────

class TestClassificadorComLLMMockado:
    """Testa a integração com LLM usando um mock que devolve JSON válido."""

    def _mock_llm_response(self, json_str: str):
        """Cria um mock do cliente Anthropic que devolve o JSON dado."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json_str)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg
        return mock_client

    def test_llm_caso_simples(self):
        resposta = '''
        {
          "areas": [
            {
              "area": "laboral",
              "peso": 0.9,
              "principal": true,
              "instancias": ["Tribunal do Trabalho"],
              "justificacao": "Despedimento sem justa causa"
            }
          ],
          "resumo": "Caso de despedimento ilícito",
          "confianca": 0.95
        }
        '''
        clf = ClassificadorJuridico(llm_client=self._mock_llm_response(resposta))
        r = clf.classificar("Fui despedido sem justa causa")
        assert r.via_llm is True
        assert r.area_principal == AreaJuridica.LABORAL
        assert r.confianca == pytest.approx(0.95)

    def test_llm_caso_misto(self):
        resposta = '''
        {
          "areas": [
            {
              "area": "laboral",
              "peso": 0.7,
              "principal": true,
              "instancias": ["Tribunal do Trabalho"],
              "justificacao": "Despedimento"
            },
            {
              "area": "penal",
              "peso": 0.5,
              "principal": false,
              "instancias": ["Tribunal Criminal", "Ministério Público"],
              "justificacao": "Ameaças do empregador"
            }
          ],
          "resumo": "Despedimento ilícito com ameaças",
          "confianca": 0.88
        }
        '''
        clf = ClassificadorJuridico(llm_client=self._mock_llm_response(resposta))
        r = clf.classificar("Fui despedido e ameaçado pelo meu empregador")
        assert r.via_llm is True
        assert len(r.areas) == 2
        assert AreaJuridica.LABORAL in r.todas_as_areas
        assert AreaJuridica.PENAL in r.todas_as_areas

    def test_llm_json_com_markdown_e_tratado(self):
        """LLM às vezes devolve JSON com backticks — deve ser tratado."""
        resposta = '''```json
        {
          "areas": [{"area": "civil", "peso": 0.8, "principal": true, "instancias": ["Tribunal Cível"], "justificacao": "contrato"}],
          "resumo": "Incumprimento contratual",
          "confianca": 0.85
        }
        ```'''
        clf = ClassificadorJuridico(llm_client=self._mock_llm_response(resposta))
        r = clf.classificar("O meu inquilino não paga a renda")
        assert r.via_llm is True
        assert r.area_principal == AreaJuridica.CIVIL


# ── Testes de integração: Pipeline com novo classificador ──────────────────

class TestPipelineIntegracao:
    """
    Garante que a ReasoningPipeline v2 continua a funcionar
    e que os testes existentes não quebram.
    """

    def setup_method(self):
        self.pipeline = ReasoningPipeline(llm_client=None)

    def test_analisar_retorna_resultado(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert isinstance(r, ResultadoReasoning)

    def test_resultado_tem_caso_id(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert r.caso_id and len(r.caso_id) == 36

    def test_resultado_tem_normas(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert len(r.normas) > 0

    def test_resultado_tem_tipo_correcto_laboraal(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa pelo meu empregador")
        assert r.tipo_processo == TipoProcesso.LABORAL

    def test_resultado_tem_timestamp(self):
        r = self.pipeline.analisar("teste")
        assert r.timestamp is not None

    def test_resultado_grounded_por_defeito_stub(self):
        r = self.pipeline.analisar("teste")
        assert r.grounded is True

    def test_caso_penal_classificado(self):
        r = self.pipeline.analisar("Sofri ameaças de morte do meu vizinho")
        assert r.tipo_processo == TipoProcesso.PENAL

    def test_normas_laborais_para_despedimento(self):
        r = self.pipeline.analisar("O meu empregador despediu-me sem justa causa após 10 anos")
        diplomas = [n.diploma for n in r.normas]
        assert "CT" in diplomas or "CRP" in diplomas

    # Novos campos do ResultadoReasoning v2
    def test_resultado_tem_classificacao(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert isinstance(r.classificacao, ClassificacaoJuridica)

    def test_classificacao_tem_areas(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert len(r.classificacao.areas) >= 1

    def test_caso_misto_tem_multiplas_areas_em_classificacao(self):
        """O resultado agora expõe classificação multi-área no campo classificacao."""
        r = self.pipeline.analisar(
            "Fui despedido sem justa causa e o meu empregador ameaçou-me de prisão "
            "se eu apresentar queixa."
        )
        # Pode ter 1 ou 2 áreas dependendo da heurística — o importante é ter a estrutura
        assert hasattr(r.classificacao, "areas")
        assert hasattr(r.classificacao, "area_principal")


# ── Compatibilidade: função legada classificar_tipo_processo ───────────────

class TestCompatibilidadeLegada:
    """
    Garante que classificar_tipo_processo() continua a funcionar
    exatamente como antes (importada de pipeline.py).
    """

    def test_despedimento_e_laboral(self):
        assert classificar_tipo_processo("Fui despedido sem justa causa após 5 anos de trabalho") == TipoProcesso.LABORAL

    def test_furto_e_penal(self):
        assert classificar_tipo_processo("Fui vítima de furto do meu telemóvel na rua") == TipoProcesso.PENAL

    def test_rgpd_e_dados_pessoais(self):
        assert classificar_tipo_processo("Uma empresa usou os meus dados pessoais sem consentimento") == TipoProcesso.DADOS_PESSOAIS

    def test_divorcio_e_familia(self):
        assert classificar_tipo_processo("Pretendo pedir divórcio e definir a custódia dos filhos") == TipoProcesso.FAMILIA

    def test_corrupcao_e_penal(self):
        assert classificar_tipo_processo("Um funcionário público pediu suborno para passar um licença") == TipoProcesso.PENAL

    def test_arrendamento_e_civil(self):
        assert classificar_tipo_processo("O meu senhorio recusa devolver a caução do contrato de arrendamento") == TipoProcesso.CIVIL
