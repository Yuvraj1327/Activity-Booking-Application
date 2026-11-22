"""Switches for decisions the client has not made yet. Every one defaults to the SAFE value."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailedError
from app.models import PlatformSetting, Profile
from app.services import audit

DEFAULTS: dict[str, bool] = {
    "venue_approval_required": False,  # Q4: owners publish immediately until the client decides
    "refunds_enabled": False,  # Q9: no real refund until a refund/cancellation policy is approved
    "payouts_enabled": False,  # Q10: no payout record can be created or paid until approved
    "payout_requires_kyc": True,  # N11: conservative default once payouts are enabled
}
DESCRIPTIONS = {
    "venue_approval_required": "New and re-submitted venues need admin approval before going live (Q4).",
    "refunds_enabled": "Allow admins to start real refunds at the payment gateway (Q9).",
    "payouts_enabled": "Allow payout records to be created, approved and marked paid (Q10).",
    "payout_requires_kyc": "Only owners whose KYC is verified can receive a payout (N11).",
}


async def get_all(session: AsyncSession) -> dict[str, bool]:
    rows = (await session.scalars(select(PlatformSetting))).all()
    out = dict(DEFAULTS)
    for r in rows:
        if r.key in out and isinstance(r.value, bool):
            out[r.key] = r.value
    return out


async def get(session: AsyncSession, key: str) -> bool:
    return (await get_all(session))[key]


async def set_value(
    session: AsyncSession, actor: Profile, key: str, value: bool, reason: str
) -> dict[str, bool]:
    if key not in DEFAULTS:
        raise ValidationFailedError("Unknown setting.", code="UNKNOWN_SETTING")
    row = await session.get(PlatformSetting, key, with_for_update=True)
    old = row.value if row is not None else DEFAULTS[key]
    if row is None:
        session.add(PlatformSetting(key=key, value=value, updated_by=actor.id))
    else:
        row.value = value
        row.updated_by = actor.id
    audit.record(
        session,
        actor,
        "admin.setting_changed",
        "platform_setting",
        key,
        before={"value": old},
        after={"value": value},
        reason=reason,
    )
    await session.commit()
    return await get_all(session)
