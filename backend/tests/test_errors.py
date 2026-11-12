from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import ConflictError, register_exception_handlers
from app.core.middleware import RequestContextMiddleware


class Body(BaseModel):
    password: int


def build() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("Slot taken.", code="SLOT_UNAVAILABLE", details={"slot": 1})

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.post("/v")
    async def v(body: Body) -> None: ...

    return TestClient(app, raise_server_exceptions=False)


def test_app_error():
    r = build().get("/conflict")
    assert r.status_code == 409
    assert r.json()["code"] == "SLOT_UNAVAILABLE"
    assert r.json()["details"] == {"slot": 1}


def test_unexpected_error_does_not_leak():
    r = build().get("/boom")
    assert r.status_code == 500
    assert "secret" not in r.text
    assert r.json()["code"] == "INTERNAL_ERROR"


def test_validation_error_does_not_echo_input():
    r = build().post("/v", json={"password": "hunter2-not-an-int"})
    assert r.status_code == 422
    assert "hunter2" not in r.text
    assert r.json()["code"] == "VALIDATION_ERROR"
