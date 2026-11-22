"""Fakes and builders for the Step 7 tests. Razorpay TEST-mode shapes only; no real calls, no real keys."""

import hashlib
import hmac
import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient

from app.core.errors import ServiceUnavailableError
from app.gateways.razorpay import (
    GatewayOrder,
    GatewayPayment,
    GatewayRefund,
    GatewayUncertainError,
    RazorpayGateway,
)
from app.gateways.resend import EmailMessage, EmailSendError
from app.main import create_app
from tests.booking_helpers import API, book, future_day, iso, seed_world
from tests.conftest import JWT_SECRET, SUPABASE_URL, make_settings, seed_profile, sql

KEY_ID = "rzp_test_FAKEKEY000001"
KEY_SECRET = "fake_key_secret_for_tests_only"
WEBHOOK_SECRET = "fake_webhook_secret_for_tests"
HOLD = {"booking_hold_minutes": 10}


def payment_settings(**extra: Any) -> dict[str, Any]:
    return {
        "razorpay_key_id": KEY_ID,
        "razorpay_key_secret": KEY_SECRET,
        "razorpay_webhook_secret": WEBHOOK_SECRET,
        **HOLD,
        **extra,
    }


class FakeGateway(RazorpayGateway):
    """Real signature logic (so signature tests are genuine); network calls replaced by memory."""

    def __init__(self, settings: Any) -> None:
        super().__init__(settings)
        self.orders: dict[str, GatewayOrder] = {}
        self.payments: dict[str, GatewayPayment] = {}
        self.order_payments: dict[str, list[str]] = {}
        self.unreachable = False
        self.capture_calls: list[str] = []
        self.create_calls = 0
        # refunds
        self.refunds: dict[str, GatewayRefund] = {}
        self.refund_keys: dict[str, str] = {}
        self.refund_calls = 0
        self.refund_mode = "pending"  # pending | processed | failed | reject | timeout | timeout_but_created

    def _check(self) -> None:
        if self.unreachable:
            raise ServiceUnavailableError("down", code="PAYMENT_PROVIDER_UNAVAILABLE")

    async def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder:
        self._check()
        self.create_calls += 1
        order = GatewayOrder(f"order_{uuid.uuid4().hex[:14]}", amount_paise, currency, "created")
        self.orders[order.id] = order
        return order

    async def fetch_payment(self, payment_id: str) -> GatewayPayment:
        self._check()
        return self.payments[payment_id]

    async def fetch_order_payments(self, order_id: str) -> list[GatewayPayment]:
        self._check()
        return [self.payments[p] for p in self.order_payments.get(order_id, [])]

    async def capture(self, payment_id: str, amount_paise: int, currency: str) -> GatewayPayment:
        self._check()
        self.capture_calls.append(payment_id)
        old = self.payments[payment_id]
        new = GatewayPayment(
            old.id, old.order_id, old.amount_paise, old.currency, "captured", old.method, None, None
        )
        self.payments[payment_id] = new
        return new

    async def create_refund(
        self, payment_id: str, amount_paise: int, *, receipt: str, idempotency_key: str, notes: dict[str, str]
    ) -> GatewayRefund:
        self._check()
        self.refund_calls += 1
        if idempotency_key in self.refund_keys:  # real Razorpay replays the original result
            return self.refunds[self.refund_keys[idempotency_key]]
        if self.refund_mode == "reject":
            raise ServiceUnavailableError(
                "rejected",
                code="PAYMENT_PROVIDER_ERROR",
                details={"description": "The refund amount is greater than refundable."},
            )
        if self.refund_mode == "timeout":
            raise GatewayUncertainError("timeout", code="PAYMENT_PROVIDER_TIMEOUT")
        status = {"timeout_but_created": "pending"}.get(self.refund_mode, self.refund_mode)
        gr = GatewayRefund(f"rfnd_{uuid.uuid4().hex[:14]}", payment_id, amount_paise, status, receipt)
        self.refunds[gr.id] = gr
        self.refund_keys[idempotency_key] = gr.id
        if self.refund_mode == "timeout_but_created":
            raise GatewayUncertainError("timeout", code="PAYMENT_PROVIDER_TIMEOUT")
        return gr

    async def fetch_payment_refunds(self, payment_id: str) -> list[GatewayRefund]:
        self._check()
        return [r for r in self.refunds.values() if r.payment_id == payment_id]

    def set_refund_status(self, refund_id: str, status: str) -> GatewayRefund:
        old = self.refunds[refund_id]
        self.refunds[refund_id] = GatewayRefund(old.id, old.payment_id, old.amount_paise, status, old.receipt)
        return self.refunds[refund_id]

    async def list_payments_between(self, start_ts: int, end_ts: int) -> list[GatewayPayment]:
        self._check()
        return list(self.payments.values())

    # ---- test controls
    def customer_pays(
        self, order_id: str, *, status: str = "captured", amount: int | None = None, method: str = "upi"
    ) -> GatewayPayment:
        order = self.orders[order_id]
        gp = GatewayPayment(
            f"pay_{uuid.uuid4().hex[:14]}",
            order_id,
            order.amount_paise if amount is None else amount,
            order.currency,
            status,
            method,
            "BAD_REQUEST_ERROR" if status == "failed" else None,
            "Payment failed at bank" if status == "failed" else None,
        )
        self.payments[gp.id] = gp
        self.order_payments.setdefault(order_id, []).append(gp.id)
        return gp


class FakePush:
    configured = True

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict[str, str]]] = []
        self.invalid: set[str] = set()

    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> str:
        if token in self.invalid:
            return "invalid_token"
        self.sent.append((token, title, data))
        return "sent"


class FakeEmail:
    configured = True

    def __init__(self) -> None:
        self.sent: list[tuple[EmailMessage, str]] = []
        self.fail: EmailSendError | None = None

    async def send(self, message: EmailMessage, idempotency_key: str) -> str:
        if self.fail is not None:
            raise self.fail
        self.sent.append((message, idempotency_key))
        return f"email_{len(self.sent)}"


class Env:
    def __init__(self, api: TestClient, gw: FakeGateway, push: FakePush, mail: FakeEmail) -> None:
        self.api, self.gw, self.push, self.mail = api, gw, push, mail


@contextmanager
def payment_app(db: str, **settings: Any) -> Iterator[Env]:
    cfg = make_settings(
        supabase_jwt_secret=JWT_SECRET,
        supabase_url=SUPABASE_URL,
        database_url=db,
        **payment_settings(**settings),
    )
    app = create_app(cfg)
    gw, push, mail = FakeGateway(cfg), FakePush(), FakeEmail()
    app.state.payment_gateway, app.state.push_sender, app.state.email_sender = gw, push, mail
    with TestClient(app) as c:
        yield Env(c, gw, push, mail)


def sign_checkout(order_id: str, payment_id: str, secret: str = KEY_SECRET) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def webhook(
    event: str, gp: GatewayPayment, *, event_id: str | None = None, secret: str = WEBHOOK_SECRET
) -> tuple[bytes, dict[str, str]]:
    entity = {
        "id": gp.id,
        "order_id": gp.order_id,
        "amount": gp.amount_paise,
        "currency": gp.currency,
        "status": gp.status,
        "method": gp.method,
        "error_code": gp.error_code,
        "error_description": gp.error_description,
        "email": "customer@example.com",  # real payloads carry PII; we must never persist it
        "contact": "+910000000000",
    }
    body = json.dumps({"event": event, "payload": {"payment": {"entity": entity}}}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": event_id or f"evt_{uuid.uuid4().hex[:12]}",
        "Content-Type": "application/json",
    }


def refund_webhook(
    event: str, refund: GatewayRefund, *, event_id: str | None = None, secret: str = WEBHOOK_SECRET
) -> tuple[bytes, dict[str, str]]:
    entity = {
        "id": refund.id, "payment_id": refund.payment_id, "amount": refund.amount_paise,
        "status": refund.status, "receipt": refund.receipt,
    }  # fmt: skip
    body = json.dumps(
        {
            "event": event,
            "payload": {"refund": {"entity": entity}, "payment": {"entity": {"id": refund.payment_id}}},
        }
    ).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, {
        "X-Razorpay-Signature": sig,
        "X-Razorpay-Event-Id": event_id or f"evt_{uuid.uuid4().hex[:12]}",
        "Content-Type": "application/json",
    }


def post_webhook(env: Env, body: bytes, headers: dict[str, str]):
    return env.api.post(f"{API}/payments/webhook", content=body, headers=headers)


def hold_booking(env: Env, w: dict[str, Any], hour: int = 9, headers: Any = None) -> dict[str, Any]:
    r = book(env.api, w, iso(future_day(), hour), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def create_order(env: Env, booking_id: str, headers: dict[str, str]):
    return env.api.post(f"{API}/payments/create-order", json={"booking_id": booking_id}, headers=headers)


def paid_booking(
    env: Env, w: dict[str, Any], hour: int = 9
) -> tuple[dict[str, Any], dict[str, Any], GatewayPayment]:
    """booking -> order -> customer pays -> verified by the backend. Returns (booking, order, gateway payment)."""
    b = hold_booking(env, w, hour)
    o = create_order(env, b["id"], w["customer_h"])
    assert o.status_code == 200, o.text
    order = o.json()
    gp = env.gw.customer_pays(order["checkout"]["order_id"])
    v = env.api.post(
        f"{API}/payments/verify",
        json={
            "razorpay_order_id": gp.order_id,
            "razorpay_payment_id": gp.id,
            "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
        },
        headers=w["customer_h"],
    )
    assert v.status_code == 200, v.text
    return b, order, gp


def make_admin(db: str) -> dict[str, str]:
    from tests.conftest import auth_headers

    admin = seed_profile(db, "admin", name="Ada Admin")
    return auth_headers(admin, aal="aal2")


def rows(db: str, query: str, *args: Any) -> list[Any]:
    return sql(db, query, *args)


__all__ = [
    "API",
    "Env",
    "create_order",
    "hold_booking",
    "make_admin",
    "paid_booking",
    "payment_app",
    "post_webhook",
    "refund_webhook",
    "rows",
    "seed_world",
    "sign_checkout",
    "webhook",
]
