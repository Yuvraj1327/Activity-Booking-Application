import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.conftest import make_settings


def test_defaults_have_no_credentials():
    s = make_settings()
    assert s.database_url is None and s.supabase_service_role_key is None
    assert not s.database_configured
    assert s.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_cors_parsing():
    assert make_settings(cors_origins="http://a.com, http://b.com").cors_origins == [
        "http://a.com",
        "http://b.com",
    ]
    assert make_settings(cors_origins='["http://a.com"]').cors_origins == ["http://a.com"]


def test_blank_values_are_none():
    assert make_settings(database_url="  ").database_url is None


def test_bad_database_scheme_rejected():
    with pytest.raises(ValidationError):
        make_settings(database_url="mysql://x")


def test_production_requires_database_and_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        make_settings(environment="production")
    with pytest.raises(ValidationError):
        make_settings(
            environment="production",
            database_url="postgresql://u:p@h/d",
            supabase_url="https://x.supabase.co",
            cors_origins="*",
        )


def test_docs_disabled_in_production_by_default():
    s = make_settings(
        environment="production",
        database_url="postgresql://u:p@h/d",
        supabase_url="https://x.supabase.co",
        cors_origins="https://admin.example.com",
    )
    assert s.docs_are_enabled is False


def test_secrets_not_in_repr():
    s = make_settings(database_url="postgresql://u:topsecret@h/d")
    assert "topsecret" not in repr(s)


def test_step7_provider_settings_default_to_not_configured_and_hide_secrets():
    s = Settings(
        _env_file=None, environment="test", razorpay_key_id="", razorpay_key_secret="", resend_api_key=""
    )
    assert s.razorpay_key_id is None and s.razorpay_key_secret is None and s.resend_api_key is None
    t = Settings(
        _env_file=None,
        environment="test",
        razorpay_key_secret="super-secret-value",
        razorpay_webhook_secret="hook-secret-value",
        firebase_service_account='{"private_key": "-----BEGIN PRIVATE KEY-----"}',
        resend_api_key="re_secret_value",
    )
    text = repr(t) + str(t.model_dump())
    for leaked in ("super-secret-value", "hook-secret-value", "BEGIN PRIVATE KEY", "re_secret_value"):
        assert leaked not in text
