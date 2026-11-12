from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import AnyUser, CustomerUser, DbSession
from app.repositories.venues import VenueFilters, VenueRepository
from app.schemas.catalog import (
    AmenityOut,
    CategoryOut,
    CityOut,
    FavoriteCreate,
    Limit,
    Slug,
    VenueDetail,
    VenuePage,
    VenueSort,
)
from app.services.venues import VenueService

router = APIRouter(tags=["catalog"])
Lat = Annotated[float | None, Query(ge=-90, le=90)]
Lng = Annotated[float | None, Query(ge=-180, le=180)]


def _service(request: Request, session: DbSession) -> VenueService:
    return VenueService(session, request.app.state.settings)


@router.get("/cities", response_model=list[CityOut], summary="Active cities")
async def list_cities(_: AnyUser, session: DbSession) -> list[CityOut]:
    return [CityOut.model_validate(c) for c in await VenueRepository(session).cities()]


@router.get("/categories", response_model=list[CategoryOut], summary="Active venue categories")
async def list_categories(_: AnyUser, session: DbSession) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in await VenueRepository(session).categories()]


@router.get("/amenities", response_model=list[AmenityOut], summary="Active amenities")
async def list_amenities(_: AnyUser, session: DbSession) -> list[AmenityOut]:
    return [AmenityOut.model_validate(a) for a in await VenueRepository(session).amenities()]


@router.get("/venues", response_model=VenuePage, summary="Search published venues")
async def list_venues(
    request: Request,
    user: AnyUser,
    session: DbSession,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    category: Slug | None = None,
    city_id: UUID | None = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    lat: Lat = None,
    lng: Lng = None,
    radius_km: Annotated[float | None, Query(gt=0, le=200)] = None,
    sort: VenueSort = "popular",
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    available_today: bool = False,
) -> VenuePage:
    filters = VenueFilters(
        q, category, city_id, min_price, max_price, lat, lng, radius_km, sort, limit, offset, available_today
    )
    customer_id = user.id if user.role == "customer" else None
    return await _service(request, session).list_venues(filters, customer_id)


@router.get("/venues/{venue_id}", response_model=VenueDetail, summary="Published venue detail")
async def get_venue(
    venue_id: UUID, request: Request, user: AnyUser, session: DbSession, lat: Lat = None, lng: Lng = None
) -> VenueDetail:
    customer_id = user.id if user.role == "customer" else None
    return await _service(request, session).venue_detail(venue_id, customer_id, lat, lng)


@router.get("/favorites", response_model=VenuePage, summary="Own favorite venues (newest first)")
async def list_favorites(
    request: Request,
    user: CustomerUser,
    session: DbSession,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> VenuePage:
    return await _service(request, session).list_favorites(user.id, limit, offset)


@router.post("/favorites", status_code=status.HTTP_204_NO_CONTENT, summary="Add a favorite (idempotent)")
async def add_favorite(
    body: FavoriteCreate, request: Request, user: CustomerUser, session: DbSession
) -> Response:
    await _service(request, session).add_favorite(user.id, body.venue_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/favorites/{venue_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a favorite (idempotent)"
)
async def remove_favorite(
    venue_id: UUID, request: Request, user: CustomerUser, session: DbSession
) -> Response:
    await _service(request, session).remove_favorite(user.id, venue_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
