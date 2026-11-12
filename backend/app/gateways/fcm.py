"""Firebase Cloud Messaging (HTTP v1) adapter.

The service-account private key lives only in the backend environment. An OAuth2 access token is
obtained with a signed JWT (RS256) and cached until shortly before it expires.
"""

import json
import logging
import time
from pathlib import Path
from typing import Literal, Protocol

import httpx
import jwt

from app.core.config import Settings

logger = logging.getLogger(__name__)

PushResult = Literal["sent", "invalid_token", "failed"]
_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class PushSender(Protocol):
    @property
    def configured(self) -> bool: ...

    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> PushResult: ...


def load_service_account(raw: str) -> dict[str, str] | None:
    """Accepts the JSON text or a path to the JSON file. Returns None if it cannot be used."""
    text = raw.strip()
    try:
        if not text.startswith("{"):
            text = Path(text).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        return None
    if not all(k in data for k in ("client_email", "private_key")):
        return None
    return {k: str(v) for k, v in data.items()}


class FcmSender:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._project = settings.firebase_project_id
        raw = settings.firebase_service_account
        self._account = load_service_account(raw.get_secret_value()) if raw else None
        self._client = client
        self._token: str | None = None
        self._token_exp = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._project and self._account)

    async def _access_token(self, client: httpx.AsyncClient) -> str | None:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        assert self._account is not None
        now = int(time.time())
        uri = self._account.get("token_uri", "https://oauth2.googleapis.com/token")
        assertion = jwt.encode(
            {
                "iss": self._account["client_email"],
                "scope": _SCOPE,
                "aud": uri,
                "iat": now,
                "exp": now + 3600,
            },
            self._account["private_key"],
            algorithm="RS256",
        )
        resp = await client.post(
            uri,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        )
        if resp.status_code != 200:
            logger.warning("fcm_auth_failed", extra={"status": resp.status_code})
            return None
        body = resp.json()
        self._token = str(body["access_token"])
        self._token_exp = time.time() + int(body.get("expires_in", 3600))
        return self._token

    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> PushResult:
        if not self.configured:
            return "failed"
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            access = await self._access_token(client)
            if access is None:
                return "failed"
            resp = await client.post(
                f"https://fcm.googleapis.com/v1/projects/{self._project}/messages:send",
                headers={"Authorization": f"Bearer {access}"},
                json={
                    "message": {
                        "token": token,
                        "notification": {"title": title, "body": body},
                        "data": data,
                    }
                },
            )
        except (httpx.HTTPError, jwt.PyJWTError, ValueError) as exc:
            logger.warning("fcm_unreachable", extra={"error": type(exc).__name__})
            return "failed"
        finally:
            if owns:
                await client.aclose()
        if resp.status_code == 200:
            return "sent"
        if resp.status_code == 404 or "UNREGISTERED" in resp.text:
            return "invalid_token"
        logger.warning("fcm_rejected", extra={"status": resp.status_code})
        return "failed"
