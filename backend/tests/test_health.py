import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings


def test_health_without_database_is_degraded_not_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "not_configured"
    assert body["app"] == "ZURUV API"
    assert "x-request-id" in r.headers


def test_health_unreachable_database_reports_unavailable():
    s = make_settings(
        database_url="postgresql://u:p@127.0.0.1:1/none", db_connect_timeout=1, db_health_timeout=2
    )
    with TestClient(create_app(s)) as c:
        body = c.get("/health").json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "unavailable"
    assert "p@" not in str(body)


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_health_with_real_postgres():
    s = make_settings(database_url=os.environ["TEST_DATABASE_URL"])
    with TestClient(create_app(s)) as c:
        body = c.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"
    assert body["database"]["latency_ms"] is not None
