"""Google Places adapter (Places API (New)). The API key lives only in the backend environment.

Clients (Flutter, admin) never see the key: they call `/api/v1/places/*`, which calls Google.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_PLACE_ID = re.compile(r"^[A-Za-z0-9_-]{10,300}$")


class PlacesError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


@dataclass(frozen=True)
class PlaceSuggestion:
    place_id: str
    description: str


@dataclass(frozen=True)
class PlaceDetails:
    place_id: str
    name: str | None
    formatted_address: str | None
    latitude: float | None
    longitude: float | None
    postal_code: str | None


class PlacesGateway(Protocol):
    @property
    def configured(self) -> bool: ...

    async def autocomplete(self, text: str, session_token: str | None) -> list[PlaceSuggestion]: ...

    async def details(self, place_id: str) -> PlaceDetails: ...


def valid_place_id(value: str) -> bool:
    return bool(_PLACE_ID.match(value))


class GooglePlaces:
    BASE = "https://places.googleapis.com/v1"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        # getattr: a missing/blank key (or an older Settings) must never crash app startup.
        key = getattr(settings, "google_maps_api_key", None)
        self._key = (key.get_secret_value().strip() or None) if key else None
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self._key)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(8.0))
        try:
            return await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise PlacesError(f"Google Places unreachable ({type(exc).__name__}).") from exc
        finally:
            if owns:
                await client.aclose()

    async def autocomplete(self, text: str, session_token: str | None) -> list[PlaceSuggestion]:
        if not self._key:
            raise PlacesError("Places is not configured.")
        body: dict[str, Any] = {"input": text}
        if session_token:
            body["sessionToken"] = session_token
        resp = await self._request(
            "POST", f"{self.BASE}/places:autocomplete", headers={"X-Goog-Api-Key": self._key}, json=body
        )
        if resp.status_code != 200:
            logger.warning("places_autocomplete_rejected", extra={"status": resp.status_code})
            raise PlacesError(f"Google Places returned HTTP {resp.status_code}.")
        out: list[PlaceSuggestion] = []
        for item in resp.json().get("suggestions", []):
            pred = item.get("placePrediction")
            if pred and pred.get("placeId"):
                out.append(PlaceSuggestion(pred["placeId"], (pred.get("text") or {}).get("text", "")))
        return out

    async def details(self, place_id: str) -> PlaceDetails:
        if not self._key:
            raise PlacesError("Places is not configured.")
        resp = await self._request(
            "GET",
            f"{self.BASE}/places/{place_id}",
            headers={
                "X-Goog-Api-Key": self._key,
                "X-Goog-FieldMask": "id,displayName,formattedAddress,location,addressComponents",
            },
        )
        if resp.status_code == 404:
            raise PlacesError("Place not found.", not_found=True)
        if resp.status_code != 200:
            logger.warning("places_details_rejected", extra={"status": resp.status_code})
            raise PlacesError(f"Google Places returned HTTP {resp.status_code}.")
        data = resp.json()
        loc = data.get("location") or {}
        postal = next(
            (
                c.get("longText")
                for c in data.get("addressComponents", [])
                if "postal_code" in c.get("types", [])
            ),
            None,
        )
        return PlaceDetails(
            place_id=data.get("id", place_id),
            name=(data.get("displayName") or {}).get("text"),
            formatted_address=data.get("formattedAddress"),
            latitude=loc.get("latitude"),
            longitude=loc.get("longitude"),
            postal_code=postal,
        )
