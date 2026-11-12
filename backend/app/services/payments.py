"""Payment orders, verification, webhooks and reconciliation (Razorpay).

Rules this module enforces:
* The payable amount is read from the booking ON THE SERVER; the client never sends one.
* A booking becomes `confirmed`/`paid` only from gateway evidence: a verified checkout signature
  plus the payment fetched from Razorpay (or a verified webhook), with order, amount and currency
  all matching our own `payments` row. A frontend "success" callback alone never confirms anything.
* Verify, webhook and reconcile all go through ONE function, `_apply`, inside one DB transaction:
  payment row, booking status, history and queued notifications commit together or not at all.
* Webhooks are idempotent (unique gateway event id + row locks) and may arrive late or repeated.
* Late money (captured after the hold expired / booking cancelled) is recorded and FLAGGED for
  staff review. No refund is invented (open questions Q9, N5).
"""

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.domain import booking_state as bst
from app.domain import payment_state as pst
from app.gateways.razorpay import GatewayPayment, PaymentGateway, payment_from_entity
from app.models import AuditLog, Booking, Payment, PaymentEvent, Profile, Venue
from app.schemas.owner import Unavailable
from app.schemas.payment import (
    AdminPaymentDetail,
    AdminPaymentOut,
    AdminPaymentPage,
    AdminPaymentSummary,
    CheckoutConfig,
    CheckoutPrefill,
    CreateOrderOut,
    OwnerEarningsOut,
    OwnerPaymentOut,
    OwnerPaymentPage,
    PaymentEventOut,
    PaymentOut,
    PaymentPage,
    VenueGross,
)
from app.services.bookings import BookingService
from app.services.notifications import EmailSpec, NotificationService

logger = logging.getLogger(__name__)

MIN_AMOUNT_PAISE = 100  # Razorpay's minimum order amount (INR 1.00)
_HANDLED_EVENTS = {
    "payment.authorized",
    "payment.captured",
    "payment.failed",
    "order.paid",
    "refund.processed",
    "refund.created",
}
_SENSITIVE_KEYS = {"card", "vpa", "email", "contact", "bank", "wallet", "acquirer_data", "notes"}


def _unavailable(what: str) -> Unavailable:
    return Unavailable(
        depends_on="Business rules not approved (open questions Q7, Q8, Q9, Q10)",
        message=f"{what} will appear once the fee, commission, tax and payout rules are approved.",
    )


def _when(b: Booking) -> str:
    from zoneinfo import ZoneInfo

    local = b.starts_at.astimezone(ZoneInfo(b.timezone))
    end = b.ends_at.astimezone(ZoneInfo(b.timezone))
    return f"{local:%a %d %b %Y, %H:%M}–{end:%H:%M}"


class PaymentService:
    def __init__(self, session: AsyncSession, settings: Settings, gateway: PaymentGateway) -> None:
        self.s = session
        self.settings = settings
        self.gw = gateway

    # ================================================================== create order
    async def create_order(self, user: CurrentUser, booking_id: UUID) -> CreateOrderOut:
        if not self.gw.configured or not self.gw.public_key_id:
            raise ServiceUnavailableError("Payments are not configured yet.", code="PAYMENTS_NOT_CONFIGURED")
        booking = await self.s.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.customer_id == user.id).with_for_update()
        )
        if booking is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        payment = await self.s.scalar(
            select(Payment).where(Payment.booking_id == booking.id).with_for_update()
        )
        if payment is not None and payment.status in pst.PAID:
            raise ConflictError("This booking is already paid.", code="ALREADY_PAID")
        if booking.payment_status == "paid":
            raise ConflictError("This booking is already paid.", code="ALREADY_PAID")
        if booking.status not in bst.HOLDS:
            code = "PAYMENT_NOT_REQUIRED" if booking.status == bst.CONFIRMED else "BOOKING_NOT_PAYABLE"
            raise ConflictError("This booking cannot be paid for.", code=code)
        now = datetime.now(UTC)
        if booking.expires_at is not None and booking.expires_at <= now:
            raise ConflictError(
                "The payment time for this booking has run out. Please book again.", code="HOLD_EXPIRED"
            )
        if booking.total_amount_paise < MIN_AMOUNT_PAISE:
            raise ValidationFailedError("This booking has no payable amount.", code="AMOUNT_NOT_PAYABLE")

        if payment is None:
            order = await self.gw.create_order(
                amount_paise=booking.total_amount_paise,
                currency=booking.currency,
                receipt=booking.booking_code,
                notes={"booking_id": str(booking.id), "booking_code": booking.booking_code},
            )
            if order.amount_paise != booking.total_amount_paise or order.currency != booking.currency:
                raise ServiceUnavailableError(
                    "The payment provider returned an unexpected order.", code="PAYMENT_PROVIDER_ERROR"
                )
            payment = Payment(
                booking_id=booking.id,
                customer_id=booking.customer_id,
                venue_id=booking.venue_id,
                provider_order_id=order.id,
                amount_paise=booking.total_amount_paise,
                currency=booking.currency,
                status=pst.CREATED,
                gateway_refs={"receipt": booking.booking_code, "order_status": order.status},
            )
            self.s.add(payment)
            await self.s.flush()
            self._event(payment, "order.created", "system", "applied", order_id=order.id)
        elif payment.status == pst.FAILED:
            # Retry on the same order (one payment row per booking is a database guarantee).
            self._set_status(payment, pst.PENDING)
            if booking.status == bst.FAILED:
                BookingService(self.s, self.settings)._move(
                    booking, bst.PENDING, "system", None, "Payment retry started."
                )
        booking.payment_status = "pending"
        await self.s.commit()
        profile = user.profile
        return CreateOrderOut(
            payment=self._out(payment, booking),
            checkout=CheckoutConfig(
                key_id=self.gw.public_key_id,
                order_id=payment.provider_order_id,
                amount_paise=payment.amount_paise,
                currency=payment.currency,
                name="ZURUV",
                description=f"{booking.venue_name} · {booking.resource_name}"[:255],
                prefill=CheckoutPrefill(name=profile.full_name, email=profile.email, contact=profile.phone),
            ),
        )

    # ================================================================== verify (client callback)
    async def verify(self, user: CurrentUser, order_id: str, payment_id: str, signature: str) -> PaymentOut:
        payment = await self.s.scalar(
            select(Payment).where(Payment.provider_order_id == order_id, Payment.customer_id == user.id)
        )
        if payment is None:
            raise NotFoundError("Payment not found.", code="PAYMENT_NOT_FOUND")
        if not self.gw.verify_checkout_signature(order_id, payment_id, signature):
            self._event(
                payment,
                "checkout.verify",
                "verify",
                "rejected",
                payment_id=payment_id,
                detail={"reason": "INVALID_SIGNATURE"},
            )
            await self.s.commit()
            logger.warning("payment_signature_invalid", extra={"payment_id": str(payment.id)})
            raise BadRequestError("Payment verification failed.", code="PAYMENT_SIGNATURE_INVALID")
        try:
            evidence = await self.gw.fetch_payment(payment_id)
        except ServiceUnavailableError:
            # Signature is genuine but the amount cannot be checked right now: do NOT confirm. The
            # webhook / reconciliation will. The app shows "verification in progress".
            self._event(
                payment,
                "checkout.verify",
                "verify",
                "ignored",
                payment_id=payment_id,
                detail={"reason": "GATEWAY_UNREACHABLE"},
            )
            await self.s.commit()
            return await self._load_out(payment.id)
        await self._apply(payment.id, evidence, source="verify", event_type="checkout.verify", event_id=None)
        await self.s.commit()
        return await self._load_out(payment.id)

    # ================================================================== webhook
    async def handle_webhook(
        self, raw_body: bytes, signature: str | None, event_id_header: str | None
    ) -> str:
        """Returns the outcome string. Raises BadRequestError only for a bad signature / payload."""
        if not self.gw.webhook_configured:
            raise ServiceUnavailableError("Webhook is not configured.", code="WEBHOOK_NOT_CONFIGURED")
        if not self.gw.verify_webhook_signature(raw_body, signature):
            logger.warning("webhook_signature_invalid")
            raise BadRequestError("Invalid webhook signature.", code="WEBHOOK_SIGNATURE_INVALID")
        try:
            payload = json.loads(raw_body)
            event_type = str(payload["event"])
        except (ValueError, KeyError, TypeError) as exc:
            raise BadRequestError("Malformed webhook payload.", code="WEBHOOK_PAYLOAD_INVALID") from exc
        event_id = event_id_header or "body:" + hashlib.sha256(raw_body).hexdigest()
        if await self.s.scalar(select(PaymentEvent.id).where(PaymentEvent.provider_event_id == event_id)):
            return "duplicate"
        if event_type not in _HANDLED_EVENTS:
            await self._record_orphan(
                event_id, event_type, None, None, "ignored", {"reason": "UNHANDLED_EVENT"}
            )
            return "ignored"
        body = payload.get("payload") or {}
        pay_entity = (body.get("payment") or {}).get("entity")
        ref_entity = (body.get("refund") or {}).get("entity")
        if pay_entity is None and ref_entity is not None:
            pay_id = ref_entity.get("payment_id")
            if pay_id:
                pay_entity = {"id": pay_id}
        if not isinstance(pay_entity, dict) or "id" not in pay_entity:
            await self._record_orphan(
                event_id, event_type, None, None, "ignored", {"reason": "NO_PAYMENT_ENTITY"}
            )
            return "ignored"
        gp = payment_from_entity(pay_entity)
        payment = None
        if gp.order_id:
            payment = await self.s.scalar(select(Payment).where(Payment.provider_order_id == gp.order_id))
        if payment is None:
            payment = await self.s.scalar(select(Payment).where(Payment.provider_payment_id == gp.id))
        if payment is None:
            await self._record_orphan(
                event_id, event_type, gp.order_id, gp.id, "ignored", {"reason": "UNKNOWN_ORDER"}
            )
            return "ignored"
        try:
            if event_type.startswith("refund."):
                outcome = await self._apply_refund(payment.id, gp.id, ref_entity or {}, event_type)
            else:
                # The webhook body is signed, but the amount/status we ACT on come from the gateway
                # API when possible, so a stale or reordered webhook cannot downgrade state.
                evidence = gp
                if (
                    event_type in ("payment.captured", "order.paid", "payment.authorized")
                    and self.gw.configured
                ):
                    try:
                        evidence = await self.gw.fetch_payment(gp.id)
                    except ServiceUnavailableError:
                        evidence = gp  # signed webhook data is still genuine evidence
                outcome = await self._apply(
                    payment.id, evidence, source="webhook", event_type=event_type, event_id=event_id
                )
            await self.s.commit()
            return outcome
        except IntegrityError as exc:
            await self.s.rollback()
            if "uq_payment_events_provider_event" in str(exc.orig):
                return "duplicate"  # a concurrent delivery of the same event won the race
            raise

    async def _record_orphan(
        self,
        event_id: str,
        event_type: str,
        order_id: str | None,
        payment_id: str | None,
        outcome: str,
        detail: dict[str, Any],
    ) -> None:
        try:
            async with self.s.begin_nested():
                self.s.add(
                    PaymentEvent(
                        provider_event_id=event_id,
                        event_type=event_type[:80],
                        source="webhook",
                        provider_order_id=order_id,
                        provider_payment_id=payment_id,
                        outcome=outcome,
                        detail=detail,
                    )
                )
                await self.s.flush()
            await self.s.commit()
        except IntegrityError:
            await self.s.rollback()

    # ================================================================== the one place that applies results
    async def _apply(
        self, payment_id: UUID, gp: GatewayPayment, *, source: str, event_type: str, event_id: str | None
    ) -> str:
        pre = await self.s.get(Payment, payment_id)
        assert pre is not None
        # Lock order everywhere: booking, then payment (create_order does the same).
        booking = await self.s.scalar(select(Booking).where(Booking.id == pre.booking_id).with_for_update())
        payment = await self.s.scalar(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert booking is not None and payment is not None
        outcome = "applied"
        detail: dict[str, Any] = {"gateway_status": gp.status}

        if gp.order_id is not None and gp.order_id != payment.provider_order_id:
            return self._finish(
                payment, event_type, source, event_id, gp, "rejected", {"reason": "ORDER_MISMATCH"}
            )
        if (
            gp.status in ("captured", "authorized")
            and payment.provider_payment_id
            and payment.provider_payment_id != gp.id
            and payment.status in pst.PAID
        ):
            payment.review_required = True
            payment.review_reason = "DUPLICATE_PAYMENT_ATTEMPT"
            await self._queue_admin_review(payment, booking)
            return self._finish(
                payment,
                event_type,
                source,
                event_id,
                gp,
                "rejected",
                {"reason": "SECOND_PAYMENT_ON_PAID_ORDER"},
            )

        target = {
            "captured": pst.CAPTURED,
            "authorized": pst.AUTHORIZED,
            "failed": pst.FAILED,
            "created": pst.PENDING,
            "refunded": pst.REFUNDED,
        }.get(gp.status)
        if target is None:
            return self._finish(
                payment, event_type, source, event_id, gp, "ignored", {"reason": "UNKNOWN_STATUS"}
            )

        if target in (pst.CAPTURED, pst.AUTHORIZED) and (
            gp.amount_paise != payment.amount_paise or gp.currency != payment.currency
        ):
            payment.review_required = True
            payment.review_reason = "AMOUNT_MISMATCH"
            await self._queue_admin_review(payment, booking)
            return self._finish(
                payment,
                event_type,
                source,
                event_id,
                gp,
                "rejected",
                {"reason": "AMOUNT_MISMATCH", "expected": payment.amount_paise, "received": gp.amount_paise},
            )

        if target == pst.AUTHORIZED:
            payment.provider_payment_id = payment.provider_payment_id or gp.id
            if payment.status != pst.AUTHORIZED:
                if not pst.can_move(payment.status, pst.AUTHORIZED):
                    return self._finish(
                        payment, event_type, source, event_id, gp, "ignored", {"reason": "NO_DOWNGRADE"}
                    )
                self._set_status(payment, pst.AUTHORIZED)
            payment.method = gp.method or payment.method
            booking.payment_status = "pending"
            try:  # capture so the money is actually taken; confirmation still waits for "captured"
                captured = await self.gw.capture(gp.id, payment.amount_paise, payment.currency)
            except ServiceUnavailableError:
                return self._finish(
                    payment, event_type, source, event_id, gp, "applied", {**detail, "capture": "deferred"}
                )
            if captured.status == "captured":
                gp = captured
                target = pst.CAPTURED
                detail["capture"] = "done"
            else:
                return self._finish(payment, event_type, source, event_id, gp, "applied", detail)

        if target == pst.CAPTURED:
            outcome = await self._on_captured(payment, booking, gp)
        elif target == pst.FAILED:
            outcome = await self._on_failed(payment, booking, gp)
        elif target == pst.PENDING:
            if payment.status == pst.CREATED:
                self._set_status(payment, pst.PENDING)
            elif payment.status != pst.PENDING:
                outcome = "ignored"
        else:  # refunded reported on the payment entity
            outcome = "ignored"  # refund bookkeeping is handled by refund.* events only
        return self._finish(payment, event_type, source, event_id, gp, outcome, detail)

    async def _on_captured(self, payment: Payment, booking: Booking, gp: GatewayPayment) -> str:
        if payment.status in pst.PAID:
            return "duplicate" if payment.provider_payment_id == gp.id else "ignored"
        if not pst.can_move(payment.status, pst.CAPTURED):
            return "ignored"
        now = datetime.now(UTC)
        payment.provider_payment_id = gp.id
        payment.method = gp.method or payment.method
        payment.captured_at = now
        payment.failure_code = None
        payment.failure_reason = None
        self._set_status(payment, pst.CAPTURED)
        booking.payment_status = "paid"
        svc = BookingService(self.s, self.settings)
        notes = NotificationService(self.s)
        code, dk = booking.booking_code, f"payment:{payment.id}:captured"
        ctx = {
            "booking_code": code,
            "venue_name": booking.venue_name,
            "resource_name": booking.resource_name,
            "when": _when(booking),
            "amount_paise": payment.amount_paise,
            "currency": payment.currency,
        }
        venue = await self.s.get(Venue, booking.venue_id)
        assert venue is not None
        if booking.status in (bst.PENDING, bst.FAILED):
            # Money is in and the slot is still ours (the blocking slot row exists): confirm.
            if booking.status == bst.FAILED:
                svc._move(booking, bst.PENDING, "system", None, "Payment received after a failed attempt.")
            svc._move(booking, bst.CONFIRMED, "system", None, "Payment verified.")
            booking.confirmed_at = now
            booking.expires_at = None
            await notes.queue(
                user_id=booking.customer_id,
                type_="booking.confirmed",
                title="Booking confirmed",
                body=f"{booking.venue_name}, {_when(booking)}",
                dedupe_key=f"{dk}:booking_confirmed",
                booking_id=booking.id,
                payment_id=payment.id,
                email=EmailSpec("booking_confirmed", ctx),
            )
            await notes.queue(
                user_id=booking.customer_id,
                type_="payment.received",
                title="Payment received",
                body=f"Payment for {code} was successful.",
                dedupe_key=f"{dk}:payment_received",
                booking_id=booking.id,
                payment_id=payment.id,
                email=EmailSpec("payment_received", ctx),
            )
            await notes.queue(
                user_id=venue.owner_id,
                type_="booking.created",
                title="New booking",
                body=f"{booking.venue_name} / {booking.resource_name}: {code}",
                dedupe_key=f"{dk}:owner_booking",
                booking_id=booking.id,
                payment_id=payment.id,
                email=EmailSpec("owner_new_booking", ctx),
            )
            await notes.queue(
                user_id=venue.owner_id,
                type_="payment.received",
                title="Payment received",
                body=f"{code}: payment verified.",
                dedupe_key=f"{dk}:owner_payment",
                booking_id=booking.id,
                payment_id=payment.id,
            )
        elif booking.status == bst.CONFIRMED:
            pass  # already confirmed (e.g. a repeated signal); nothing more to do
        else:
            # Hold expired / booking cancelled before the money arrived. Do not guess a refund.
            payment.review_required = True
            payment.review_reason = f"LATE_PAYMENT_BOOKING_{booking.status.upper()}"
            await notes.queue(
                user_id=booking.customer_id,
                type_="payment.received",
                title="Payment received",
                body=f"We received your payment for {code}, but the booking could not be confirmed. "
                "Our team will review it.",
                dedupe_key=f"{dk}:late_customer",
                booking_id=booking.id,
                payment_id=payment.id,
            )
            await self._queue_admin_review(payment, booking)
        self.s.add(
            AuditLog(
                actor_role="system",
                action="payment.captured",
                entity_type="payment",
                entity_id=str(payment.id),
                metadata_={
                    "booking_id": str(booking.id),
                    "amount_paise": payment.amount_paise,
                    "review": payment.review_required,
                },
            )
        )
        return "applied"

    async def _on_failed(self, payment: Payment, booking: Booking, gp: GatewayPayment) -> str:
        if payment.status in pst.PAID or not pst.can_move(payment.status, pst.FAILED):
            return "ignored"  # late "failed" never overrides a captured payment
        payment.failure_code = (gp.error_code or "")[:100] or None
        payment.failure_reason = (gp.error_description or "")[:300] or None
        payment.failed_at = datetime.now(UTC)
        self._set_status(payment, pst.FAILED)
        if booking.status == bst.PENDING:
            BookingService(self.s, self.settings)._move(
                booking, bst.FAILED, "system", None, "Payment failed."
            )
        if booking.status in bst.HOLDS:
            booking.payment_status = "failed"
        await NotificationService(self.s).queue(
            user_id=booking.customer_id,
            type_="payment.failed",
            title="Payment failed",
            body=f"Your payment for {booking.booking_code} did not go through. You can try again.",
            dedupe_key=f"payment:{payment.id}:failed:{gp.id}",
            booking_id=booking.id,
            payment_id=payment.id,
        )
        return "applied"

    async def _apply_refund(
        self, payment_id: UUID, gateway_payment_id: str, refund: dict[str, Any], event_type: str
    ) -> str:
        """Mirror a refund the gateway reports (e.g. issued from the dashboard). We never start one."""
        pre = await self.s.get(Payment, payment_id)
        assert pre is not None
        booking = await self.s.scalar(select(Booking).where(Booking.id == pre.booking_id).with_for_update())
        payment = await self.s.scalar(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert booking is not None and payment is not None
        gp = GatewayPayment(
            gateway_payment_id,
            payment.provider_order_id,
            payment.amount_paise,
            payment.currency,
            "refunded",
            None,
            None,
            None,
        )
        if event_type != "refund.processed" or payment.status not in (pst.CAPTURED, pst.PARTIALLY_REFUNDED):
            return self._finish(
                payment, event_type, "webhook", None, gp, "ignored", {"reason": "NOT_APPLICABLE"}
            )
        refunded = int(refund.get("amount", 0))
        total = refunded + int(payment.gateway_refs.get("refunded_paise", 0))
        payment.gateway_refs = {**payment.gateway_refs, "refunded_paise": total}
        if total >= payment.amount_paise:
            self._set_status(payment, pst.REFUNDED)
            booking.payment_status = "refunded"
            if booking.status == bst.REFUND_PENDING:
                BookingService(self.s, self.settings)._move(
                    booking, bst.REFUNDED, "system", None, "Refund processed."
                )
        else:
            self._set_status(payment, pst.PARTIALLY_REFUNDED)
        return self._finish(payment, event_type, "webhook", None, gp, "applied", {"refunded_paise": refunded})

    # ================================================================== helpers
    def _set_status(self, payment: Payment, target: str) -> None:
        if payment.status == target:
            return
        if not pst.can_move(payment.status, target):
            raise ConflictError("Invalid payment status change.", code="PAYMENT_TRANSITION_NOT_ALLOWED")
        payment.status = target

    def _finish(
        self,
        payment: Payment,
        event_type: str,
        source: str,
        event_id: str | None,
        gp: GatewayPayment,
        outcome: str,
        detail: dict[str, Any],
    ) -> str:
        self._event(
            payment,
            event_type,
            source,
            "duplicate" if outcome == "duplicate" else outcome,
            order_id=gp.order_id,
            payment_id=gp.id,
            event_id=event_id,
            detail=detail,
        )
        return outcome

    def _event(
        self,
        payment: Payment | None,
        event_type: str,
        source: str,
        outcome: str,
        *,
        order_id: str | None = None,
        payment_id: str | None = None,
        event_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        safe = {k: v for k, v in (detail or {}).items() if k not in _SENSITIVE_KEYS}
        self.s.add(
            PaymentEvent(
                payment_id=payment.id if payment else None,
                provider_event_id=event_id,
                event_type=event_type[:80],
                source=source,
                provider_order_id=order_id or (payment.provider_order_id if payment else None),
                provider_payment_id=payment_id,
                outcome=outcome,
                detail=safe,
            )
        )

    async def _queue_admin_review(self, payment: Payment, booking: Booking) -> None:
        admins = (
            await self.s.scalars(
                select(Profile.id).where(Profile.role == "admin", Profile.status == "active")
            )
        ).all()
        notes = NotificationService(self.s)
        for admin_id in admins:
            await notes.queue(
                user_id=admin_id,
                type_="payment.review",
                title="Payment needs review",
                body=f"{booking.booking_code}: {payment.review_reason}",
                dedupe_key=f"payment:{payment.id}:review:{payment.review_reason}",
                booking_id=booking.id,
                payment_id=payment.id,
            )

    # ================================================================== reads
    def _out(self, p: Payment, b: Booking) -> PaymentOut:
        return PaymentOut(
            id=p.id,
            booking_id=b.id,
            booking_code=b.booking_code,
            venue_name=b.venue_name,
            resource_name=b.resource_name,
            amount_paise=p.amount_paise,
            currency=p.currency,
            status=p.status,
            method=p.method,
            razorpay_order_id=p.provider_order_id,
            razorpay_payment_id=p.provider_payment_id,
            failure_reason=p.failure_reason,
            booking_status=b.status,
            booking_payment_status=b.payment_status,
            confirmed=p.status in pst.PAID
            and b.status in (bst.CONFIRMED, bst.COMPLETED)
            and not p.review_required,
            needs_review=p.review_required,
            hold_expires_at=b.expires_at if b.status in bst.HOLDS else None,
            created_at=p.created_at,
            captured_at=p.captured_at,
        )

    async def _load_out(self, payment_id: UUID) -> PaymentOut:
        row = (
            await self.s.execute(
                select(Payment, Booking)
                .join(Booking, Booking.id == Payment.booking_id)
                .where(Payment.id == payment_id)
                .execution_options(populate_existing=True)
            )
        ).one()
        return self._out(row[0], row[1])

    async def get_mine(self, customer_id: UUID, payment_id: UUID) -> PaymentOut:
        found = await self.s.scalar(
            select(Payment.id).where(Payment.id == payment_id, Payment.customer_id == customer_id)
        )
        if found is None:
            raise NotFoundError("Payment not found.", code="PAYMENT_NOT_FOUND")
        payment = await self.s.get(Payment, payment_id)
        assert payment is not None
        if payment.status in pst.OPEN and self.gw.configured:
            await self.reconcile(payment.id)  # delayed confirmation: ask the gateway what happened
            await self.s.commit()
        return await self._load_out(payment_id)

    async def history(self, customer_id: UUID, limit: int, offset: int) -> PaymentPage:
        rows = (
            await self.s.execute(
                select(Payment, Booking)
                .join(Booking, Booking.id == Payment.booking_id)
                .where(Payment.customer_id == customer_id)
                .order_by(Payment.created_at.desc(), Payment.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        return PaymentPage(
            items=[self._out(p, b) for p, b in rows[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    # ================================================================== reconciliation
    async def reconcile(self, payment_id: UUID) -> str:
        """Ask the gateway for the order's payment attempts and apply the best one."""
        payment = await self.s.get(Payment, payment_id)
        if payment is None or payment.status not in pst.OPEN:
            return "ignored"
        try:
            attempts = await self.gw.fetch_order_payments(payment.provider_order_id)
        except ServiceUnavailableError:
            return "ignored"
        rank = {"captured": 0, "authorized": 1, "failed": 3}
        attempts.sort(key=lambda a: rank.get(a.status, 2))
        if not attempts:
            return "ignored"
        return await self._apply(
            payment_id, attempts[0], source="reconcile", event_type="reconcile", event_id=None
        )

    async def reconcile_open(self, limit: int = 25) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=self.settings.payment_reconcile_after_minutes)
        ids = (
            await self.s.scalars(
                select(Payment.id)
                .join(Booking, Booking.id == Payment.booking_id)
                .where(Payment.status.in_(tuple(pst.OPEN)), Payment.created_at <= cutoff)
                .order_by(Payment.created_at)
                .limit(limit)
            )
        ).all()
        done = 0
        for pid in ids:
            try:
                await self.reconcile(pid)
                await self.s.commit()
                done += 1
            except Exception:
                logger.exception("reconcile_failed", extra={"payment_id": str(pid)})
                await self.s.rollback()
        return done

    # ================================================================== owner
    async def owner_payments(self, owner_id: UUID, limit: int, offset: int) -> OwnerPaymentPage:
        rows = (
            await self.s.execute(
                select(Payment, Booking, Venue.name)
                .join(Booking, Booking.id == Payment.booking_id)
                .join(Venue, Venue.id == Payment.venue_id)
                .where(Venue.owner_id == owner_id, Payment.status.in_(tuple(pst.PAID)))
                .order_by(Payment.captured_at.desc().nullslast(), Payment.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        items = [
            OwnerPaymentOut(
                id=p.id,
                booking_id=b.id,
                booking_code=b.booking_code,
                venue_id=p.venue_id,
                venue_name=vn,
                resource_name=b.resource_name,
                amount_paise=p.amount_paise,
                currency=p.currency,
                status=p.status,
                method=p.method,
                captured_at=p.captured_at,
                created_at=p.created_at,
            )
            for p, b, vn in rows[:limit]
        ]
        return OwnerPaymentPage(items=items, limit=limit, offset=offset, has_more=len(rows) > limit)

    async def owner_earnings(self, owner_id: UUID) -> OwnerEarningsOut:
        rows = (
            await self.s.execute(
                select(
                    Venue.id,
                    Venue.name,
                    func.coalesce(func.sum(Payment.amount_paise), 0),
                    func.count(Payment.id),
                )
                .join(Payment, Payment.venue_id == Venue.id)
                .where(Venue.owner_id == owner_id, Payment.status.in_(tuple(pst.PAID)))
                .group_by(Venue.id, Venue.name)
                .order_by(Venue.name)
            )
        ).all()
        by_venue = [
            VenueGross(venue_id=r[0], venue_name=r[1], gross_paid_paise=int(r[2]), payments=int(r[3]))
            for r in rows
        ]
        return OwnerEarningsOut(
            gross_paid_paise=sum(v.gross_paid_paise for v in by_venue),
            payments_count=sum(v.payments for v in by_venue),
            by_venue=by_venue,
            deductions=_unavailable("Platform fees, commission and tax"),
            net_earnings=_unavailable("Net earnings"),
            payouts=_unavailable("Payout status"),
        )

    # ================================================================== admin
    def _admin_out(self, p: Payment, b: Booking, venue_name: str) -> AdminPaymentOut:
        return AdminPaymentOut(
            id=p.id,
            booking_id=b.id,
            booking_code=b.booking_code,
            booking_status=b.status,
            customer_id=p.customer_id,
            venue_id=p.venue_id,
            venue_name=venue_name,
            amount_paise=p.amount_paise,
            currency=p.currency,
            status=p.status,
            method=p.method,
            razorpay_order_id=p.provider_order_id,
            razorpay_payment_id=p.provider_payment_id,
            failure_code=p.failure_code,
            failure_reason=p.failure_reason,
            review_required=p.review_required,
            review_reason=p.review_reason,
            created_at=p.created_at,
            captured_at=p.captured_at,
            failed_at=p.failed_at,
        )

    async def admin_list(
        self, status: str | None, review_required: bool | None, limit: int, offset: int
    ) -> AdminPaymentPage:
        stmt = (
            select(Payment, Booking, Venue.name)
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Venue, Venue.id == Payment.venue_id)
        )
        if status:
            stmt = stmt.where(Payment.status == status)
        if review_required is not None:
            stmt = stmt.where(Payment.review_required == review_required)
        rows = (
            await self.s.execute(
                stmt.order_by(Payment.created_at.desc(), Payment.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return AdminPaymentPage(
            items=[self._admin_out(p, b, vn) for p, b, vn in rows[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def admin_get(self, payment_id: UUID) -> AdminPaymentDetail:
        row = (
            await self.s.execute(
                select(Payment, Booking, Venue.name)
                .join(Booking, Booking.id == Payment.booking_id)
                .join(Venue, Venue.id == Payment.venue_id)
                .where(Payment.id == payment_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Payment not found.", code="PAYMENT_NOT_FOUND")
        events = (
            await self.s.scalars(
                select(PaymentEvent)
                .where(PaymentEvent.payment_id == payment_id)
                .order_by(PaymentEvent.created_at)
            )
        ).all()
        base = self._admin_out(*row)
        return AdminPaymentDetail(
            **base.model_dump(),
            events=[
                PaymentEventOut(
                    id=e.id,
                    event_type=e.event_type,
                    source=e.source,
                    outcome=e.outcome,
                    provider_event_id=e.provider_event_id,
                    provider_payment_id=e.provider_payment_id,
                    created_at=e.created_at,
                )
                for e in events
            ],
        )

    async def admin_summary(self) -> AdminPaymentSummary:
        gross, captured = (
            await self.s.execute(
                select(func.coalesce(func.sum(Payment.amount_paise), 0), func.count(Payment.id)).where(
                    Payment.status.in_(tuple(pst.PAID))
                )
            )
        ).one()
        counts = dict(
            (
                await self.s.execute(select(Payment.status, func.count(Payment.id)).group_by(Payment.status))
            ).all()
        )
        review = (
            await self.s.execute(select(func.count(Payment.id)).where(Payment.review_required.is_(True)))
        ).scalar_one()
        rejected = (
            await self.s.execute(
                select(func.count(PaymentEvent.id)).where(PaymentEvent.outcome == "rejected")
            )
        ).scalar_one()
        return AdminPaymentSummary(
            gross_captured_paise=int(gross),
            captured_count=int(captured),
            failed_count=int(counts.get(pst.FAILED, 0)),
            open_count=int(sum(counts.get(s, 0) for s in (pst.CREATED, pst.PENDING, pst.AUTHORIZED))),
            review_required_count=int(review),
            rejected_events_count=int(rejected),
            refunds=_unavailable("Refund totals"),
        )
