"""
Testes de integração end-to-end do SNAJI.

Testam o sistema de ponta a ponta sem LLM:
- Login → Token → Acesso autenticado
- Upload de documento → Análise automática
- Criação de processo → Avanço de fases
- Geração de documento jurídico
- Controlo de acesso por papel
"""
import pytest
import os

# Variáveis de ambiente mínimas para testes
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-nao-usada")
os.environ.setdefault("JWT_SECRET", "test-secret-para-testes-unitarios-snaji")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def login(email: str, password: str) -> str:
    """Faz login e devolve o token."""
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login falhou: {r.json()}"
    return r.json()["access_token"]

def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["sistema"] == "SNAJI"


# ── Autenticação ─────────────────────────────────────────────────────────────

class TestAutenticacao:

    def test_login_cidadao_ok(self):
        token = login("cidadao@snaji.gov.pt", "Cidad2024!")
        assert token.startswith("ey")  # JWT começa sempre com "ey"

    def test_login_magistrado_ok(self):
        token = login("magistrado@snaji.gov.pt", "Magis2024!")
        assert token

    def test_login_password_errada(self):
        r = client.post("/api/v1/auth/login", json={"email": "admin@snaji.gov.pt", "password": "errada"})
        assert r.status_code == 401

    def test_login_email_inexistente(self):
        r = client.post("/api/v1/auth/login", json={"email": "nao@existe.pt", "password": "qualquer"})
        assert r.status_code == 401

    def test_me_com_token(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.get("/api/v1/auth/me", headers=headers(token))
        assert r.status_code == 200
        assert r.json()["role"] == "advogado"

    def test_me_sem_token(self):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_token_invalido_rejeitado(self):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token_falso"})
        assert r.status_code == 401

    def test_roles_publico(self):
        r = client.get("/api/v1/auth/roles")
        assert r.status_code == 200
        roles = [item["papel"] for item in r.json()["roles"]]
        assert "cidadao" in roles
        assert "magistrado" in roles


# ── Fontes jurídicas ──────────────────────────────────────────────────────────

class TestFontes:

    def test_listar_fontes_autenticado(self):
        token = login("cidadao@snaji.gov.pt", "Cidad2024!")
        r = client.get("/api/v1/fontes", headers=headers(token))
        assert r.status_code == 200
        assert r.json()["total_artigos"] == 246

    def test_listar_fontes_sem_token(self):
        r = client.get("/api/v1/fontes")
        assert r.status_code == 401


# ── Processos ─────────────────────────────────────────────────────────────────

class TestProcessos:

    def test_listar_processos_autenticado(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.get("/api/v1/processos", headers=headers(token))
        assert r.status_code == 200
        assert "processos" in r.json()
        assert "total" in r.json()
        # Processos demo devem existir
        assert r.json()["total"] > 0

    def test_listar_processos_sem_token(self):
        r = client.get("/api/v1/processos")
        assert r.status_code == 401

    def test_criar_processo(self):
        token = login("cidadao@snaji.gov.pt", "Cidad2024!")
        r = client.post("/api/v1/processos", json={
            "tipo": "laboral",
            "descricao": "Teste de criação de processo via API",
            "nome_autor": "Teste Autor",
            "nome_reu": "Teste Réu",
            "comarca": "Porto",
        }, headers=headers(token))
        assert r.status_code == 200
        assert "id" in r.json()
        assert "numero" in r.json()
        assert r.json()["estado"] == "Apresentação"

    def test_ver_processo_existente(self):
        token = login("magistrado@snaji.gov.pt", "Magis2024!")
        # Primeiro lista para obter um ID
        lista = client.get("/api/v1/processos", headers=headers(token)).json()
        pid = lista["processos"][0]["id"]
        r = client.get(f"/api/v1/processos/{pid}", headers=headers(token))
        assert r.status_code == 200
        assert r.json()["id"] == pid
        assert "eventos" in r.json()
        assert "prazos" in r.json()

    def test_ver_processo_inexistente(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.get("/api/v1/processos/id-que-nao-existe", headers=headers(token))
        assert r.status_code == 404

    def test_avancar_processo(self):
        token = login("magistrado@snaji.gov.pt", "Magis2024!")
        # Cria processo novo
        criado = client.post("/api/v1/processos", json={
            "tipo": "civil", "descricao": "Processo para testar avanço",
            "nome_autor": "A", "nome_reu": "B",
        }, headers=headers(token)).json()
        pid = criado["id"]
        # Avança
        r = client.post(f"/api/v1/processos/{pid}/avancar",
                        data={"nota": "Avanço de teste"}, headers=headers(token))
        assert r.status_code == 200
        assert r.json()["estado"] == "Citação"


# ── Geração de documentos ─────────────────────────────────────────────────────

class TestGeracao:

    def test_gerar_peticao_inicial(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.post("/api/v1/gerar-documento", json={
            "tipo": "peticao_inicial",
            "texto_caso": "Fui despedido sem justa causa após 5 anos de serviço.",
            "nome_autor": "João Silva",
            "nome_reu": "Empresa ABC Lda",
        }, headers=headers(token))
        assert r.status_code == 200
        assert "conteudo" in r.json()
        assert "EXMO" in r.json()["conteudo"]
        assert "advertencia" in r.json()
        assert "IA" in r.json()["advertencia"]

    def test_gerar_queixa_crime(self):
        token = login("cidadao@snaji.gov.pt", "Cidad2024!")
        r = client.post("/api/v1/gerar-documento", json={
            "tipo": "queixa_crime",
            "texto_caso": "Fui ameaçado de morte pelo meu vizinho. Tenho mensagens como prova.",
            "nome_autor": "Vítima",
            "nome_reu": "Arguido",
        }, headers=headers(token))
        assert r.status_code == 200
        assert "QUEIXA-CRIME" in r.json()["conteudo"]


# ── Upload de documentos ───────────────────────────────────────────────────────

class TestUpload:

    def test_upload_txt(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        conteudo = b"Fui despedido sem justa causa. Trabalho na empresa ha 5 anos."
        r = client.post(
            "/api/v1/documentos/upload",
            files={"ficheiro": ("teste.txt", conteudo, "text/plain")},
            data={"analisar": "true"},
            headers=headers(token),
        )
        assert r.status_code == 200
        assert r.json()["tipo"] == "txt"
        assert r.json()["num_caracteres"] > 0

    def test_upload_formato_invalido(self):
        token = login("advogado@snaji.gov.pt", "Advog2024!")
        r = client.post(
            "/api/v1/documentos/upload",
            files={"ficheiro": ("teste.exe", b"conteudo", "application/octet-stream")},
            data={"analisar": "false"},
            headers=headers(token),
        )
        assert r.status_code == 400

    def test_upload_sem_token(self):
        r = client.post(
            "/api/v1/documentos/upload",
            files={"ficheiro": ("teste.txt", b"texto", "text/plain")},
            data={"analisar": "false"},
        )
        assert r.status_code == 401
