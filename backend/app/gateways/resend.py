"""Resend email adapter. The API key is read from the environment only."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """The provider did not accept the message. `retryable` says whether trying again can help."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str


class EmailSender(Protocol):
    @property
    def configured(self) -> bool: ...

    async def send(self, message: EmailMessage, idempotency_key: str) -> str: ...


class ResendSender:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        key = settings.resend_api_key
        self._key = key.get_secret_value() if key else None
        self._from = settings.email_from_address
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self._key and self._from)

    async def send(self, message: EmailMessage, idempotency_key: str) -> str:
        if not self.configured:
            raise EmailSendError("Email is not configured.", retryable=False)
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._key}", "Idempotency-Key": idempotency_key},
                json={
                    "from": self._from,
                    "to": [message.to],
                    "subject": message.subject,
                    "html": message.html,
                    "text": message.text,
                },
            )
        except httpx.HTTPError as exc:
            raise EmailSendError(f"Resend unreachable ({type(exc).__name__}).", retryable=True) from exc
        finally:
            if owns:
                await client.aclose()
        if resp.status_code in (200, 201):
            return str(resp.json().get("id", ""))
        logger.warning("resend_rejected", extra={"status": resp.status_code})
        raise EmailSendError(
            f"Resend returned HTTP {resp.status_code}.",
            retryable=resp.status_code in (429, 500, 502, 503, 504),
        )
