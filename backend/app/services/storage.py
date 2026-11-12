"""Venue image storage. The `venue-images` bucket is public to READ and writable only by the
backend, using the service-role key. That key exists only in the backend environment; it is never
sent to a client and never logged."""

from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError


class StorageGateway(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, paths: list[str]) -> None: ...


class SupabaseStorageGateway:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.supabase_url.rstrip("/") if settings.supabase_url else None
        self._bucket = settings.supabase_storage_bucket_venue_images
        key = settings.supabase_service_role_key
        self._key = key.get_secret_value() if key else None

    @property
    def configured(self) -> bool:
        return bool(self._base and self._key)

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        assert self._key is not None
        headers = {"Authorization": f"Bearer {self._key}", "apikey": self._key}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _require(self) -> None:
        if not self.configured:
            raise ServiceUnavailableError(
                "Image storage is not configured on the server.", code="STORAGE_NOT_CONFIGURED"
            )

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self._require()
        url = f"{self._base}/storage/v1/object/{self._bucket}/{path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.post(
                    url, content=data, headers={**self._headers(content_type), "x-upsert": "false"}
                )
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(
                "Image storage is unreachable.", code="STORAGE_UNAVAILABLE"
            ) from exc
        if res.status_code >= 400:
            raise ServiceUnavailableError("Image storage rejected the upload.", code="STORAGE_UNAVAILABLE")

    async def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        self._require()
        url = f"{self._base}/storage/v1/object/{self._bucket}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.request(
                    "DELETE", url, json={"prefixes": paths}, headers=self._headers("application/json")
                )
        except httpx.HTTPError:
            # Orphaned files are harmless; the database row is the source of truth.
            return
