import time

import jwt
import pytest

from app.core.errors import AuthenticationError
from app.core.security import JWTVerifier

SECRET = "x" * 48
ISS = "https://proj.supabase.co/auth/v1"


def verifier(**kw):
    return JWTVerifier(secret=SECRET, jwks_url=None, audience="authenticated", issuer=ISS, **kw)


def token(**over):
    claims = {
        "sub": "user-1",
        "aud": "authenticated",
        "iss": ISS,
        "exp": int(time.time()) + 600,
        "role": "authenticated",
        "email": "a@b.co",
    }
    claims.update(over)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_valid_token():
    c = verifier().verify(token())
    assert c.sub == "user-1" and c.role == "authenticated"


def test_expired_token():
    with pytest.raises(AuthenticationError) as e:
        verifier(leeway=0).verify(token(exp=int(time.time()) - 60))
    assert e.value.code == "TOKEN_EXPIRED"


@pytest.mark.parametrize("over", [{"aud": "other"}, {"iss": "https://evil/auth/v1"}])
def test_wrong_audience_or_issuer(over):
    with pytest.raises(AuthenticationError):
        verifier().verify(token(**over))


def test_bad_signature():
    bad = jwt.encode({"sub": "u", "exp": int(time.time()) + 60}, "y" * 48, algorithm="HS256")
    with pytest.raises(AuthenticationError):
        verifier().verify(bad)


def test_alg_none_rejected():
    forged = jwt.encode({"sub": "u", "exp": int(time.time()) + 60}, None, algorithm="none")
    with pytest.raises(AuthenticationError):
        verifier().verify(forged)


def test_garbage_rejected():
    with pytest.raises(AuthenticationError):
        verifier().verify("not-a-jwt")


def test_missing_sub_rejected():
    t = jwt.encode(
        {"aud": "authenticated", "iss": ISS, "exp": int(time.time()) + 60},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        verifier().verify(t)


def test_hs_token_without_secret_rejected():
    v = JWTVerifier(secret=None, jwks_url=None, audience="authenticated", issuer=ISS)
    assert not v.configured
    with pytest.raises(AuthenticationError):
        v.verify(token())
