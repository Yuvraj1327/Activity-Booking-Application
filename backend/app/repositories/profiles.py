from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, City, CustomerProfile, OwnerProfile, Profile


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(self, user_id: UUID) -> Profile | None:
        return await self.session.get(Profile, user_id)

    async def get_customer(self, user_id: UUID) -> CustomerProfile | None:
        return await self.session.get(CustomerProfile, user_id)

    async def insert_customer_profile_if_missing(self, user_id: UUID) -> bool:
        """Create the `customer_profiles` row for an existing CUSTOMER account; True if one was inserted.

        A single `INSERT ... SELECT ... ON CONFLICT DO NOTHING`: idempotent, safe under concurrent calls
        (the loser simply inserts nothing), and it only selects `profiles` rows whose role is
        `customer`, so owners and admins can never get one. The foreign keys stay in force."""
        stmt = (
            pg_insert(CustomerProfile)
            .from_select(
                ["user_id", "role"],
                select(Profile.id, Profile.role).where(Profile.id == user_id, Profile.role == "customer"),
            )
            .on_conflict_do_nothing(index_elements=[CustomerProfile.user_id])
            .returning(CustomerProfile.user_id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def get_owner(self, user_id: UUID) -> OwnerProfile | None:
        return await self.session.get(OwnerProfile, user_id)

    async def active_city_exists(self, city_id: UUID) -> bool:
        stmt = select(City.id).where(City.id == city_id, City.is_active.is_(True))
        return (await self.session.execute(stmt)).first() is not None

    def add(self, *objects: object) -> None:
        self.session.add_all(objects)

    async def flush(self) -> None:
        await self.session.flush()

    async def add_audit(self, entry: AuditLog) -> None:
        self.session.add(entry)
