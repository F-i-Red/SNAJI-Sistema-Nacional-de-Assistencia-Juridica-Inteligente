"""
Rotas de autenticação do SNAJI.

POST /auth/login  → faz login, recebe token
GET  /auth/me     → vê os teus dados (requer login)
GET  /auth/roles  → lista papéis e permissões (público, para documentação)
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
import structlog

from app.security.jwt_manager import jwt_manager, TokenResponse
from app.security.rbac import rbac, Role
from app.security.dependencias import requer_login
from app.db.utilizadores import repositorio, Utilizador

router = APIRouter(prefix="/auth", tags=["Autenticação"])
logger = structlog.get_logger(__name__)


class LoginRequest(BaseModel):
    email: str
    password: str


class UtilizadorInfo(BaseModel):
    id: str
    email: str
    nome: str
    role: str
    permissoes: list[str]


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Fazer login",
    description="Autentica com email e password. Devolve um token JWT válido por 8 horas.",
)
async def login(dados: LoginRequest) -> TokenResponse:
    utilizador = repositorio.autenticar(dados.email, dados.password)

    if not utilizador:
        # Mensagem genérica — não revela se foi o email ou a password
        logger.warning("auth.login.falhou", email=dados.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    token = jwt_manager.criar_token(
        user_id=utilizador.id,
        role=utilizador.role,
    )

    logger.info("auth.login.ok", user_id=utilizador.id, role=utilizador.role.value)
    return token


@router.get(
    "/me",
    response_model=UtilizadorInfo,
    summary="Ver os meus dados",
    description="Devolve informação sobre o utilizador autenticado e as suas permissões.",
)
async def meus_dados(
    utilizador: Utilizador = Depends(requer_login),
) -> UtilizadorInfo:
    return UtilizadorInfo(
        id=utilizador.id,
        email=utilizador.email,
        nome=utilizador.nome,
        role=utilizador.role.value,
        permissoes=rbac.permissoes_do_role(utilizador.role),
    )


@router.get(
    "/roles",
    summary="Listar papéis e permissões",
    description="Documenta os papéis disponíveis e as respectivas permissões. Público.",
)
async def listar_roles():
    return {
        "roles": [
            {
                "papel": role.value,
                "permissoes": rbac.permissoes_do_role(role),
            }
            for role in Role
        ]
    }
