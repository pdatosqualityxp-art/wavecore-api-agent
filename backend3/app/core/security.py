from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

SUPABASE_JWT_AUDIENCE = "authenticated"
ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None = None

    @property
    def identifier(self) -> str:
        return self.email or self.id


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache
def get_jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True
    )


def decode_supabase_token(
    token: str, settings: Settings, jwks_client: jwt.PyJWKClient | None = None
) -> CurrentUser:
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                raise _unauthorized("Token inválido")
            key: object = settings.SUPABASE_JWT_SECRET
            algorithms = ["HS256"]
        elif algorithm in ASYMMETRIC_ALGORITHMS:
            client = jwks_client or get_jwks_client(settings.SUPABASE_URL)
            key = client.get_signing_key_from_jwt(token).key
            algorithms = ASYMMETRIC_ALGORITHMS
        else:
            raise _unauthorized("Token inválido")
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=SUPABASE_JWT_AUDIENCE,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expirado")
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo obtener las claves de firma de Supabase",
        )
    except jwt.InvalidTokenError:
        raise _unauthorized("Token inválido")
    return CurrentUser(id=str(claims["sub"]), email=claims.get("email"))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser | None:
    """Valida el JWT de Supabase. Devuelve None solo si AUTH_ENABLED=false (desarrollo local)."""
    if not settings.AUTH_ENABLED:
        return None
    if credentials is None:
        raise _unauthorized("Falta el token de autenticación")
    return decode_supabase_token(credentials.credentials, settings)
