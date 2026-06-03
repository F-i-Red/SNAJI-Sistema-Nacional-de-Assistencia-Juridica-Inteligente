"""
Testes reais do SNAJI.
Testam comportamento, não apenas que as funções existem.
"""
import pytest
from app.rag.motor import RAGJuridico, ValidadorCitacoes


class TestRAGJuridico:
    def setup_method(self):
        self.rag = RAGJuridico()

    def test_search_retorna_resultados_para_query_laboral(self):
        resultados = self.rag.search("despedimento sem justa causa trabalhador")
        assert len(resultados) > 0

    def test_search_retorna_crp_artigo_53_para_despedimento(self):
        resultados = self.rag.search("despedimento sem justa causa trabalhador")
        diplomas = [r.diploma for r in resultados]
        artigos = [r.artigo for r in resultados]
        # CRP art. 53 é sobre segurança no emprego — deve estar nos resultados
        assert "CRP" in diplomas
        assert "53" in artigos

    def test_search_retorna_rgpd_para_protecao_dados(self):
        resultados = self.rag.search("dados pessoais consentimento tratamento")
        diplomas = [r.diploma for r in resultados]
        assert "RGPD" in diplomas

    def test_search_scores_sao_positivos(self):
        resultados = self.rag.search("direito propriedade compropriedade")
        for r in resultados:
            assert r.score >= 0.0

    def test_search_top_k_respeitado(self):
        resultados = self.rag.search("qualquer coisa", top_k=3)
        assert len(resultados) <= 3

    def test_search_query_vazia_nao_explode(self):
        resultados = self.rag.search("")
        assert isinstance(resultados, list)


class TestValidadorCitacoes:
    def setup_method(self):
        self.v = ValidadorCitacoes()

    def test_artigo_valido_crp(self):
        assert self.v.validar("CRP", "13") is True

    def test_artigo_invalido_crp(self):
        assert self.v.validar("CRP", "999") is False

    def test_diploma_desconhecido(self):
        assert self.v.validar("DIPLOMA_FALSO", "1") is False

    def test_extrair_citacoes_validas_do_texto(self):
        texto = "Nos termos do Artigo 13.º da CRP e do Artigo 483.º do Código Civil..."
        validas, suspeitas = self.v.extrair_e_validar(texto)
        assert len(validas) == 2
        assert len(suspeitas) == 0

    def test_detectar_citacao_suspeita(self):
        texto = "Conforme o Artigo 999.º da CRP, o cidadão tem direito..."
        validas, suspeitas = self.v.extrair_e_validar(texto)
        assert any(s["artigo"] == "999" for s in suspeitas)

    def test_sem_citacoes_no_texto(self):
        texto = "Este é um texto sem qualquer referência a artigos jurídicos."
        validas, suspeitas = self.v.extrair_e_validar(texto)
        assert validas == []
        assert suspeitas == []
