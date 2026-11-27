"""Profile business logic: registration after sign-in, and self-service updates."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.logging import request_id_ctx
from app.core.security import TokenClaims
from app.models import AuditLog, Category, CustomerProfile, OwnerProfile, Profile, SupportTicket
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import (
    CustomerUpdate,
    OwnerUpdate,
    ProfileCreate,
    ProfileUpdate,
    SupportTicketCreate,
)
from app.services.notifications import NotificationService
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
            profile = self._existing_or_conflict(existing, payload)
            if profile.role == "customer":  # heals an account registered before its customer row existed
                await self.ensure_customer_profile(user_id)
            return profile, False

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
            await self._notify_admins_of_registration(profile)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            state = _sqlstate(exc)
            if state == PG_UNIQUE_VIOLATION:  # concurrent first sign-in: someone else created it
                existing = await self.repo.get_profile(user_id)
                if existing is not None:
                    profile = self._existing_or_conflict(existing, payload)
                    if profile.role == "customer":
                        await self.ensure_customer_profile(user_id)
                    return profile, False
            if state == PG_FK_VIOLATION:  # token is valid but the auth user no longer exists
                raise AuthenticationError("Account not found.", code="USER_NOT_FOUND") from exc
            logger.error("profile_registration_failed", extra={"sqlstate": state}, exc_info=exc)
            raise
        await self.session.refresh(profile)
        return profile, True

    async def ensure_customer_profile(self, user_id: UUID) -> None:
        """Guarantee the `customer_profiles` row that `bookings.customer_id` (and payments, reviews,
        favourites) reference. Idempotent and concurrency-safe; never touches owners or admins.

        Raises 403 `CUSTOMER_PROFILE_REQUIRED` for a non-customer account and 503
        `CUSTOMER_PROFILE_UNAVAILABLE` if the row cannot be created, instead of letting a foreign key
        violation surface later as a 500."""
        try:
            if await self.repo.get_customer(user_id) is not None:
                return
            if await self.repo.insert_customer_profile_if_missing(user_id):
                await self.repo.add_audit(
                    AuditLog(
                        actor_id=None,
                        actor_role="system",
                        action="customer_profile.provisioned",
                        entity_type="profile",
                        entity_id=str(user_id),
                        metadata_={},
                        request_id=request_id_ctx.get(),
                    )
                )
            await self.session.commit()
            if await self.repo.get_customer(user_id) is not None:
                return
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error(
                "customer_profile_provisioning_failed", extra={"user_id": str(user_id)}, exc_info=exc
            )
            raise ServiceUnavailableError(
                "Your account is not ready for booking yet. Please try again.",
                code="CUSTOMER_PROFILE_UNAVAILABLE",
            ) from exc
        profile = await self.repo.get_profile(user_id)
        if profile is not None and profile.role != "customer":
            raise PermissionDeniedError("Only customer accounts can book.", code="CUSTOMER_PROFILE_REQUIRED")
        raise ServiceUnavailableError(
            "Your account is not ready for booking yet. Please try again.",
            code="CUSTOMER_PROFILE_UNAVAILABLE",
        )

    async def _notify_admins_of_registration(self, profile: Profile) -> None:
        """Tell active admins about a new customer or owner (de-duplicated per account)."""
        admins = (
            await self.session.scalars(
                select(Profile.id).where(Profile.role == "admin", Profile.status == "active")
            )
        ).all()
        notes = NotificationService(self.session)
        for admin_id in admins:
            await notes.queue(
                user_id=admin_id,
                type_=f"admin.new_{profile.role}",
                title=f"New {profile.role} registered",
                body=profile.full_name[:200],
                dedupe_key=f"register:{profile.id}",
            )

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
        interests = changes.get("preferred_category_ids")
        if interests is not None:
            interests = list(dict.fromkeys(interests))
            known = set(
                (await self.session.scalars(select(Category.id).where(Category.id.in_(interests)))).all()
            )
            if known != set(interests):
                raise ValidationFailedError("Unknown sport.", code="INVALID_CATEGORY")
            changes["preferred_category_ids"] = interests
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

    # ------------------------------------------------------------------ account deletion request
    async def request_deletion(self, user_id: UUID) -> Profile:
        """Record that the user wants the account deleted. Nothing is removed here: an administrator
        reviews the request (bookings and payments may need to be settled first) and the user can
        cancel it until then."""
        profile = self._require(await self.repo.get_profile(user_id))
        if profile.deletion_requested_at is None:
            profile.deletion_requested_at = datetime.now(UTC)
            await self.repo.add_audit(self._audit(profile, "profile.deletion_requested"))
            await self.session.commit()
            await self.session.refresh(profile)
        return profile

    async def cancel_deletion(self, user_id: UUID) -> Profile:
        profile = self._require(await self.repo.get_profile(user_id))
        if profile.deletion_requested_at is not None:
            profile.deletion_requested_at = None
            await self.repo.add_audit(self._audit(profile, "profile.deletion_cancelled"))
            await self.session.commit()
            await self.session.refresh(profile)
        return profile

    # ------------------------------------------------------------------ support
    MAX_TICKETS_PER_HOUR = 5

    async def create_ticket(self, user_id: UUID, body: SupportTicketCreate) -> SupportTicket:
        since = datetime.now(UTC) - timedelta(hours=1)
        recent = await self.session.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(SupportTicket.user_id == user_id, SupportTicket.created_at >= since)
        )
        if (recent or 0) >= self.MAX_TICKETS_PER_HOUR:
            raise ConflictError("Too many messages sent. Please try again later.", code="RATE_LIMITED")
        ticket = SupportTicket(user_id=user_id, **body.model_dump())
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        return ticket

    async def list_tickets(self, user_id: UUID, limit: int = 20) -> list[SupportTicket]:
        rows = await self.session.scalars(
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id)
            .order_by(SupportTicket.created_at.desc())
            .limit(limit)
        )
        return list(rows.all())

    @staticmethod
    def _require[T](row: T | None) -> T:
        if row is None:
            raise NotFoundError("Profile not found.", code="PROFILE_NOT_FOUND")
        return row
