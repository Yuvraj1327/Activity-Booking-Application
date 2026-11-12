"""Step 10: Google Places proxy. The key stays on the server; Google is faked, never called."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.gateways.places import GooglePlaces, PlaceDetails, PlacesError, PlaceSuggestion
from app.main import create_app
from tests.booking_helpers import API
from tests.conftest import JWT_SECRET, SUPABASE_URL, auth_headers, make_settings, seed_profile


class FakePlaces:
    def __init__(self, configured: bool = True) -> None:
        self._configured = configured
        self.calls: list[tuple] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def autocomplete(self, text, session_token):
        self.calls.append(("autocomplete", text, session_token))
        if text == "boom":
            raise PlacesError("upstream")
        return [PlaceSuggestion("ChIJabcdefghijk", "Koramangala, Bengaluru, India")]

    async def details(self, place_id):
        self.calls.append(("details", place_id))
        if place_id == "ChIJmissingmissing":
            raise PlacesError("nope", not_found=True)
        return PlaceDetails(place_id, "Smash Arena", "80 Feet Rd, Bengaluru", 12.93, 77.62, "560034")


def client(db: str, places) -> TestClient:
    cfg = make_settings(supabase_jwt_secret=JWT_SECRET, supabase_url=SUPABASE_URL, database_url=db)
    app = create_app(cfg)
    app.state.places_gateway = places
    return TestClient(app)


def test_autocomplete_and_details_for_any_signed_in_role(clean_db):
    owner = auth_headers(seed_profile(clean_db, "owner"))
    cust = auth_headers(seed_profile(clean_db, "customer"))
    fake = FakePlaces()
    with client(clean_db, fake) as api:
        for h in (owner, cust):
            r = api.get(
                f"{API}/places/autocomplete", params={"q": "koram", "session_token": "abc-123"}, headers=h
            )
            assert r.status_code == 200 and r.json()[0]["place_id"] == "ChIJabcdefghijk"
        d = api.get(f"{API}/places/ChIJabcdefghijk", headers=owner).json()
        assert (d["latitude"], d["longitude"], d["postal_code"]) == (12.93, 77.62, "560034")
    assert ("autocomplete", "koram", "abc-123") in fake.calls


def test_requires_authentication_and_validates_input(clean_db):
    cust = auth_headers(seed_profile(clean_db, "customer"))
    with client(clean_db, FakePlaces()) as api:
        assert api.get(f"{API}/places/autocomplete", params={"q": "koram"}).status_code == 401
        assert api.get(f"{API}/places/autocomplete", params={"q": "k"}, headers=cust).status_code == 422
        assert api.get(f"{API}/places/autocomplete", params={"q": "x" * 101}, headers=cust).status_code == 422
        assert (
            api.get(
                f"{API}/places/autocomplete", params={"q": "ok", "session_token": "a b!"}, headers=cust
            ).status_code
            == 422
        )
        bad = api.get(f"{API}/places/..%2F..%2Fadmin", headers=cust)
        assert bad.status_code in (404, 422)
        r = api.get(f"{API}/places/short", headers=cust)
        assert (r.status_code, r.json()["code"]) == (422, "INVALID_PLACE_ID")


def test_not_configured_is_honest_not_faked(clean_db):
    cust = auth_headers(seed_profile(clean_db, "customer"))
    with client(clean_db, FakePlaces(configured=False)) as api:
        r = api.get(f"{API}/places/autocomplete", params={"q": "koram"}, headers=cust)
        assert (r.status_code, r.json()["code"]) == (503, "PLACES_NOT_CONFIGURED")
        r = api.get(f"{API}/places/ChIJabcdefghijk", headers=cust)
        assert (r.status_code, r.json()["code"]) == (503, "PLACES_NOT_CONFIGURED")


def test_upstream_failures_and_missing_places(clean_db):
    cust = auth_headers(seed_profile(clean_db, "customer"))
    with client(clean_db, FakePlaces()) as api:
        r = api.get(f"{API}/places/autocomplete", params={"q": "boom"}, headers=cust)
        assert (r.status_code, r.json()["code"]) == (503, "PLACES_UNAVAILABLE")
        r = api.get(f"{API}/places/ChIJmissingmissing", headers=cust)
        assert (r.status_code, r.json()["code"]) == (404, "PLACE_NOT_FOUND")


# ------------------------------------------------------------------ the real adapter against a fake HTTP server
def _gateway(handler) -> GooglePlaces:
    cfg = Settings(_env_file=None, google_maps_api_key="test-key-not-real", environment="test")
    return GooglePlaces(cfg, httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.mark.asyncio
async def test_adapter_sends_the_key_as_a_header_and_parses_google_responses():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path.endswith("places:autocomplete"):
            return httpx.Response(
                200,
                json={
                    "suggestions": [
                        {"placePrediction": {"placeId": "ChIJabcdefghijk", "text": {"text": "Koramangala"}}}
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "ChIJabcdefghijk",
                "displayName": {"text": "Smash Arena"},
                "formattedAddress": "80 Feet Rd",
                "location": {"latitude": 12.9, "longitude": 77.6},
                "addressComponents": [{"types": ["postal_code"], "longText": "560034"}],
            },
        )

    gw = _gateway(handler)
    assert gw.configured
    suggestions = await gw.autocomplete("koram", "tok")
    assert [(s.place_id, s.description) for s in suggestions] == [("ChIJabcdefghijk", "Koramangala")]
    assert json.loads(seen[0].content) == {"input": "koram", "sessionToken": "tok"}
    d = await gw.details("ChIJabcdefghijk")
    assert (d.name, d.postal_code, d.latitude) == ("Smash Arena", "560034", 12.9)
    for req in seen:
        assert req.headers["X-Goog-Api-Key"] == "test-key-not-real"
        assert "key=" not in str(req.url)  # the key is never put in a URL that could be logged


@pytest.mark.asyncio
async def test_adapter_maps_google_errors():
    gw = _gateway(lambda req: httpx.Response(404 if "/places/" in req.url.path else 403, json={}))
    with pytest.raises(PlacesError) as nf:
        await gw.details("ChIJabcdefghijk")
    assert nf.value.not_found
    with pytest.raises(PlacesError):
        await gw.autocomplete("koram", None)
    unconfigured = GooglePlaces(Settings(_env_file=None, environment="test"))
    assert not unconfigured.configured
    with pytest.raises(PlacesError):
        await unconfigured.autocomplete("koram", None)
