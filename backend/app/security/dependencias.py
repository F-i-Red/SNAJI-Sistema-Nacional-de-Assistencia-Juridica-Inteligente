"""
Dependências de autenticação para as rotas FastAPI.

Em linguagem simples:
- Cada rota protegida declara que precisa de um utilizador autenticado.
- O FastAPI chama estas funções automaticamente antes de executar a rota.
- Se o token for inválido ou faltar permissão, devolve 401/403 imediatamente.

Exemplo de uso numa rota:
    @router.post("/analysis")
    async def analisar(
        request: AnalysisRequest,
        utilizador: Utilizador = Depends(requer_login)
    ):
        ...  # só chega aqui se o utilizador estiver autenticado
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.security.jwt_manager import jwt_manager
from app.security.rbac import rbac, Role, Permissao
from app.db.utilizadores import repositorio, Utilizador

# Esquema Bearer: o token vai no header "Authorization: Bearer <token>"
_bearer = HTTPBearer(auto_error=False)


def _extrair_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    """Extrai o token do header. Lança 401 se não existir."""
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Inclua o token no header Authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def requer_login(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Utilizador:
    """
    Dependência base: verifica que o utilizador está autenticado.
    Devolve o objecto Utilizador se tudo estiver correcto.
    """
    token = _extrair_token(credentials)
    try:
        payload = jwt_manager.verificar_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado. Faz login novamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    utilizador = repositorio.por_id(payload.sub)
    if not utilizador or not utilizador.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador não encontrado ou desactivado.",
        )
    return utilizador


def requer_permissao(permissao: Permissao):
    """
    Fábrica de dependências: cria uma função que verifica uma permissão específica.

    Uso:
        @router.get("/audit")
        async def ver_auditoria(
            u: Utilizador = Depends(requer_permissao(Permissao.VER_AUDITORIA_COMPLETA))
        ):
    """
    async def _verificar(utilizador: Utilizador = Depends(requer_login)) -> Utilizador:
        if not rbac.tem_permissao(utilizador.role, permissao):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Não tens permissão para esta acção. "
                       f"Papel actual: {utilizador.role.value}. "
                       f"Necessário: {permissao.value}.",
            )
        return utilizador
    return _verificar


def requer_role(*roles: Role):
    """
    Dependência que aceita um ou mais papéis específicos.

    Uso:
        @router.delete("/caso/{id}")
        async def apagar_caso(
            u: Utilizador = Depends(requer_role(Role.ADMIN, Role.MAGISTRADO))
        ):
    """
    async def _verificar(utilizador: Utilizador = Depends(requer_login)) -> Utilizador:
        if utilizador.role not in roles:
            nomes = ", ".join(r.value for r in roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso restrito. Papéis permitidos: {nomes}.",
            )
        return utilizador
    return _verificar
