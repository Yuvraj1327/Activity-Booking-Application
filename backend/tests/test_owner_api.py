import io
import uuid

from tests.conftest import auth_headers, seed_profile, sql

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
B = "/api/v1/owners"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.objects[path] = data

    async def delete(self, paths: list[str]) -> None:
        for p in paths:
            self.objects.pop(p, None)


def _setup(api, db, role="owner"):
    storage = FakeStorage()
    api.app.state.storage = storage
    uid = seed_profile(db, role)
    return uid, auth_headers(uid), storage


def _city(db):
    return sql(
        db,
        "INSERT INTO public.cities (name, country_code) VALUES ($1,'IN') RETURNING id",
        f"C{uuid.uuid4().hex[:5]}",
    )[0]["id"]


def _cat(db):
    return sql(
        db, "INSERT INTO public.categories (slug, name) VALUES ($1,'X') RETURNING id", uuid.uuid4().hex[:8]
    )[0]["id"]


def _create(api, h, **body):
    r = api.post(f"{B}/venues", json={"name": "Ace", **body}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _upload(api, h, vid, data=PNG, name="a.png"):
    return api.post(
        f"{B}/venues/{vid}/images", files={"file": (name, io.BytesIO(data), "image/png")}, headers=h
    )


def test_role_enforcement(api, clean_db):
    _, owner_h, _ = _setup(api, clean_db)
    customer_h = auth_headers(seed_profile(clean_db, "customer"))
    for path in (
        "/venues",
        "/dashboard",
        "/notifications",
        "/bookings",
        "/earnings",
        "/reviews",
        "/analytics",
    ):
        assert api.get(f"{B}{path}").status_code == 401
        assert api.get(f"{B}{path}", headers=customer_h).status_code == 403
        assert api.get(f"{B}{path}", headers=owner_h).status_code == 200
    suspended = auth_headers(seed_profile(clean_db, "owner", status="suspended"))
    assert api.get(f"{B}/venues", headers=suspended).status_code == 403


def test_create_edit_list_delete(api, clean_db):
    _, h, _ = _setup(api, clean_db)
    v = _create(api, h, description="d", starting_price_paise=50000)
    assert v["status"] == "draft"
    r = api.patch(f"{B}/venues/{v['id']}", json={"name": "Ace 2", "description": None}, headers=h)
    assert r.json()["name"] == "Ace 2" and r.json()["description"] is None
    assert api.patch(f"{B}/venues/{v['id']}", json={"name": None}, headers=h).status_code == 422
    items = api.get(f"{B}/venues", params={"q": "ace"}, headers=h).json()["items"]
    assert [i["name"] for i in items] == ["Ace 2"]
    assert api.get(f"{B}/venues", params={"status": "published"}, headers=h).json()["items"] == []
    assert api.delete(f"{B}/venues/{v['id']}", headers=h).status_code == 204
    assert api.get(f"{B}/venues/{v['id']}", headers=h).status_code == 404


def test_owner_isolation(api, clean_db):
    _, a, _ = _setup(api, clean_db)
    _, b, _ = _setup(api, clean_db)
    v = _create(api, a)
    vid = v["id"]
    assert api.get(f"{B}/venues", headers=b).json()["items"] == []
    for method, path, kw in [
        ("get", f"/venues/{vid}", {}),
        ("patch", f"/venues/{vid}", {"json": {"name": "Hack"}}),
        ("delete", f"/venues/{vid}", {}),
        ("post", f"/venues/{vid}/publish", {}),
        ("post", f"/venues/{vid}/unpublish", {}),
        ("get", f"/venues/{vid}/schedules", {}),
        ("put", f"/venues/{vid}/schedules", {"json": {"regular": []}}),
        ("put", f"/venues/{vid}/images/order", {"json": {"image_ids": [str(uuid.uuid4())]}}),
    ]:
        r = getattr(api, method)(f"{B}{path}", headers=b, **kw)
        assert r.status_code == 404 and r.json()["code"] == "VENUE_NOT_FOUND", (method, path, r.text)
    assert _upload(api, b, vid).status_code == 404
    assert api.get(f"{B}/venues/{vid}", headers=a).json()["name"] == "Ace"


def test_validation_of_references(api, clean_db):
    _, h, _ = _setup(api, clean_db)
    r = api.post(f"{B}/venues", json={"name": "X", "city_id": str(uuid.uuid4())}, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "INVALID_CITY"
    r = api.post(f"{B}/venues", json={"name": "X", "category_ids": [str(uuid.uuid4())]}, headers=h)
    assert r.json()["code"] == "INVALID_CATEGORY"
    r = api.post(f"{B}/venues", json={"name": "X", "latitude": 12.0}, headers=h)
    assert r.status_code == 422
    r = api.post(f"{B}/venues", json={"name": "X", "timezone": "Mars/Base"}, headers=h)
    assert r.json()["code"] == "INVALID_TIMEZONE"


def test_publish_blockers_and_unpublish(api, clean_db):
    _, h, _ = _setup(api, clean_db)
    v = _create(api, h)
    r = api.post(f"{B}/venues/{v['id']}/publish", headers=h)
    assert r.status_code == 422 and r.json()["code"] == "PUBLISH_REQUIREMENTS"
    assert r.json()["details"]
    cat = _cat(clean_db)
    r = api.patch(
        f"{B}/venues/{v['id']}",
        json={
            "city_id": str(_city(clean_db)),
            "latitude": 12.9,
            "longitude": 77.5,
            "category_ids": [str(cat)],
        },
        headers=h,
    )
    assert r.status_code == 200 and r.json()["publish_blockers"] == []
    assert api.post(f"{B}/venues/{v['id']}/publish", headers=h).json()["status"] == "published"
    r = api.patch(f"{B}/venues/{v['id']}", json={"latitude": None, "longitude": None}, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "PUBLISHED_VENUE_INCOMPLETE"
    assert api.post(f"{B}/venues/{v['id']}/unpublish", headers=h).json()["status"] == "draft"


def test_image_upload_cover_reorder_delete(api, clean_db):
    _, h, storage = _setup(api, clean_db)
    vid = _create(api, h)["id"]
    first = _upload(api, h, vid)
    assert first.status_code == 201 and first.json()["is_cover"] is True
    second = _upload(api, h, vid, JPEG, "b.jpg")
    assert second.json()["is_cover"] is False and len(storage.objects) == 2
    ids = [second.json()["id"], first.json()["id"]]
    order = api.put(f"{B}/venues/{vid}/images/order", json={"image_ids": ids}, headers=h)
    assert [i["id"] for i in order.json()] == ids
    bad = api.put(f"{B}/venues/{vid}/images/order", json={"image_ids": ids[:1]}, headers=h)
    assert bad.json()["code"] == "INVALID_IMAGE_ORDER"
    cover = api.patch(f"{B}/venues/{vid}/images/{second.json()['id']}", json={"is_cover": True}, headers=h)
    assert cover.json()["is_cover"] is True
    detail = api.get(f"{B}/venues/{vid}", headers=h).json()
    assert [i["is_cover"] for i in detail["images"]].count(True) == 1
    assert api.delete(f"{B}/venues/{vid}/images/{second.json()['id']}", headers=h).status_code == 204
    detail = api.get(f"{B}/venues/{vid}", headers=h).json()
    assert len(detail["images"]) == 1 and detail["images"][0]["is_cover"] is True
    assert len(storage.objects) == 1
    api.delete(f"{B}/venues/{vid}", headers=h)
    assert storage.objects == {}


def test_image_rejections(api, clean_db):
    _, h, storage = _setup(api, clean_db)
    vid = _create(api, h)["id"]
    r = _upload(api, h, vid, b"GIF89a" + b"\x00" * 50, "x.gif")
    assert r.status_code == 422 and r.json()["code"] == "INVALID_IMAGE"
    r = _upload(api, h, vid, b"<script>alert(1)</script>", "x.png")
    assert r.json()["code"] == "INVALID_IMAGE"
    r = _upload(api, h, vid, PNG + b"\x00" * (5 * 1024 * 1024))
    assert r.json()["code"] == "IMAGE_TOO_LARGE"
    assert storage.objects == {}
    for _ in range(10):
        assert _upload(api, h, vid).status_code == 201
    assert _upload(api, h, vid).json()["code"] == "IMAGE_LIMIT_REACHED"


def test_storage_unconfigured_is_503(api, clean_db):
    uid = seed_profile(clean_db, "owner")
    h = auth_headers(uid)
    vid = _create(api, h)["id"]
    r = _upload(api, h, vid)  # default gateway has no Supabase service key in tests
    assert r.status_code == 503 and r.json()["code"] == "STORAGE_NOT_CONFIGURED"
    assert api.get(f"{B}/venues/{vid}", headers=h).json()["images"] == []


def test_schedule_roundtrip_and_validation(api, clean_db):
    _, h, _ = _setup(api, clean_db)
    vid = _create(api, h)["id"]
    s = api.get(f"{B}/venues/{vid}/schedules", headers=h).json()
    assert [d["weekday"] for d in s["regular"]] == list(range(7)) and all(
        d["intervals"] == [] for d in s["regular"]
    )
    assert s["slot_configuration"]["status"] == "not_configured"
    iv = [{"opens_at": "06:00:00", "closes_at": "22:00:00"}]
    r = api.put(
        f"{B}/venues/{vid}/schedules",
        json={
            "regular": [{"weekday": d, "intervals": iv} for d in range(5)],
            "special": [
                {"on_date": "2030-01-26", "is_closed": True, "note": "Holiday"},
                {
                    "on_date": "2030-02-01",
                    "is_closed": False,
                    "opens_at": "08:00:00",
                    "closes_at": "12:00:00",
                },
            ],
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["regular"][0]["intervals"][0]["opens_at"].startswith("06:00")
    assert out["regular"][6]["intervals"] == [] and len(out["special"]) == 2
    # replacing only regular leaves special untouched
    api.put(f"{B}/venues/{vid}/schedules", json={"regular": []}, headers=h)
    out = api.get(f"{B}/venues/{vid}/schedules", headers=h).json()
    assert all(d["intervals"] == [] for d in out["regular"]) and len(out["special"]) == 2
    bad = [
        {"regular": [{"weekday": 0, "intervals": iv}, {"weekday": 0, "intervals": iv}]},
        {
            "regular": [
                {"weekday": 0, "intervals": [iv[0], {"opens_at": "10:00:00", "closes_at": "23:00:00"}]}
            ]
        },
        {"regular": [{"weekday": 0, "intervals": [{"opens_at": "10:00:00", "closes_at": "09:00:00"}]}]},
        {
            "special": [
                {"on_date": "2030-01-01", "is_closed": True},
                {"on_date": "2030-01-01", "is_closed": True},
            ]
        },
        {"special": [{"on_date": "2030-01-01", "is_closed": True, "opens_at": "08:00:00"}]},
        {},
    ]
    for body in bad:
        assert api.put(f"{B}/venues/{vid}/schedules", json=body, headers=h).status_code == 422, body


def test_dashboard_real_and_unavailable(api, clean_db):
    uid, h, _ = _setup(api, clean_db)
    d = api.get(f"{B}/dashboard", headers=h).json()
    assert d["venues_total"] == 0 and d["average_rating"] is None
    assert d["total_bookings"] == 0
    assert d["booking_overview"] == {"upcoming": 0, "completed": 0, "cancelled": 0}
    for key in ("total_revenue", "monthly_revenue", "average_utilization"):
        assert d[key]["available"] is False and d[key]["depends_on"]
    a = _create(api, h, name="A")
    b = _create(api, h, name="B")
    sql(
        clean_db,
        "UPDATE public.venues SET rating_avg=4.0, rating_count=10, status='published', published_at=now(), latitude=12.9, longitude=77.5, city_id=$2 WHERE id=$1",
        uuid.UUID(a["id"]),
        _city(clean_db),
    )
    sql(clean_db, "UPDATE public.venues SET rating_avg=5.0, rating_count=30 WHERE id=$1", uuid.UUID(b["id"]))
    d = api.get(f"{B}/dashboard", headers=h).json()
    assert (d["venues_total"], d["venues_published"], d["venues_draft"]) == (2, 1, 1)
    assert d["average_rating"] == 4.8 and d["ratings_count"] == 40
    assert d["venue_performance"][0]["name"] == "B"
    other = _setup(api, clean_db)[1]
    assert api.get(f"{B}/dashboard", headers=other).json()["venues_total"] == 0


def test_notifications_read_state_and_isolation(api, clean_db):
    uid, h, _ = _setup(api, clean_db)
    other_uid, other_h, _ = _setup(api, clean_db)
    ids = []
    for t in ("booking.created", "payment.received", "review.created"):
        ids.append(
            sql(
                clean_db,
                "INSERT INTO public.notifications (user_id, type, title) VALUES ($1,$2,'T') RETURNING id",
                uid,
                t,
            )[0]["id"]
        )
    sql(
        clean_db,
        "INSERT INTO public.notifications (user_id, type, title) VALUES ($1,'booking.created','Other')",
        other_uid,
    )
    page = api.get(f"{B}/notifications", headers=h).json()
    assert len(page["items"]) == 3 and page["unread_count"] == 3
    assert [
        n["type"]
        for n in api.get(f"{B}/notifications", params={"group": "payments"}, headers=h).json()["items"]
    ] == ["payment.received"]
    assert api.post(f"{B}/notifications/{ids[0]}/read", headers=h).status_code == 204
    assert api.post(f"{B}/notifications/{ids[0]}/read", headers=other_h).status_code == 404
    page = api.get(f"{B}/notifications", params={"unread_only": True}, headers=h).json()
    assert len(page["items"]) == 2 and page["unread_count"] == 2
    api.post(f"{B}/notifications/read-all", headers=h)
    assert api.get(f"{B}/notifications", headers=h).json()["unread_count"] == 0
    assert api.get(f"{B}/notifications", headers=other_h).json()["unread_count"] == 1
    assert api.get(f"{B}/dashboard", headers=h).json()["recent_activity"]


def test_pending_endpoints_are_honest(api, clean_db):
    _, h, _ = _setup(api, clean_db)
    r = api.get(f"{B}/bookings", params={"bucket": "past"}, headers=h).json()
    assert r["available"] is True and r["items"] == []
    assert api.get(f"{B}/bookings", params={"bucket": "bogus"}, headers=h).status_code == 422
    r = api.get(f"{B}/bookings/{uuid.uuid4()}", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "BOOKING_NOT_FOUND"
    e = api.get(f"{B}/earnings", headers=h).json()
    # Step 7: real gross amounts (none yet), deductions/payouts honestly unavailable
    assert e["gross_paid_paise"] == 0 and e["payments_count"] == 0
    assert e["deductions"]["available"] is False and e["payouts"]["available"] is False
    rv = api.get(f"{B}/reviews", headers=h).json()  # Step 10: real reviews feature, none yet
    assert rv["items"] == [] and rv["summary"]["count"] == 0 and rv["summary"]["average"] is None
    a = api.get(f"{B}/analytics", params={"date_from": "2030-02-01", "date_to": "2030-01-01"}, headers=h)
    assert a.status_code == 422 and a.json()["code"] == "INVALID_DATE_RANGE"
    assert api.get(f"{B}/analytics", headers=h).json()["total_bookings"]["available"] is False


def test_owner_me_still_works(api, clean_db):
    _, h, _ = _setup(api, clean_db)
    assert api.get(f"{B}/me", headers=h).status_code == 200
