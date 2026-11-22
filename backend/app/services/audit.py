"""One helper for every sensitive admin mutation: who, what, which record, before, after, why."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import request_id_ctx
from app.models import AuditLog, Profile


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def record(
    session: AsyncSession,
    actor: Profile | None,
    action: str,
    entity_type: str | None,
    entity_id: object | None,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
    **extra: Any,
) -> None:
    meta: dict[str, Any] = {}
    if before is not None:
        meta["before"] = jsonable(before)
    if after is not None:
        meta["after"] = jsonable(after)
    if reason is not None:
        meta["reason"] = reason
    meta.update(jsonable(extra))
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_role=actor.role if actor else "system",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            metadata_=meta,
            request_id=request_id_ctx.get(),
        )
    )
