"""
Testes do reasoning pipeline e gerador de documentos.
Correm sem LLM — testam tudo o que é determinístico.
"""
import pytest
from app.reasoning.pipeline import (
    ReasoningPipeline, classificar_tipo_processo,
    TipoProcesso, ResultadoReasoning,
)
from app.generation.gerador import GeradorDocumentos, TipoDocumento


class TestClassificacao:

    def test_despedimento_e_laboral(self):
        assert classificar_tipo_processo(
            "Fui despedido sem justa causa após 5 anos de trabalho"
        ) == TipoProcesso.LABORAL

    def test_furto_e_penal(self):
        assert classificar_tipo_processo(
            "Fui vítima de furto do meu telemóvel na rua"
        ) == TipoProcesso.PENAL

    def test_rgpd_e_dados_pessoais(self):
        assert classificar_tipo_processo(
            "Uma empresa usou os meus dados pessoais sem consentimento"
        ) == TipoProcesso.DADOS_PESSOAIS

    def test_divorcio_e_familia(self):
        assert classificar_tipo_processo(
            "Pretendo pedir divórcio e definir a custódia dos filhos"
        ) == TipoProcesso.FAMILIA

    def test_corrupção_e_penal(self):
        assert classificar_tipo_processo(
            "Um funcionário público pediu suborno para passar um licença"
        ) == TipoProcesso.PENAL

    def test_arrendamento_e_civil(self):
        assert classificar_tipo_processo(
            "O meu senhorio recusa devolver a caução do contrato de arrendamento"
        ) == TipoProcesso.CIVIL


class TestReasoningPipeline:

    def setup_method(self):
        # Sem LLM — modo stub determinístico
        self.pipeline = ReasoningPipeline(llm_client=None)

    def test_analisar_retorna_resultado(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert isinstance(r, ResultadoReasoning)

    def test_resultado_tem_caso_id(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert r.caso_id and len(r.caso_id) == 36  # UUID formato

    def test_resultado_tem_normas(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa")
        assert len(r.normas) > 0

    def test_resultado_tem_tipo_correcto(self):
        r = self.pipeline.analisar("Fui despedido sem justa causa pelo meu empregador")
        assert r.tipo_processo == TipoProcesso.LABORAL

    def test_resultado_tem_timestamp(self):
        r = self.pipeline.analisar("teste")
        assert r.timestamp is not None

    def test_resultado_grounded_por_defeito_stub(self):
        # Stub não cita artigos, por isso grounded é True (sem suspeitas)
        r = self.pipeline.analisar("teste")
        assert r.grounded is True

    def test_caso_penal_classificado(self):
        r = self.pipeline.analisar("Sofri ameaças de morte do meu vizinho")
        assert r.tipo_processo == TipoProcesso.PENAL

    def test_normas_laborais_para_despedimento(self):
        r = self.pipeline.analisar("O meu empregador despediu-me sem justa causa após 10 anos")
        diplomas = [n.diploma for n in r.normas]
        assert "CT" in diplomas or "CRP" in diplomas


class TestGeradorDocumentos:

    def setup_method(self):
        self.pipeline = ReasoningPipeline(llm_client=None)
        self.gerador = GeradorDocumentos()

    def _resultado_laboral(self) -> ResultadoReasoning:
        return self.pipeline.analisar(
            "Fui despedido sem justa causa após 8 anos de serviço. "
            "O meu empregador recusa pagar a indemnização devida."
        )

    def test_gerar_peticao_inicial(self):
        r = self._resultado_laboral()
        doc = self.gerador.gerar(TipoDocumento.PETICAO_INICIAL, r, "João Silva", "Empresa XYZ Lda")
        assert doc.conteudo
        assert "EXMO" in doc.conteudo
        assert doc.tipo == TipoDocumento.PETICAO_INICIAL

    def test_documento_tem_advertencia(self):
        r = self._resultado_laboral()
        doc = self.gerador.gerar(TipoDocumento.PETICAO_INICIAL, r)
        assert "IA" in doc.advertencia

    def test_documento_tem_caso_id(self):
        r = self._resultado_laboral()
        doc = self.gerador.gerar(TipoDocumento.PETICAO_INICIAL, r)
        assert doc.caso_id == r.caso_id

    def test_tipos_disponiveis_laboral(self):
        tipos = self.gerador.tipos_disponiveis(TipoProcesso.LABORAL)
        assert TipoDocumento.PETICAO_INICIAL in tipos

    def test_tipos_disponiveis_penal(self):
        tipos = self.gerador.tipos_disponiveis(TipoProcesso.PENAL)
        assert TipoDocumento.QUEIXA_CRIME in tipos

    def test_gerar_queixa_crime(self):
        r = self.pipeline.analisar("Fui ameaçado de morte pelo meu vizinho")
        doc = self.gerador.gerar(TipoDocumento.QUEIXA_CRIME, r, "Vítima", "Arguido")
        assert "QUEIXA-CRIME" in doc.conteudo

    def test_contestacao_usa_argumentos_defesa(self):
        r = self._resultado_laboral()
        doc = self.gerador.gerar(TipoDocumento.CONTESTACAO, r, "Empresa XYZ", "João Silva")
        assert "CONTESTAÇÃO" in doc.conteudo
