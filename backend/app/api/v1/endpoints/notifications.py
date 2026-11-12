"""Notification history, read state, device tokens and preferences (any signed-in role)."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import AnyUser, DbSession
from app.schemas.catalog import Limit
from app.schemas.owner import NotificationPage
from app.schemas.payment import (
    DeviceTokenRemoveRequest,
    DeviceTokenRequest,
    PreferencesOut,
    PreferencesUpdate,
    UnreadCount,
)
from app.services import notifications as svc
from app.services.owner_business import OwnerBusinessService

router = APIRouter(tags=["notifications"])


def _history(request: Request, session: DbSession) -> OwnerBusinessService:
    # The history queries are keyed only by user id, so they serve every role.
    return OwnerBusinessService(session, request.app.state.settings)


@router.get("/notifications", response_model=NotificationPage, summary="My notifications")
async def list_notifications(
    request: Request,
    user: AnyUser,
    session: DbSession,
    group: Literal["all", "bookings", "payments", "reviews"] = "all",
    unread_only: bool = False,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> NotificationPage:
    return await _history(request, session).notifications(user.id, group, unread_only, limit, offset)


@router.get("/notifications/unread-count", response_model=UnreadCount, summary="Unread badge count")
async def unread(user: AnyUser, session: DbSession) -> UnreadCount:
    return UnreadCount(unread_count=await svc.unread_count(session, user.id))


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT, summary="Mark all read")
async def read_all(request: Request, user: AnyUser, session: DbSession) -> Response:
    await _history(request, session).mark_all_read(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, summary="Mark one read"
)
async def read_one(notification_id: UUID, request: Request, user: AnyUser, session: DbSession) -> Response:
    await _history(request, session).mark_read(user.id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/notifications/preferences", response_model=PreferencesOut, summary="My notification preferences"
)
async def get_prefs(user: AnyUser, session: DbSession) -> PreferencesOut:
    push, mail = await svc.get_preferences(session, user.id)
    return PreferencesOut(push_enabled=push, email_enabled=mail)


@router.put("/notifications/preferences", response_model=PreferencesOut, summary="Update my preferences")
async def put_prefs(body: PreferencesUpdate, user: AnyUser, session: DbSession) -> PreferencesOut:
    push, mail = await svc.set_preferences(session, user.id, body.push_enabled, body.email_enabled)
    return PreferencesOut(push_enabled=push, email_enabled=mail)


@router.put(
    "/devices/token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Register or refresh this device's push token",
)
async def register_device(body: DeviceTokenRequest, user: AnyUser, session: DbSession) -> Response:
    """Idempotent upsert by token. A token that moves to another account (sign-out / sign-in on the
    same phone) is re-assigned, so the previous user never receives the new user's pushes."""
    await svc.register_token(session, user.id, body.token, body.platform, body.app)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/devices/token/remove", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a token (sign-out)"
)
async def remove_device(body: DeviceTokenRemoveRequest, user: AnyUser, session: DbSession) -> Response:
    await svc.remove_token(session, user.id, body.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
