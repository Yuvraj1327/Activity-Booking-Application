"""Venue image storage. The `venue-images` bucket is public to READ and writable only by the
backend, using the service-role key. That key exists only in the backend environment; it is never
sent to a client and never logged."""

from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError


class StorageGateway(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str, bucket: str | None = None) -> None: ...

    async def delete(self, paths: list[str], bucket: str | None = None) -> None: ...

    async def download(self, path: str, bucket: str) -> bytes: ...


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

    async def upload(self, path: str, data: bytes, content_type: str, bucket: str | None = None) -> None:
        self._require()
        url = f"{self._base}/storage/v1/object/{bucket or self._bucket}/{path}"
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

    async def download(self, path: str, bucket: str) -> bytes:
        """Private objects are read only here, with the service-role key, never via a public URL."""
        self._require()
        url = f"{self._base}/storage/v1/object/{bucket}/{path}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError("Storage is unreachable.", code="STORAGE_UNAVAILABLE") from exc
        if res.status_code == 404:
            raise ServiceUnavailableError("The stored file is missing.", code="STORAGE_OBJECT_MISSING")
        if res.status_code >= 400:
            raise ServiceUnavailableError("Storage rejected the request.", code="STORAGE_UNAVAILABLE")
        return res.content

    async def delete(self, paths: list[str], bucket: str | None = None) -> None:
        if not paths:
            return
        self._require()
        url = f"{self._base}/storage/v1/object/{bucket or self._bucket}"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.request(
                    "DELETE", url, json={"prefixes": paths}, headers=self._headers("application/json")
                )
        except httpx.HTTPError:
            # Orphaned files are harmless; the database row is the source of truth.
            return
