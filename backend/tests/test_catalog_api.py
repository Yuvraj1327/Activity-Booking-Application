import uuid

from tests.conftest import SUPABASE_URL, auth_headers, seed_profile, sql
from tests.test_db_constraints import seed_venue


def _category(url, slug, name, order=0):
    return sql(
        url,
        "INSERT INTO public.categories (slug, name, sort_order) VALUES ($1,$2,$3) RETURNING id",
        slug, name, order,
    )[0]["id"]  # fmt: skip


def _venue(url, owner, name, *, lat, lng, price=None, rating=None, count=0, status="published", city=None):
    city = (
        city
        or sql(
            url,
            "INSERT INTO public.cities (name, country_code) VALUES ($1,'IN') RETURNING id",
            f"C{uuid.uuid4().hex[:5]}",
        )[0]["id"]
    )
    return sql(
        url,
        "INSERT INTO public.venues (owner_id, city_id, name, latitude, longitude, timezone, status, "
        "starting_price_paise, rating_avg, rating_count, published_at) "
        "VALUES ($1,$2,$3,$4,$5,'Asia/Kolkata',$6,$7,$8,$9, now()) RETURNING id",
        owner, city, name, lat, lng, status, price, rating, count,
    )[0]["id"]  # fmt: skip


def _link(url, venue, category):
    sql(url, "INSERT INTO public.venue_categories (venue_id, category_id) VALUES ($1,$2)", venue, category)


def test_requires_authentication(api):
    for path in ("/venues", "/categories", "/cities", "/favorites"):
        assert api.get(f"/api/v1{path}").status_code == 401


def test_reference_data_lists_only_active(api, clean_db):
    user = seed_profile(clean_db, "customer")
    _category(clean_db, "tennis", "Tennis", 2)
    _category(clean_db, "badminton", "Badminton", 1)
    sql(clean_db, "INSERT INTO public.categories (slug, name, is_active) VALUES ('old','Old',false)")
    r = api.get("/api/v1/categories", headers=auth_headers(user))
    assert [c["slug"] for c in r.json()] == ["badminton", "tennis"]
    sql(clean_db, "INSERT INTO public.cities (name, country_code) VALUES ('Pune','IN')")
    assert [c["name"] for c in api.get("/api/v1/cities", headers=auth_headers(user)).json()] == ["Pune"]


def test_only_published_venues_are_visible(api, clean_db):
    user, owner = seed_profile(clean_db, "customer"), seed_profile(clean_db, "owner")
    pub = _venue(clean_db, owner, "Public", lat=12.97, lng=77.59)
    draft = _venue(clean_db, owner, "Draft", lat=12.97, lng=77.59, status="draft")
    h = auth_headers(user)
    names = [v["name"] for v in api.get("/api/v1/venues", headers=h).json()["items"]]
    assert names == ["Public"]
    assert api.get(f"/api/v1/venues/{pub}", headers=h).status_code == 200
    r = api.get(f"/api/v1/venues/{draft}", headers=h)
    assert r.status_code == 404 and r.json()["code"] == "VENUE_NOT_FOUND"


def test_search_filters_sort_and_pagination(api, clean_db):
    user, owner = seed_profile(clean_db, "customer"), seed_profile(clean_db, "owner")
    badminton, tennis = _category(clean_db, "badminton", "Badminton"), _category(clean_db, "tennis", "Tennis")
    a = _venue(clean_db, owner, "Ace Arena", lat=12.97, lng=77.59, price=50000, rating=4.8, count=10)
    b = _venue(clean_db, owner, "Baseline Club", lat=13.10, lng=77.60, price=30000, rating=4.2, count=40)
    c = _venue(clean_db, owner, "Court 100%", lat=19.07, lng=72.87, price=90000)
    _link(clean_db, a, badminton)
    _link(clean_db, b, tennis)
    _link(clean_db, c, tennis)
    h = auth_headers(user)

    def get(**params):
        r = api.get("/api/v1/venues", params=params, headers=h)
        assert r.status_code == 200, r.text
        return [v["name"] for v in r.json()["items"]]

    assert get() == ["Baseline Club", "Ace Arena", "Court 100%"]  # popular = most reviewed first
    assert get(sort="rating") == ["Ace Arena", "Baseline Club", "Court 100%"]
    assert get(sort="price_asc") == ["Baseline Club", "Ace Arena", "Court 100%"]
    assert get(sort="price_desc") == ["Court 100%", "Ace Arena", "Baseline Club"]
    assert get(category="tennis", sort="price_asc") == ["Baseline Club", "Court 100%"]
    assert get(q="ace") == ["Ace Arena"]
    assert get(q="Tennis") == ["Baseline Club", "Court 100%"]  # matches category name
    assert get(q="100%") == ["Court 100%"]  # LIKE wildcards are escaped
    assert get(q="%") == ["Court 100%"]
    assert get(min_price=40000, max_price=60000) == ["Ace Arena"]
    # distance: Bengaluru user; Mumbai venue is ~840 km away
    assert get(lat=12.97, lng=77.59, sort="distance") == ["Ace Arena", "Baseline Club", "Court 100%"]
    assert get(lat=12.97, lng=77.59, radius_km=50, sort="distance") == ["Ace Arena", "Baseline Club"]
    first = api.get("/api/v1/venues", params={"lat": 12.97, "lng": 77.59, "sort": "distance"}, headers=h)
    assert first.json()["items"][0]["distance_km"] == 0.0

    page1 = api.get("/api/v1/venues", params={"limit": 2}, headers=h).json()
    assert len(page1["items"]) == 2 and page1["has_more"] is True
    page2 = api.get("/api/v1/venues", params={"limit": 2, "offset": 2}, headers=h).json()
    assert len(page2["items"]) == 1 and page2["has_more"] is False
    assert {v["id"] for v in page1["items"]}.isdisjoint({v["id"] for v in page2["items"]})
    assert b and c  # silence unused


def test_filter_validation(api, clean_db):
    user = seed_profile(clean_db, "customer")
    h = auth_headers(user)
    g = lambda **p: api.get("/api/v1/venues", params=p, headers=h)  # noqa: E731
    assert g(sort="distance").json()["code"] == "LOCATION_REQUIRED"
    assert g(lat=12.9).json()["code"] == "INVALID_LOCATION"
    assert g(radius_km=5).json()["code"] == "LOCATION_REQUIRED"
    assert g(min_price=10, max_price=5).json()["code"] == "INVALID_PRICE_RANGE"
    assert g(limit=500).status_code == 422
    assert g(lat=100, lng=0).status_code == 422
    assert g(sort="bogus").status_code == 422


def test_venue_detail_images_amenities_and_urls(api, clean_db):
    user, owner = seed_profile(clean_db, "customer"), seed_profile(clean_db, "owner")
    venue = _venue(clean_db, owner, "Detail", lat=12.97, lng=77.59, price=45000)
    cat = _category(clean_db, "yoga", "Yoga")
    _link(clean_db, venue, cat)
    am = sql(clean_db, "INSERT INTO public.amenities (slug, name) VALUES ('parking','Parking') RETURNING id")[
        0
    ]["id"]
    sql(clean_db, "INSERT INTO public.venue_amenities (venue_id, amenity_id) VALUES ($1,$2)", venue, am)
    sql(
        clean_db,
        "INSERT INTO public.venue_images (venue_id, storage_path, status, is_cover, sort_order) "
        "VALUES ($1,$2,'active',false,0), ($1,$3,'active',true,1), ($1,$4,'pending',false,2)",
        venue, f"{venue}/a.jpg", f"{venue}/cover.jpg", f"{venue}/pending.jpg",
    )  # fmt: skip
    r = api.get(f"/api/v1/venues/{venue}", headers=auth_headers(user))
    assert r.status_code == 200
    body = r.json()
    base = f"{SUPABASE_URL}/storage/v1/object/public/venue-images"
    assert body["cover_image_url"] == f"{base}/{venue}/cover.jpg"
    assert [i["is_cover"] for i in body["images"]] == [True, False]  # pending image hidden, cover first
    assert body["amenities"][0]["slug"] == "parking" and body["categories"] == ["yoga"]
    assert body["currency"] == "INR" and body["starting_price_paise"] == 45000
    assert body["is_favorite"] is False and body["rating_avg"] is None and body["rating_count"] == 0
    assert api.get(f"/api/v1/venues/{uuid.uuid4()}", headers=auth_headers(user)).status_code == 404


def test_favorites_lifecycle_and_isolation(api, clean_db):
    alice, bob = seed_profile(clean_db, "customer"), seed_profile(clean_db, "customer")
    owner = seed_profile(clean_db, "owner")
    v1 = _venue(clean_db, owner, "One", lat=12.9, lng=77.5)
    v2 = _venue(clean_db, owner, "Two", lat=12.9, lng=77.5)
    draft = _venue(clean_db, owner, "Draft", lat=12.9, lng=77.5, status="draft")
    ha, hb = auth_headers(alice), auth_headers(bob)

    assert api.get("/api/v1/favorites", headers=ha).json()["items"] == []
    assert api.post("/api/v1/favorites", json={"venue_id": str(v1)}, headers=ha).status_code == 204
    assert (
        api.post("/api/v1/favorites", json={"venue_id": str(v1)}, headers=ha).status_code == 204
    )  # idempotent
    assert api.post("/api/v1/favorites", json={"venue_id": str(v2)}, headers=ha).status_code == 204
    missing = api.post("/api/v1/favorites", json={"venue_id": str(draft)}, headers=ha)
    assert missing.status_code == 404 and missing.json()["code"] == "VENUE_NOT_FOUND"
    assert api.post("/api/v1/favorites", json={"venue_id": "nope"}, headers=ha).status_code == 422
    assert api.post("/api/v1/favorites", json={"venue_id": str(v1), "x": 1}, headers=ha).status_code == 422

    items = api.get("/api/v1/favorites", headers=ha).json()["items"]
    assert [i["name"] for i in items] == ["Two", "One"] and all(i["is_favorite"] for i in items)
    assert api.get("/api/v1/favorites", headers=hb).json()["items"] == []  # isolation
    flags = {v["name"]: v["is_favorite"] for v in api.get("/api/v1/venues", headers=ha).json()["items"]}
    assert flags == {"One": True, "Two": True}
    assert not any(v["is_favorite"] for v in api.get("/api/v1/venues", headers=hb).json()["items"])

    assert api.delete(f"/api/v1/favorites/{v1}", headers=hb).status_code == 204  # cannot touch Alice's
    assert len(api.get("/api/v1/favorites", headers=ha).json()["items"]) == 2
    assert api.delete(f"/api/v1/favorites/{v1}", headers=ha).status_code == 204
    assert api.delete(f"/api/v1/favorites/{v1}", headers=ha).status_code == 204  # idempotent
    assert [i["name"] for i in api.get("/api/v1/favorites", headers=ha).json()["items"]] == ["Two"]


def test_unpublished_favorite_is_hidden(api, clean_db):
    cust, owner = seed_profile(clean_db, "customer"), seed_profile(clean_db, "owner")
    v = seed_venue(clean_db, owner, "published", "Soon Gone")
    h = auth_headers(cust)
    api.post("/api/v1/favorites", json={"venue_id": str(v)}, headers=h)
    sql(clean_db, "UPDATE public.venues SET status='archived' WHERE id=$1", v)
    assert api.get("/api/v1/favorites", headers=h).json()["items"] == []


def test_favorites_are_customer_only(api, clean_db):
    owner = seed_profile(clean_db, "owner")
    h = auth_headers(owner)
    assert api.get("/api/v1/favorites", headers=h).status_code == 403
    assert api.post("/api/v1/favorites", json={"venue_id": str(uuid.uuid4())}, headers=h).status_code == 403
    assert api.get("/api/v1/venues", headers=h).status_code == 200  # owners may browse, not favorite
