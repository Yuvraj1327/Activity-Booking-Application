def test_version(client):
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    assert r.json()["api_version"] == "v1"


def test_openapi_and_docs_available_in_test(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_not_found_uses_standard_error_shape(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404
    body = r.json()
    assert set(body) == {"code", "message", "details", "request_id"}
    assert body["code"] == "NOT_FOUND"
    assert body["request_id"] == r.headers["x-request-id"]


def test_client_request_id_is_echoed_only_if_safe(client):
    assert (
        client.get("/health", headers={"X-Request-ID": "abc-12345678"}).headers["x-request-id"]
        == "abc-12345678"
    )
    bad = client.get("/health", headers={"X-Request-ID": "bad id\twith space"})
    assert bad.headers["x-request-id"] != "bad id\twith space"


def test_cors_allows_configured_origin_only(client):
    ok = client.options(
        "/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options(
        "/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
