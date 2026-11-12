"""JWT verification foundation for tokens issued by Supabase Auth.

Scope in Stage 2: prove that a bearer token is genuine, unexpired and meant for this
API. Deciding what the user may DO (role, account status, ownership) is Stage 3 and
comes from our own `profiles` table, never from token metadata
(docs/SYSTEM_ARCHITECTURE.md section 8).

Note: the Supabase `role` claim ("authenticated") is a Postgres role, not an
application role.
"""

import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidTokenError,
    PyJWKClientConnectionError,
    PyJWKClientError,
)
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import AuthenticationError, ServiceUnavailableError

logger = logging.getLogger(__name__)

SYMMETRIC_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})
ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"})


class TokenClaims(BaseModel):
    """The verified claims of a Supabase access token."""

    model_config = ConfigDict(extra="allow")

    sub: str
    exp: int
    aud: str | list[str] | None = None
    iss: str | None = None
    iat: int | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    session_id: str | None = None
    aal: str | None = None
    # user_metadata is editable by the user and must never be used for authorisation.
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class JWTVerifier:
    def __init__(
        self,
        *,
        secret: str | None,
        jwks_url: str | None,
        audience: str,
        issuer: str | None,
        leeway: int = 10,
        jwks_client: PyJWKClient | Any | None = None,
    ) -> None:
        self._secret = secret
        self._audience = audience
        self._issuer = issuer
        self._leeway = leeway
        if jwks_client is not None:
            self._jwks_client = jwks_client
        elif jwks_url:
            self._jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600, timeout=5)
        else:
            self._jwks_client = None

    @property
    def configured(self) -> bool:
        return self._secret is not None or self._jwks_client is not None

    def verify(self, token: str) -> TokenClaims:
        """Verify a token and return its claims. Blocking (JWKS fetch); see verify_async."""
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc

        algorithm = header.get("alg")
        key = self._select_key(token, algorithm)

        options: dict[str, Any] = {"require": ["exp", "sub"]}
        kwargs: dict[str, Any] = {
            "algorithms": [algorithm],
            "audience": self._audience,
            "leeway": self._leeway,
            "options": options,
        }
        if self._issuer:
            kwargs["issuer"] = self._issuer

        try:
            payload = jwt.decode(token, key, **kwargs)
        except ExpiredSignatureError as exc:
            raise AuthenticationError("The token has expired.", code="TOKEN_EXPIRED") from exc
        except InvalidTokenError as exc:
            raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc
        return TokenClaims.model_validate(payload)

    async def verify_async(self, token: str) -> TokenClaims:
        return await run_in_threadpool(self.verify, token)

    def _select_key(self, token: str, algorithm: object) -> Any:
        # The algorithm is chosen from an allow-list per key type. A token claiming "none",
        # or an asymmetric token verified with a shared secret (algorithm confusion),
        # is rejected.
        if algorithm in SYMMETRIC_ALGORITHMS:
            if not self._secret:
                logger.warning("jwt_symmetric_token_but_no_secret_configured")
                raise AuthenticationError("Invalid token.", code="INVALID_TOKEN")
            return self._secret
        if algorithm in ASYMMETRIC_ALGORITHMS:
            if self._jwks_client is None:
                logger.warning("jwt_asymmetric_token_but_no_jwks_configured")
                raise AuthenticationError("Invalid token.", code="INVALID_TOKEN")
            try:
                return self._jwks_client.get_signing_key_from_jwt(token).key
            except PyJWKClientConnectionError as exc:
                logger.error("jwks_unreachable", exc_info=exc)
                raise ServiceUnavailableError("Authentication service unavailable.") from exc
            except PyJWKClientError as exc:
                raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc
            except InvalidTokenError as exc:
                raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc
        raise AuthenticationError("Invalid token.", code="INVALID_TOKEN")


def build_jwt_verifier(settings: Settings) -> JWTVerifier:
    secret = settings.supabase_jwt_secret.get_secret_value() if settings.supabase_jwt_secret else None
    return JWTVerifier(
        secret=secret,
        jwks_url=settings.jwks_url,
        audience=settings.supabase_jwt_audience,
        issuer=settings.jwt_issuer,
        leeway=settings.jwt_leeway_seconds,
    )
