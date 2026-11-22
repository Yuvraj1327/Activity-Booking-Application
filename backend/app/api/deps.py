"""Shared FastAPI dependencies: settings, database, token verification and authorisation.

Authorisation is always decided server-side from the `profiles` table (decision D-11).
Nothing the client sends, in the body or in token metadata, can grant a role.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field, replace
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.permissions import ALL_PERMISSIONS, SUPER_ADMIN
from app.core.security import JWTVerifier, TokenClaims
from app.database.session import Database
from app.models import AdminProfile, AdminRole, Profile
from app.repositories.profiles import ProfileRepository

_bearer = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_database(request: Request) -> Database:
    return request.app.state.db  # type: ignore[no-any-return]


def get_jwt_verifier(request: Request) -> JWTVerifier:
    return request.app.state.jwt_verifier  # type: ignore[no-any-return]


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.db.session():
        yield session


async def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[JWTVerifier, Depends(get_jwt_verifier)],
) -> TokenClaims:
    """Verified token claims: proves identity only. Raises 401 otherwise."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Missing bearer token.", code="MISSING_TOKEN")
    if not verifier.configured:
        raise AuthenticationError("Token verification is not configured.", code="AUTH_NOT_CONFIGURED")
    return await verifier.verify_async(credentials.credentials)


def token_user_id(claims: TokenClaims) -> UUID:
    try:
        return UUID(claims.sub)
    except ValueError as exc:
        raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc


@dataclass(frozen=True)
class CurrentUser:
    """An authenticated, active account. `role` and `status` come from the database."""

    id: UUID
    role: str
    profile: Profile
    claims: TokenClaims
    permissions: frozenset[str] = field(default_factory=frozenset)
    admin_role: str | None = None

    @property
    def mfa_verified(self) -> bool:
        return self.claims.aal == "aal2"


async def get_current_user(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentUser:
    """Signed in AND registered AND not suspended. 401 / 403 otherwise."""
    user_id = token_user_id(claims)
    profile = await ProfileRepository(session).get_profile(user_id)
    if profile is None:
        raise PermissionDeniedError("Complete registration first.", code="PROFILE_REQUIRED")
    if not profile.is_active:
        raise PermissionDeniedError("This account is suspended.", code="ACCOUNT_SUSPENDED")
    return CurrentUser(id=user_id, role=profile.role, profile=profile, claims=claims)


def require_roles(*roles: str) -> Callable[..., Awaitable[CurrentUser]]:
    async def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.role not in roles:
            raise PermissionDeniedError(code="INSUFFICIENT_ROLE")
        return user

    return dependency


require_customer = require_roles("customer")
require_owner = require_roles("owner")


async def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> CurrentUser:
    if user.role != "admin":
        raise PermissionDeniedError(code="INSUFFICIENT_ROLE")
    if settings.admin_mfa_required and not user.mfa_verified:
        raise PermissionDeniedError("Multi-factor authentication is required.", code="MFA_REQUIRED")
    return user


async def load_admin_permissions(session: AsyncSession, user_id: UUID) -> tuple[str | None, frozenset[str]]:
    """The admin's role name and permissions, read from the database on every request."""
    row = (
        await session.execute(
            select(AdminRole.name, AdminRole.permissions, AdminRole.is_system)
            .join(AdminProfile, AdminProfile.role_id == AdminRole.id)
            .where(AdminProfile.user_id == user_id)
        )
    ).first()
    if row is None:
        return None, frozenset()
    name, perms, is_system = row
    if is_system and name == SUPER_ADMIN:
        return name, ALL_PERMISSIONS
    return name, frozenset(p for p in perms if p in ALL_PERMISSIONS)


def require_permission(*needed: str) -> Callable[..., Awaitable[CurrentUser]]:
    """Admin (MFA-verified when enabled) who holds EVERY listed permission."""
    unknown = set(needed) - ALL_PERMISSIONS
    assert not unknown, f"unknown permission(s): {unknown}"

    async def dependency(
        user: Annotated[CurrentUser, Depends(require_admin)],
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> CurrentUser:
        role, perms = await load_admin_permissions(session, user.id)
        if role is None:
            raise PermissionDeniedError(
                "This administrator has no role assigned yet.", code="ADMIN_ROLE_REQUIRED"
            )
        missing = [p for p in needed if p not in perms]
        if missing:
            raise PermissionDeniedError(
                "You do not have permission for this action.",
                code="PERMISSION_DENIED",
                details={"required": list(needed)},
            )
        return replace(user, permissions=perms, admin_role=role)

    return dependency


AnyUser = Annotated[CurrentUser, Depends(get_current_user)]
CustomerUser = Annotated[CurrentUser, Depends(require_customer)]
OwnerUser = Annotated[CurrentUser, Depends(require_owner)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
