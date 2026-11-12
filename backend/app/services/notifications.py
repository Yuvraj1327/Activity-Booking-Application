"""Notifications: in-app history, push (FCM) and email (Resend).

Pattern ("outbox"): business code calls `NotificationService.queue(...)` INSIDE its database
transaction. That only inserts rows (a notification with push_status='pending' and optionally an
email_deliveries row with status='queued'), so the notification commits or rolls back together
with the business change, and a repeated event cannot duplicate it (unique dedupe keys).
AFTER the commit, `dispatch()` delivers whatever is pending. A failed delivery never affects
payment or booking state; it stays pending/queued and the background sweep retries it.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateways.fcm import PushSender
from app.gateways.resend import EmailSender, EmailSendError
from app.models import (
    EmailDelivery,
    Notification,
    NotificationPreference,
    Profile,
    UserDeviceToken,
)
from app.services import email_templates

logger = logging.getLogger(__name__)

MAX_PUSH_ATTEMPTS = 5
MAX_EMAIL_ATTEMPTS = 5
BATCH = 50


@dataclass(frozen=True)
class EmailSpec:
    template: str
    context: dict[str, Any]


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ------------------------------------------------------------------ queue (inside a transaction)
    async def queue(
        self,
        *,
        user_id: UUID,
        type_: str,
        title: str,
        body: str,
        dedupe_key: str,
        booking_id: UUID | None = None,
        payment_id: UUID | None = None,
        email: EmailSpec | None = None,
    ) -> bool:
        """Returns False when this exact notification was already queued (duplicate event)."""
        prefs = await self.s.get(NotificationPreference, user_id)
        push_on = prefs.push_enabled if prefs else True
        email_on = prefs.email_enabled if prefs else True
        # Only ids go into `data` (used for tap navigation). No amounts, no tokens, no secrets.
        data: dict[str, Any] = {}
        if booking_id:
            data["booking_id"] = str(booking_id)
        if payment_id:
            data["payment_id"] = str(payment_id)
        stmt = (
            pg_insert(Notification)
            .values(
                user_id=user_id,
                type=type_,
                title=title,
                body=body,
                data=data,
                booking_id=booking_id,
                payment_id=payment_id,
                dedupe_key=dedupe_key,
                push_status="pending" if push_on else "skipped",
            )
            .on_conflict_do_nothing(
                index_elements=[Notification.user_id, Notification.dedupe_key],
                index_where=Notification.dedupe_key.is_not(None),
            )
            .returning(Notification.id)
        )
        created = (await self.s.execute(stmt)).first() is not None
        if created and email is not None and email_on:
            profile = await self.s.get(Profile, user_id)
            if profile is not None and profile.email:
                await self.s.execute(
                    pg_insert(EmailDelivery)
                    .values(
                        user_id=user_id,
                        to_email=profile.email,
                        template=email.template,
                        context=email.context,
                        dedupe_key=f"{dedupe_key}:{user_id}",
                        booking_id=booking_id,
                        payment_id=payment_id,
                    )
                    .on_conflict_do_nothing(index_elements=[EmailDelivery.dedupe_key])
                )
        return created


# ---------------------------------------------------------------------- dispatch (after commit)
async def dispatch_push(session: AsyncSession, sender: PushSender, limit: int = BATCH) -> int:
    """Deliver pending push notifications. Returns how many were handled."""
    rows = (
        await session.scalars(
            select(Notification)
            .where(Notification.push_status == "pending")
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for n in rows:
        tokens = list(
            (await session.scalars(select(UserDeviceToken).where(UserDeviceToken.user_id == n.user_id))).all()
        )
        if not tokens:
            n.push_status = "skipped"  # nothing to deliver to; the in-app copy remains
            continue
        if not sender.configured:
            n.push_status = "skipped"
            continue
        payload = {"type": n.type, "notification_id": str(n.id), **{k: str(v) for k, v in n.data.items()}}
        ok = False
        for t in tokens:
            result = await sender.send(t.token, n.title, n.body or "", payload)
            if result == "sent":
                ok = True
            elif result == "invalid_token":
                await session.execute(delete(UserDeviceToken).where(UserDeviceToken.id == t.id))
        n.push_attempts += 1
        if ok:
            n.push_status = "sent"
            n.push_sent_at = datetime.now(UTC)
        elif n.push_attempts >= MAX_PUSH_ATTEMPTS:
            n.push_status = "failed"
    await session.commit()
    return len(rows)


async def dispatch_email(session: AsyncSession, sender: EmailSender, limit: int = BATCH) -> int:
    rows = (
        await session.scalars(
            select(EmailDelivery)
            .where(EmailDelivery.status == "queued", EmailDelivery.attempts < MAX_EMAIL_ATTEMPTS)
            .order_by(EmailDelivery.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for e in rows:
        if not sender.configured:
            e.status = "skipped"
            e.last_error = "Email is not configured."
            continue
        e.attempts += 1
        try:
            message = email_templates.render(e.template, e.to_email, e.context)
            e.provider_message_id = await sender.send(message, idempotency_key=e.dedupe_key[:256])
            e.status = "sent"
            e.sent_at = datetime.now(UTC)
            e.last_error = None
        except EmailSendError as exc:
            e.last_error = str(exc)[:300]
            if not exc.retryable or e.attempts >= MAX_EMAIL_ATTEMPTS:
                e.status = "failed"
        except Exception as exc:  # a template bug must not poison the queue
            logger.exception("email_render_failed", extra={"template": e.template})
            e.status = "failed"
            e.last_error = f"{type(exc).__name__}"[:300]
    await session.commit()
    return len(rows)


async def dispatch_all(session: AsyncSession, push: PushSender, email: EmailSender) -> None:
    try:
        await dispatch_push(session, push)
        await dispatch_email(session, email)
    except Exception:  # delivery problems must never surface to the caller
        logger.exception("dispatch_failed")
        await session.rollback()


# ---------------------------------------------------------------------- devices and preferences
async def register_token(session: AsyncSession, user_id: UUID, token: str, platform: str, app: str) -> None:
    stmt = pg_insert(UserDeviceToken).values(user_id=user_id, token=token, platform=platform, app=app)
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserDeviceToken.token],
        set_={
            "user_id": user_id,
            "platform": platform,
            "app": app,
            "last_seen_at": datetime.now(UTC),
        },
    )
    await session.execute(stmt)
    await session.commit()


async def remove_token(session: AsyncSession, user_id: UUID, token: str) -> None:
    await session.execute(
        delete(UserDeviceToken).where(UserDeviceToken.user_id == user_id, UserDeviceToken.token == token)
    )
    await session.commit()


async def get_preferences(session: AsyncSession, user_id: UUID) -> tuple[bool, bool]:
    prefs = await session.get(NotificationPreference, user_id)
    return (prefs.push_enabled, prefs.email_enabled) if prefs else (True, True)


async def set_preferences(
    session: AsyncSession, user_id: UUID, push_enabled: bool | None, email_enabled: bool | None
) -> tuple[bool, bool]:
    cur_push, cur_email = await get_preferences(session, user_id)
    push = cur_push if push_enabled is None else push_enabled
    mail = cur_email if email_enabled is None else email_enabled
    stmt = pg_insert(NotificationPreference).values(user_id=user_id, push_enabled=push, email_enabled=mail)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[NotificationPreference.user_id],
            set_={"push_enabled": push, "email_enabled": mail, "updated_at": datetime.now(UTC)},
        )
    )
    await session.commit()
    return push, mail


async def unread_count(session: AsyncSession, user_id: UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            )
        ).scalar_one()
    )
