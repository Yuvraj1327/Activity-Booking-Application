"""Address search for the apps. The Google key stays on the server (see gateways/places.py)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.api.deps import AnyUser
from app.core.errors import NotFoundError, ServiceUnavailableError, ValidationFailedError
from app.gateways.places import PlacesError, PlacesGateway, valid_place_id

router = APIRouter(prefix="/places", tags=["places"])


class SuggestionOut(BaseModel):
    place_id: str
    description: str


class PlaceOut(BaseModel):
    place_id: str
    name: str | None
    formatted_address: str | None
    latitude: float | None
    longitude: float | None
    postal_code: str | None


def _gateway(request: Request) -> PlacesGateway:
    gw: PlacesGateway = request.app.state.places_gateway
    if not gw.configured:
        raise ServiceUnavailableError("Address search is not configured yet.", code="PLACES_NOT_CONFIGURED")
    return gw


@router.get("/autocomplete", response_model=list[SuggestionOut], summary="Address and place suggestions")
async def autocomplete(
    request: Request,
    _: AnyUser,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    session_token: Annotated[str | None, Query(max_length=100, pattern=r"^[A-Za-z0-9_-]+$")] = None,
) -> list[SuggestionOut]:
    try:
        found = await _gateway(request).autocomplete(q.strip(), session_token)
    except PlacesError as exc:
        raise ServiceUnavailableError(
            "Address search is unavailable right now.", code="PLACES_UNAVAILABLE"
        ) from exc
    return [SuggestionOut(place_id=s.place_id, description=s.description) for s in found]


@router.get("/{place_id}", response_model=PlaceOut, summary="Coordinates and address of a place")
async def place_details(place_id: str, request: Request, _: AnyUser) -> PlaceOut:
    if not valid_place_id(place_id):
        raise ValidationFailedError("That is not a valid place id.", code="INVALID_PLACE_ID")
    try:
        p = await _gateway(request).details(place_id)
    except PlacesError as exc:
        if exc.not_found:
            raise NotFoundError("Place not found.", code="PLACE_NOT_FOUND") from exc
        raise ServiceUnavailableError(
            "Address search is unavailable right now.", code="PLACES_UNAVAILABLE"
        ) from exc
    return PlaceOut(
        place_id=p.place_id,
        name=p.name,
        formatted_address=p.formatted_address,
        latitude=p.latitude,
        longitude=p.longitude,
        postal_code=p.postal_code,
    )
