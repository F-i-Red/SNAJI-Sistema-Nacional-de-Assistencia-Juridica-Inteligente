"""
Testes do motor de workflow processual — Fase 2.
Testam prazos legais, transições válidas/inválidas e notificações.
"""
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-workflow-snaji")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

import pytest
from datetime import datetime, timezone, timedelta

from app.workflow.motor import MotorWorkflow, motor_workflow
from app.processes.repositorio import (
    TipoProcesso, EstadoProcesso, ORDEM_FASES, RepositorioProcessos, Parte
)
from app.notifications.gestor import GestorNotificacoes, NivelAlerta


class TestMotorWorkflow:

    def setup_method(self):
        self.motor = MotorWorkflow()

    def test_calcular_prazos_laboral_apresentacao(self):
        prazos = self.motor.calcular_prazos_fase(TipoProcesso.LABORAL, EstadoProcesso.APRESENTACAO)
        assert len(prazos) > 0
        assert all(pr.data_limite > datetime.now(timezone.utc) for pr in prazos)

    def test_calcular_prazos_penal_tem_base_legal(self):
        prazos = self.motor.calcular_prazos_fase(TipoProcesso.PENAL, EstadoProcesso.CONTESTACAO)
        assert any("CPP" in pr.descricao for pr in prazos)

    def test_calcular_prazos_civil_contestacao(self):
        prazos = self.motor.calcular_prazos_fase(TipoProcesso.CIVIL, EstadoProcesso.CITACAO)
        # CPC Art. 569 — 30 dias úteis para contestação
        assert len(prazos) > 0
        prazo = prazos[0]
        dias = (prazo.data_limite - datetime.now(timezone.utc)).days
        assert dias >= 25  # 30 dias úteis ≈ 42 dias corridos, mas pelo menos 25

    def test_validar_transicao_sequencial_ok(self):
        valido, msg = self.motor.validar_transicao(EstadoProcesso.APRESENTACAO, EstadoProcesso.CITACAO)
        assert valido

    def test_validar_transicao_retrocesso_invalido(self):
        valido, msg = self.motor.validar_transicao(EstadoProcesso.INSTRUCAO, EstadoProcesso.CITACAO)
        assert not valido
        assert "retroceder" in msg.lower()

    def test_validar_transicao_salto_invalido(self):
        valido, msg = self.motor.validar_transicao(EstadoProcesso.APRESENTACAO, EstadoProcesso.JULGAMENTO)
        assert not valido

    def test_validar_arquivamento_sempre_valido(self):
        valido, _ = self.motor.validar_transicao(EstadoProcesso.INSTRUCAO, EstadoProcesso.ARQUIVADO)
        assert valido

    def test_analisar_urgencia_prazo_expirado(self):
        from app.processes.repositorio import Prazo
        prazo_expirado = Prazo(
            descricao="Prazo expirado de teste",
            data_limite=datetime.now(timezone.utc) - timedelta(days=2),
        )
        alertas = self.motor.analisar_urgencia([prazo_expirado])
        assert any("EXPIRADO" in a.upper() for a in alertas)

    def test_analisar_urgencia_prazo_hoje(self):
        from app.processes.repositorio import Prazo
        prazo_hoje = Prazo(
            descricao="Prazo de hoje",
            data_limite=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        alertas = self.motor.analisar_urgencia([prazo_hoje])
        assert any("HOJE" in a.upper() for a in alertas)

    def test_analisar_urgencia_prazo_distante_sem_alerta(self):
        from app.processes.repositorio import Prazo
        prazo_distante = Prazo(
            descricao="Prazo distante",
            data_limite=datetime.now(timezone.utc) + timedelta(days=30),
        )
        alertas = self.motor.analisar_urgencia([prazo_distante])
        assert len(alertas) == 0

    def test_dias_uteis_nao_conta_fim_de_semana(self):
        # Começa numa sexta-feira
        sexta = datetime(2024, 11, 1, tzinfo=timezone.utc)  # sexta-feira
        resultado = self.motor._adicionar_dias_uteis(sexta, 1)
        # 1 dia útil a partir de sexta = segunda-feira
        assert resultado.weekday() == 0  # segunda-feira


class TestGestorNotificacoes:

    def setup_method(self):
        self.gestor = GestorNotificacoes()

    def test_gerar_alerta_prazo_urgente(self):
        from app.processes.repositorio import Prazo
        prazos = [Prazo("Prazo urgente", datetime.now(timezone.utc) + timedelta(days=2), urgente=True)]
        notifs = self.gestor.gerar_alertas_processo("p-001", "2024/0001-L", prazos)
        assert len(notifs) > 0
        assert notifs[0].nivel == NivelAlerta.URGENTE

    def test_gerar_alerta_prazo_expirado(self):
        from app.processes.repositorio import Prazo
        prazos = [Prazo("Prazo expirado", datetime.now(timezone.utc) - timedelta(days=1))]
        notifs = self.gestor.gerar_alertas_processo("p-002", "2024/0002-P", prazos)
        assert len(notifs) > 0
        assert notifs[0].nivel == NivelAlerta.CRITICO

    def test_prazo_distante_sem_notificacao(self):
        from app.processes.repositorio import Prazo
        prazos = [Prazo("Prazo distante", datetime.now(timezone.utc) + timedelta(days=30))]
        notifs = self.gestor.gerar_alertas_processo("p-003", "2024/0003-C", prazos)
        assert len(notifs) == 0

    def test_prazo_cumprido_sem_notificacao(self):
        from app.processes.repositorio import Prazo
        prazos = [Prazo("Prazo cumprido", datetime.now(timezone.utc) - timedelta(days=1), cumprido=True)]
        notifs = self.gestor.gerar_alertas_processo("p-004", "2024/0004-A", prazos)
        assert len(notifs) == 0

    def test_marcar_notificacao_lida(self):
        from app.processes.repositorio import Prazo
        prazos = [Prazo("Teste", datetime.now(timezone.utc) + timedelta(days=1), urgente=True)]
        notifs = self.gestor.gerar_alertas_processo("p-005", "2024/0005-L", prazos)
        nid = notifs[0].id
        ok = self.gestor.marcar_lida(nid)
        assert ok
        nao_lidas = self.gestor.listar(apenas_nao_lidas=True)
        assert all(n.id != nid for n in nao_lidas)

    def test_contar_nao_lidas(self):
        from app.processes.repositorio import Prazo
        prazos = [
            Prazo("Urgente", datetime.now(timezone.utc) + timedelta(days=2), urgente=True),
            Prazo("Critico", datetime.now(timezone.utc) - timedelta(days=1)),
        ]
        self.gestor.gerar_alertas_processo("p-006", "2024/0006-P", prazos)
        contagem = self.gestor.contar_nao_lidas()
        assert contagem["total"] >= 2


class TestWorkflowIntegrado:
    """Testa o workflow integrado com os processos reais."""

    def setup_method(self):
        self.repo = RepositorioProcessos()

    def test_criar_processo_e_avancar_com_prazos(self):
        from app.processes.repositorio import avancar_com_workflow
        # Cria processo
        p = self.repo.criar(
            tipo=TipoProcesso.CIVIL,
            descricao="Teste workflow integrado",
            partes=[Parte("Autor", "autor"), Parte("Réu", "réu")],
            criado_por="user-test",
        )
        assert p.estado == EstadoProcesso.APRESENTACAO
        assert len(p.prazos) == 0

        # Avança com workflow (gera prazos automáticos)
        # Injecta o processo no repo local para o teste
        from app.processes.repositorio import repositorio_processos
        repositorio_processos._processos[p.id] = p

        p_avancado = avancar_com_workflow(p.id, "user-test")
        assert p_avancado.estado == EstadoProcesso.CITACAO
        assert len(p_avancado.prazos) > 0
        # Prazos devem ter base legal
        assert any("CPC" in pr.descricao or "CPP" in pr.descricao or "CT" in pr.descricao
                   for pr in p_avancado.prazos)

    def test_ordem_fases_correcta(self):
        """Verifica que a ordem legal das fases está correcta."""
        assert ORDEM_FASES[0] == EstadoProcesso.APRESENTACAO
        assert ORDEM_FASES[1] == EstadoProcesso.CITACAO
        assert ORDEM_FASES[2] == EstadoProcesso.CONTESTACAO
        assert ORDEM_FASES[4] == EstadoProcesso.JULGAMENTO
        assert ORDEM_FASES[5] == EstadoProcesso.SENTENCA
