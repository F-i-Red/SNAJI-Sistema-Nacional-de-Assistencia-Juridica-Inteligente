"""
Testes de autenticação e controlo de acesso do SNAJI.
Testam comportamento real, não apenas que as classes existem.
"""
import pytest
from app.security.rbac import RBACManager, Role, Permissao
from app.security.passwords import criar_hash, verificar_password
from app.db.utilizadores import RepositorioUtilizadores


class TestRBAC:

    def setup_method(self):
        self.rbac = RBACManager()

    def test_admin_tem_acesso_total(self):
        assert self.rbac.tem_permissao(Role.ADMIN, Permissao.SUBMETER_CASO)
        assert self.rbac.tem_permissao(Role.ADMIN, Permissao.VER_AUDITORIA_COMPLETA)
        assert self.rbac.tem_permissao(Role.ADMIN, Permissao.GERIR_UTILIZADORES)

    def test_cidadao_pode_submeter_caso(self):
        assert self.rbac.tem_permissao(Role.CIDADAO, Permissao.SUBMETER_CASO)

    def test_cidadao_nao_pode_ver_auditoria_completa(self):
        assert not self.rbac.tem_permissao(Role.CIDADAO, Permissao.VER_AUDITORIA_COMPLETA)

    def test_cidadao_nao_pode_gerir_utilizadores(self):
        assert not self.rbac.tem_permissao(Role.CIDADAO, Permissao.GERIR_UTILIZADORES)

    def test_magistrado_pode_ver_auditoria_completa(self):
        assert self.rbac.tem_permissao(Role.MAGISTRADO, Permissao.VER_AUDITORIA_COMPLETA)

    def test_advogado_nao_pode_ver_qualquer_caso(self):
        assert not self.rbac.tem_permissao(Role.ADVOGADO, Permissao.LER_CASO_QUALQUER)

    def test_role_desconhecido_nega_sempre(self):
        assert not self.rbac.tem_permissao("role_falso", Permissao.SUBMETER_CASO)

    def test_permissao_desconhecida_nega_sempre(self):
        assert not self.rbac.tem_permissao(Role.ADMIN, "permissao_falsa")

    def test_permissoes_do_role_nao_vazio(self):
        perms = self.rbac.permissoes_do_role(Role.MAGISTRADO)
        assert len(perms) > 0

    def test_permissoes_cidadao_menos_que_magistrado(self):
        p_cidadao = self.rbac.permissoes_do_role(Role.CIDADAO)
        p_magistrado = self.rbac.permissoes_do_role(Role.MAGISTRADO)
        assert len(p_cidadao) < len(p_magistrado)


class TestPasswords:

    def test_hash_nao_e_plaintext(self):
        h = criar_hash("MinhaPassword123!")
        assert h != "MinhaPassword123!"

    def test_verificacao_correcta(self):
        h = criar_hash("MinhaPassword123!")
        assert verificar_password("MinhaPassword123!", h) is True

    def test_verificacao_errada(self):
        h = criar_hash("MinhaPassword123!")
        assert verificar_password("PasswordErrada!", h) is False

    def test_dois_hashes_diferentes_para_mesma_password(self):
        # bcrypt inclui salt automático
        h1 = criar_hash("MinhaPassword123!")
        h2 = criar_hash("MinhaPassword123!")
        assert h1 != h2

    def test_password_curta_rejeitada(self):
        with pytest.raises(ValueError):
            criar_hash("curta")

    def test_hash_invalido_nao_explode(self):
        assert verificar_password("qualquer", "hash_invalido") is False


class TestRepositorioUtilizadores:

    def setup_method(self):
        # Repositório fresco para cada teste
        self.repo = RepositorioUtilizadores()

    def test_utilizadores_demo_criados(self):
        assert self.repo.por_email("admin@snaji.gov.pt") is not None
        assert self.repo.por_email("cidadao@snaji.gov.pt") is not None

    def test_login_correcto(self):
        u = self.repo.autenticar("admin@snaji.gov.pt", "Admin2024!")
        assert u is not None
        assert u.role == Role.ADMIN

    def test_login_password_errada(self):
        u = self.repo.autenticar("admin@snaji.gov.pt", "PasswordErrada!")
        assert u is None

    def test_login_email_inexistente(self):
        u = self.repo.autenticar("naoexiste@snaji.gov.pt", "qualquer")
        assert u is None

    def test_criar_utilizador(self):
        u = self.repo.criar(
            email="novo@snaji.gov.pt",
            nome="Novo Utilizador",
            role=Role.CIDADAO,
            password="Password@2024!",
        )
        assert u.id is not None
        assert u.role == Role.CIDADAO

    def test_email_duplicado_rejeitado(self):
        self.repo.criar("dup@snaji.gov.pt", "X", Role.CIDADAO, "Password@2024!")
        with pytest.raises(ValueError):
            self.repo.criar("dup@snaji.gov.pt", "Y", Role.CIDADAO, "Password@2024!")

    def test_roles_dos_utilizadores_demo(self):
        assert self.repo.por_email("magistrado@snaji.gov.pt").role == Role.MAGISTRADO
        assert self.repo.por_email("advogado@snaji.gov.pt").role == Role.ADVOGADO
        assert self.repo.por_email("analista@snaji.gov.pt").role == Role.ANALISTA
