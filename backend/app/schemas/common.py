from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Any = None
    request_id: str | None = None


class DatabaseStatus(BaseModel):
    status: Literal["not_configured", "ok", "unavailable"]
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "app": "ZURUV API",
                "version": "0.1.0",
                "environment": "development",
                "database": {"status": "not_configured", "latency_ms": None},
            }
        }
    )

    # ok: app up and database reachable; degraded: app up, database not configured/unreachable.
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    database: DatabaseStatus


class VersionResponse(BaseModel):
    name: str
    version: str
    api_version: str
