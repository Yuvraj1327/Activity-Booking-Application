"""Admin: roles and permissions, platform switches, system monitoring."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, DbSession, require_permission
from app.schemas.admin_ops import AssignRole, ReasonBody, RoleCreate, RoleUpdate, SettingChange
from app.services import platform_settings
from app.services.admin_system import RoleService, monitoring_snapshot

router = APIRouter(prefix="/admin", tags=["admin-system"])


@router.get("/permissions", summary="Every permission an administrator role can hold")
async def list_permissions(
    _: Annotated[CurrentUser, Depends(require_permission("roles.manage"))],
) -> dict[str, Any]:
    return {"items": RoleService.catalogue()}


@router.get("/roles", summary="Admin roles")
async def list_roles(
    _: Annotated[CurrentUser, Depends(require_permission("roles.manage"))], session: DbSession
) -> dict[str, Any]:
    return {"items": await RoleService(session).list_roles()}


@router.post("/roles", status_code=status.HTTP_201_CREATED, summary="Create a role (audited)")
async def create_role(
    body: RoleCreate,
    user: Annotated[CurrentUser, Depends(require_permission("roles.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await RoleService(session).create_role(user, body.name, body.description, body.permissions)


@router.patch("/roles/{role_id}", summary="Edit a role's permissions (audited, before/after)")
async def update_role(
    role_id: UUID,
    body: RoleUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("roles.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await RoleService(session).update_role(
        user, role_id, body.description, body.permissions, body.reason
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an unused role")
async def delete_role(
    role_id: UUID,
    body: ReasonBody,
    user: Annotated[CurrentUser, Depends(require_permission("roles.manage"))],
    session: DbSession,
) -> Response:
    await RoleService(session).delete_role(user, role_id, body.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admins", summary="Administrators and their roles")
async def list_admins(
    _: Annotated[CurrentUser, Depends(require_permission("roles.manage"))], session: DbSession
) -> dict[str, Any]:
    return {"items": await RoleService(session).list_admins()}


@router.put("/admins/{admin_id}/role", summary="Assign (or remove) an administrator's role (audited)")
async def assign_role(
    admin_id: UUID,
    body: AssignRole,
    user: Annotated[CurrentUser, Depends(require_permission("roles.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await RoleService(session).assign(user, admin_id, body.role_id, body.reason)


@router.get("/settings", summary="Platform switches for decisions still open with the client")
async def get_settings_switches(
    _: Annotated[CurrentUser, Depends(require_permission("settings.manage"))], session: DbSession
) -> dict[str, Any]:
    values = await platform_settings.get_all(session)
    return {
        "items": [
            {
                "key": k,
                "value": v,
                "default": platform_settings.DEFAULTS[k],
                "description": platform_settings.DESCRIPTIONS[k],
            }
            for k, v in values.items()
        ]  # fmt: skip
    }


@router.put("/settings/{key}", summary="Change a platform switch (audited, reason required)")
async def put_setting(
    key: str,
    body: SettingChange,
    user: Annotated[CurrentUser, Depends(require_permission("settings.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    values = await platform_settings.set_value(session, user.profile, key, body.value, body.reason)
    return {"items": [{"key": k, "value": v} for k, v in values.items()]}


@router.get("/monitoring", summary="Backend, database, gateway and job status (no secrets)")
async def monitoring(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("monitoring.view"))],
    session: DbSession,
) -> dict[str, Any]:
    return await monitoring_snapshot(request.app, session, request.app.state.settings)
