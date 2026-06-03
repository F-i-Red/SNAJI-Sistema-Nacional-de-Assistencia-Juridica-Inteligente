"""
Integração com a Chave Móvel Digital (CMD) — Fase 4.

A CMD é o sistema de autenticação digital do Estado Português,
gerido pela AMA (Agência para a Modernização Administrativa).

Permite que cidadãos se autentiquem no SNAJI com o seu NIF
e código CMD, sem necessidade de criar conta separada.

Fluxo OAuth2/OIDC:
1. Utilizador clica "Autenticar com CMD"
2. SNAJI redireccionado para login.autenticacao.gov.pt
3. Utilizador autentica-se com NIF + código SMS
4. CMD redireciona para SNAJI com código de autorização
5. SNAJI troca código por token e obtém dados do cidadão

URLs:
- Produção: https://autenticacao.gov.pt
- Sandbox:  https://sandbox.autenticacao.gov.pt (para testes)

Referência: AMA — Especificações CMD OAuth2
https://www.autenticacao.gov.pt/autenticacao-egovernment
"""

from __future__ import annotations
import secrets
import hashlib
import base64
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode
import structlog

logger = structlog.get_logger(__name__)

# URLs da CMD — usar sandbox em desenvolvimento
CMD_BASE_SANDBOX = "https://sandbox.autenticacao.gov.pt"
CMD_BASE_PROD    = "https://autenticacao.gov.pt"

CMD_AUTHORIZE_PATH = "/oauth/askauthorization"
CMD_TOKEN_PATH     = "/oauth/accesstoken"
CMD_USERINFO_PATH  = "/oauth/openid/userinfo"


@dataclass
class ConfigCMD:
    """Configuração da integração CMD."""
    client_id: str
    client_secret: str
    redirect_uri: str
    ambiente: str = "sandbox"  # "sandbox" | "producao"
    scopes: list[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["openid", "profile", "nif"]

    @property
    def base_url(self) -> str:
        return CMD_BASE_PROD if self.ambiente == "producao" else CMD_BASE_SANDBOX


@dataclass
class UtilizadorCMD:
    """Dados do utilizador após autenticação CMD."""
    sub: str            # identificador único CMD
    nif: str            # NIF do cidadão
    nome: str
    email: Optional[str]
    autenticado_em: datetime


@dataclass
class EstadoOAuth:
    """Estado OAuth para prevenir CSRF."""
    state: str
    code_verifier: str
    criado_em: datetime
    redirect_apos: str = "/dashboard"


class GestorCMD:
    """
    Gere o fluxo OAuth2 com PKCE para a Chave Móvel Digital.

    PKCE (Proof Key for Code Exchange) é obrigatório para aplicações
    públicas — garante que o código de autorização só pode ser usado
    pelo cliente que o pediu.
    """

    def __init__(self, config: Optional[ConfigCMD] = None):
        self._config = config
        self._estados: dict[str, EstadoOAuth] = {}  # Em produção: Redis
        logger.info("cmd.gestor.init", ambiente=config.ambiente if config else "não_configurado")

    def _gerar_pkce(self) -> tuple[str, str]:
        """Gera code_verifier e code_challenge para PKCE."""
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b'=').decode()
        return verifier, challenge

    def gerar_url_autorizacao(self, redirect_apos: str = "/dashboard") -> tuple[str, str]:
        """
        Gera a URL para redirecionar o utilizador para a CMD.
        Retorna (url, state) — o state deve ser guardado na sessão.
        """
        if not self._config:
            raise ValueError("CMD não configurada. Defina CMD_CLIENT_ID e CMD_CLIENT_SECRET no .env")

        state = secrets.token_urlsafe(16)
        verifier, challenge = self._gerar_pkce()

        self._estados[state] = EstadoOAuth(
            state=state,
            code_verifier=verifier,
            criado_em=datetime.now(timezone.utc),
            redirect_apos=redirect_apos,
        )

        params = {
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self._config.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }

        url = f"{self._config.base_url}{CMD_AUTHORIZE_PATH}?{urlencode(params)}"
        logger.info("cmd.url_autorizacao_gerada", state=state)
        return url, state

    async def processar_callback(
        self,
        code: str,
        state: str,
    ) -> Optional[UtilizadorCMD]:
        """
        Processa o callback da CMD após autenticação.
        Troca o código por token e obtém dados do cidadão.
        """
        if not self._config:
            raise ValueError("CMD não configurada")

        # Valida o state
        estado = self._estados.pop(state, None)
        if not estado:
            logger.warning("cmd.state_invalido", state=state)
            raise ValueError("State OAuth inválido ou expirado")

        # Verifica que o state não expirou (10 minutos)
        if (datetime.now(timezone.utc) - estado.criado_em).seconds > 600:
            raise ValueError("Sessão OAuth expirada. Tente novamente.")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Troca código por token
                r = await client.post(
                    f"{self._config.base_url}{CMD_TOKEN_PATH}",
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self._config.redirect_uri,
                        "client_id": self._config.client_id,
                        "client_secret": self._config.client_secret,
                        "code_verifier": estado.code_verifier,
                    },
                )
                r.raise_for_status()
                token_data = r.json()
                access_token = token_data["access_token"]

                # Obtém dados do utilizador
                r2 = await client.get(
                    f"{self._config.base_url}{CMD_USERINFO_PATH}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                r2.raise_for_status()
                userinfo = r2.json()

            utilizador = UtilizadorCMD(
                sub=userinfo.get("sub", ""),
                nif=userinfo.get("nif", userinfo.get("tax_number", "")),
                nome=userinfo.get("name", ""),
                email=userinfo.get("email"),
                autenticado_em=datetime.now(timezone.utc),
            )
            logger.info("cmd.autenticacao_ok", nif_parcial=utilizador.nif[:3] + "****" if utilizador.nif else "?")
            return utilizador

        except Exception as e:
            logger.error("cmd.callback_error", error=str(e))
            raise ValueError(f"Erro ao processar autenticação CMD: {e}")

    def criar_utilizador_snaji_de_cmd(self, utilizador_cmd: UtilizadorCMD) -> dict:
        """
        Converte um utilizador CMD para o formato interno do SNAJI.
        Determina o papel com base nos dados CMD (NIF de advogado, magistrado, etc.)
        Em produção: verificar junto da Ordem dos Advogados / CSM.
        """
        from app.security.rbac import Role
        return {
            "email": utilizador_cmd.email or f"{utilizador_cmd.nif}@cmd.gov.pt",
            "nome": utilizador_cmd.nome,
            "role": Role.CIDADAO,         # Por defeito cidadão — pode ser promovido
            "cmd_sub": utilizador_cmd.sub,
            "nif": utilizador_cmd.nif,
        }

    def esta_configurada(self) -> bool:
        return self._config is not None


def criar_gestor_cmd_de_env() -> GestorCMD:
    """Cria o gestor CMD a partir das variáveis de ambiente."""
    import os
    client_id = os.getenv("CMD_CLIENT_ID")
    client_secret = os.getenv("CMD_CLIENT_SECRET")
    redirect_uri = os.getenv("CMD_REDIRECT_URI", "http://localhost:8000/api/v1/auth/cmd/callback")
    ambiente = os.getenv("CMD_AMBIENTE", "sandbox")

    if not client_id or not client_secret:
        logger.info("cmd.nao_configurada", motivo="CMD_CLIENT_ID ou CMD_CLIENT_SECRET não definidos")
        return GestorCMD(config=None)

    config = ConfigCMD(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        ambiente=ambiente,
    )
    return GestorCMD(config=config)


# Instância partilhada
gestor_cmd = criar_gestor_cmd_de_env()
