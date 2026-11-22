"""Razorpay adapter: orders, payment lookup, capture and signature checks.

Signature rules (Razorpay docs):
* checkout:  HMAC_SHA256(key_secret,        "<order_id>|<payment_id>")  -> hex
* webhook:   HMAC_SHA256(webhook_secret,    <RAW request body bytes>)   -> hex, header X-Razorpay-Signature
Both are compared in constant time. Only the backend ever holds these secrets.
"""

import contextlib
import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayOrder:
    id: str
    amount_paise: int
    currency: str
    status: str


@dataclass(frozen=True)
class GatewayPayment:
    """What the gateway itself says about one payment attempt. This is the verified evidence."""

    id: str
    order_id: str | None
    amount_paise: int
    currency: str
    status: str  # created | authorized | captured | refunded | failed
    method: str | None
    error_code: str | None
    error_description: str | None


@dataclass(frozen=True)
class GatewayRefund:
    id: str
    payment_id: str
    amount_paise: int
    status: str  # pending | processed | failed
    receipt: str | None


class GatewayUncertainError(ServiceUnavailableError):
    """The request may or may not have reached the provider (timeout, 5xx, dropped connection).
    The caller must NOT assume failure and must NOT blindly retry: it reconciles instead."""


def refund_from_entity(entity: dict[str, Any]) -> GatewayRefund:
    return GatewayRefund(
        id=str(entity["id"]),
        payment_id=str(entity.get("payment_id", "")),
        amount_paise=int(entity.get("amount", 0)),
        status=str(entity.get("status", "pending")),
        receipt=entity.get("receipt"),
    )


class PaymentGateway(Protocol):
    @property
    def configured(self) -> bool: ...

    @property
    def public_key_id(self) -> str | None: ...

    async def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder: ...

    async def fetch_payment(self, payment_id: str) -> GatewayPayment: ...

    async def fetch_order_payments(self, order_id: str) -> list[GatewayPayment]: ...

    async def capture(self, payment_id: str, amount_paise: int, currency: str) -> GatewayPayment: ...

    async def create_refund(
        self, payment_id: str, amount_paise: int, *, receipt: str, idempotency_key: str, notes: dict[str, str]
    ) -> GatewayRefund: ...

    async def fetch_payment_refunds(self, payment_id: str) -> list[GatewayRefund]: ...

    async def list_payments_between(self, start_ts: int, end_ts: int) -> list[GatewayPayment]: ...

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...

    def verify_webhook_signature(self, raw_body: bytes, signature: str | None) -> bool: ...

    @property
    def webhook_configured(self) -> bool: ...


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def payment_from_entity(entity: dict[str, Any]) -> GatewayPayment:
    return GatewayPayment(
        id=str(entity["id"]),
        order_id=entity.get("order_id"),
        amount_paise=int(entity.get("amount", 0)),
        currency=str(entity.get("currency", "")),
        status=str(entity.get("status", "")),
        method=entity.get("method"),
        error_code=entity.get("error_code"),
        error_description=entity.get("error_description"),
    )


class RazorpayGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._base = settings.razorpay_api_base.rstrip("/")
        self._key_id = settings.razorpay_key_id
        secret = settings.razorpay_key_secret
        self._secret = secret.get_secret_value() if secret else None
        hook = settings.razorpay_webhook_secret
        self._webhook_secret = hook.get_secret_value() if hook else None
        self._client = client

    # -------------------------------------------------------------- configuration
    @property
    def configured(self) -> bool:
        return bool(self._key_id and self._secret)

    @property
    def webhook_configured(self) -> bool:
        return bool(self._webhook_secret)

    @property
    def public_key_id(self) -> str | None:
        return self._key_id

    # -------------------------------------------------------------- signatures
    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if not self._secret or not signature:
            return False
        expected = _hmac_hex(self._secret, f"{order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, signature.strip().lower())

    def verify_webhook_signature(self, raw_body: bytes, signature: str | None) -> bool:
        if not self._webhook_secret or not signature:
            return False
        expected = _hmac_hex(self._webhook_secret, raw_body)
        return hmac.compare_digest(expected, signature.strip().lower())

    # -------------------------------------------------------------- HTTP
    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise ServiceUnavailableError(
                "Payments are not configured on the server.", code="PAYMENTS_NOT_CONFIGURED"
            )
        assert self._key_id and self._secret
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        try:
            resp = await client.request(
                method,
                f"{self._base}{path}",
                json=json,
                params=params,
                headers=headers,
                auth=(self._key_id, self._secret),
            )
        except httpx.HTTPError as exc:
            logger.warning("razorpay_unreachable", extra={"path": path, "error": type(exc).__name__})
            if not isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
                # The request may have been delivered: the outcome is unknown.
                raise GatewayUncertainError(
                    "The payment provider did not answer in time. The result is unknown.",
                    code="PAYMENT_PROVIDER_TIMEOUT",
                ) from exc
            raise ServiceUnavailableError(
                "The payment provider could not be reached. Please try again.",
                code="PAYMENT_PROVIDER_UNAVAILABLE",
            ) from exc
        finally:
            if owns:
                await client.aclose()
        if resp.status_code >= 400:
            # Log status and Razorpay's error code only; never the body of a payment object.
            code = None
            description = None
            with contextlib.suppress(ValueError, AttributeError):
                err = resp.json().get("error", {})
                code = err.get("code")
                description = str(err.get("description", ""))[:200] or None
            logger.warning(
                "razorpay_error", extra={"path": path, "status": resp.status_code, "provider_code": code}
            )
            if resp.status_code >= 500:
                raise GatewayUncertainError(
                    "The payment provider had an internal error. The result is unknown.",
                    code="PAYMENT_PROVIDER_TIMEOUT",
                )
            raise ServiceUnavailableError(
                "The payment provider rejected the request.",
                code="PAYMENT_PROVIDER_ERROR",
                details={"provider_code": code, "description": description},
            )
        data: dict[str, Any] = resp.json()
        return data

    # -------------------------------------------------------------- operations
    async def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder:
        data = await self._request(
            "POST",
            "/orders",
            {"amount": amount_paise, "currency": currency, "receipt": receipt[:40], "notes": notes},
        )
        return GatewayOrder(
            id=str(data["id"]),
            amount_paise=int(data["amount"]),
            currency=str(data["currency"]),
            status=str(data.get("status", "created")),
        )

    async def fetch_payment(self, payment_id: str) -> GatewayPayment:
        return payment_from_entity(await self._request("GET", f"/payments/{payment_id}"))

    async def fetch_order_payments(self, order_id: str) -> list[GatewayPayment]:
        data = await self._request("GET", f"/orders/{order_id}/payments")
        return [payment_from_entity(i) for i in data.get("items", [])]

    async def capture(self, payment_id: str, amount_paise: int, currency: str) -> GatewayPayment:
        data = await self._request(
            "POST", f"/payments/{payment_id}/capture", {"amount": amount_paise, "currency": currency}
        )
        return payment_from_entity(data)

    async def create_refund(
        self, payment_id: str, amount_paise: int, *, receipt: str, idempotency_key: str, notes: dict[str, str]
    ) -> GatewayRefund:
        data = await self._request(
            "POST",
            f"/payments/{payment_id}/refund",
            {"amount": amount_paise, "speed": "normal", "receipt": receipt[:40], "notes": notes},
            headers={"X-Refund-Idempotency": idempotency_key},
        )
        return refund_from_entity(data)

    async def fetch_payment_refunds(self, payment_id: str) -> list[GatewayRefund]:
        data = await self._request("GET", f"/payments/{payment_id}/refunds", params={"count": 100})
        return [refund_from_entity(i) for i in data.get("items", [])]

    async def list_payments_between(self, start_ts: int, end_ts: int) -> list[GatewayPayment]:
        out: list[GatewayPayment] = []
        skip = 0
        while True:
            data = await self._request(
                "GET", "/payments", params={"from": start_ts, "to": end_ts, "count": 100, "skip": skip}
            )
            items = data.get("items", [])
            out.extend(payment_from_entity(i) for i in items)
            if len(items) < 100 or skip > 20_000:
                return out
            skip += 100
