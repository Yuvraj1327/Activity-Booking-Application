"""Profile business logic: registration after sign-in, and self-service updates."""

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)
from app.core.logging import request_id_ctx
from app.core.security import TokenClaims
from app.models import AuditLog, CustomerProfile, OwnerProfile, Profile
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import CustomerUpdate, OwnerUpdate, ProfileCreate, ProfileUpdate
from app.utils.phone import normalize_claim_phone

logger = logging.getLogger(__name__)

PG_UNIQUE_VIOLATION = "23505"
PG_FK_VIOLATION = "23503"


def _sqlstate(exc: IntegrityError) -> str | None:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProfileRepository(session)

    def _audit(self, actor: Profile, action: str, **metadata: object) -> AuditLog:
        return AuditLog(
            actor_id=actor.id,
            actor_role=actor.role,
            action=action,
            entity_type="profile",
            entity_id=str(actor.id),
            metadata_=dict(metadata),
            request_id=request_id_ctx.get(),
        )

    # ------------------------------------------------------------------ registration
    async def register(self, claims: TokenClaims, payload: ProfileCreate) -> tuple[Profile, bool]:
        """Create the profile for the authenticated identity. Returns (profile, created).

        The user id, e-mail and verified phone come from the verified token. The only
        thing the client chooses is customer-or-owner; admin cannot be requested at all.
        """
        user_id = UUID(claims.sub)
        existing = await self.repo.get_profile(user_id)
        if existing is not None:
            return self._existing_or_conflict(existing, payload), False

        profile = Profile(
            id=user_id,
            role=payload.role,
            full_name=payload.full_name,
            email=claims.email.lower() if claims.email else None,
            phone=normalize_claim_phone(claims.phone) or payload.phone,
        )
        self.repo.add(profile)
        try:
            await self.repo.flush()
            if payload.role == "customer":
                self.repo.add(CustomerProfile(user_id=user_id))
            else:
                self.repo.add(
                    OwnerProfile(
                        user_id=user_id,
                        business_name=payload.business_name,
                        business_phone=payload.business_phone,
                        business_email=payload.business_email,
                        business_address=payload.business_address,
                    )
                )
            await self.repo.add_audit(self._audit(profile, "profile.registered", role=payload.role))
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            state = _sqlstate(exc)
            if state == PG_UNIQUE_VIOLATION:  # concurrent first sign-in: someone else created it
                existing = await self.repo.get_profile(user_id)
                if existing is not None:
                    return self._existing_or_conflict(existing, payload), False
            if state == PG_FK_VIOLATION:  # token is valid but the auth user no longer exists
                raise AuthenticationError("Account not found.", code="USER_NOT_FOUND") from exc
            logger.error("profile_registration_failed", extra={"sqlstate": state}, exc_info=exc)
            raise
        await self.session.refresh(profile)
        return profile, True

    @staticmethod
    def _existing_or_conflict(existing: Profile, payload: ProfileCreate) -> Profile:
        if existing.role != payload.role:
            raise ConflictError(
                f"This account is already registered as {existing.role}.", code="ROLE_CONFLICT"
            )
        return existing

    # ------------------------------------------------------------------ updates
    async def update_profile(self, user_id: UUID, patch: ProfileUpdate) -> Profile:
        profile = self._require(await self.repo.get_profile(user_id))
        changes = patch.model_dump(exclude_unset=True)
        avatar = changes.get("avatar_path")
        if avatar is not None and not avatar.startswith(f"{user_id}/"):
            raise ValidationFailedError(
                "avatar_path must be inside your own folder.", code="INVALID_AVATAR_PATH"
            )
        for name, value in changes.items():
            setattr(profile, name, value)
        await self.repo.add_audit(self._audit(profile, "profile.updated", fields=sorted(changes)))
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def update_customer(self, user_id: UUID, patch: CustomerUpdate) -> CustomerProfile:
        customer = self._require(await self.repo.get_customer(user_id))
        changes = patch.model_dump(exclude_unset=True)
        city = changes.get("preferred_city_id")
        if city is not None and not await self.repo.active_city_exists(city):
            raise ValidationFailedError("Unknown city.", code="INVALID_CITY")
        for name, value in changes.items():
            setattr(customer, name, value)
        profile = self._require(await self.repo.get_profile(user_id))
        await self.repo.add_audit(self._audit(profile, "customer.updated", fields=sorted(changes)))
        await self.session.commit()
        await self.session.refresh(customer)
        return customer

    async def update_owner(self, user_id: UUID, patch: OwnerUpdate) -> OwnerProfile:
        owner = self._require(await self.repo.get_owner(user_id))
        changes = patch.model_dump(exclude_unset=True)
        for name, value in changes.items():
            setattr(owner, name, value)
        profile = self._require(await self.repo.get_profile(user_id))
        await self.repo.add_audit(self._audit(profile, "owner.updated", fields=sorted(changes)))
        await self.session.commit()
        await self.session.refresh(owner)
        return owner

    @staticmethod
    def _require[T](row: T | None) -> T:
        if row is None:
            raise NotFoundError("Profile not found.", code="PROFILE_NOT_FOUND")
        return row
