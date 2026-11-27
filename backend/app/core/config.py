"""Application settings, loaded from environment variables (and an optional .env file).

Every variable is documented in docs/ENVIRONMENT_VARIABLES.md. No default in this
file is a credential. Missing credentials simply leave the related feature
"not configured"; in production the important ones are required at startup.
"""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]

_DEV_CORS_DEFAULT = ["http://localhost:3000", "http://127.0.0.1:3000"]
_ALLOWED_DB_SCHEMES = ("postgres://", "postgresql://", "postgresql+asyncpg://")
_OPTIONAL_TEXT_FIELDS = (
    "database_url",
    "alembic_database_url",
    "supabase_url",
    "supabase_anon_key",
    "supabase_service_role_key",
    "supabase_jwt_secret",
    "supabase_jwks_url",
    "supabase_jwt_issuer",
    "docs_enabled",
    "admin_require_mfa",
    "booking_hold_minutes",
    "razorpay_key_id",
    "razorpay_key_secret",
    "razorpay_webhook_secret",
    "firebase_project_id",
    "firebase_service_account",
    "resend_api_key",
    "google_maps_api_key",
    "email_from_address",
    "cancellation_min_notice_hours",
    "booking_min_notice_minutes",
    "booking_max_advance_days",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "ZURUV API"
    app_version: str = "0.1.0"
    environment: Environment = "development"
    log_level: str = "INFO"
    log_json: bool = True
    api_v1_prefix: str = "/api/v1"
    # None = automatic: enabled everywhere except production.
    docs_enabled: bool | None = None
    # Comma-separated list or JSON array. Mobile apps do not need CORS; only browsers do.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- Database (Supabase PostgreSQL) ---
    database_url: SecretStr | None = None
    # Optional separate URL for Alembic (direct or session-mode connection).
    alembic_database_url: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_timeout: int = Field(default=30, ge=1)
    db_connect_timeout: int = Field(default=10, ge=1)
    # 0 disables asyncpg prepared statements, required by the Supabase transaction pooler.
    db_statement_cache_size: int = Field(default=0, ge=0)
    # Use NullPool when an external pooler already does the pooling.
    db_use_nullpool: bool = False
    db_health_timeout: float = Field(default=3.0, gt=0)

    # --- Supabase ---
    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_storage_bucket_venue_images: str = "venue-images"
    supabase_storage_bucket_kyc: str = "kyc-documents"  # PRIVATE bucket, backend-only access

    # --- JWT verification (tokens issued by Supabase Auth) ---
    # Legacy projects sign with a shared HS256 secret; newer projects publish a JWKS.
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwks_url: str | None = None  # default: <SUPABASE_URL>/auth/v1/.well-known/jwks.json
    supabase_jwt_issuer: str | None = None  # default: <SUPABASE_URL>/auth/v1
    supabase_jwt_audience: str = "authenticated"
    jwt_leeway_seconds: int = Field(default=10, ge=0, le=120)
    # Admin endpoints require an MFA-verified session (token claim aal=aal2), decision D-24.
    # None = automatic: required in staging/production, not in development/test.
    admin_require_mfa: bool | None = None

    # --- Booking rules (Step 6). Unresolved business rules have NO default: unset = not applied ---
    # "hold": new bookings are pending_payment until payment is verified (Step 7) and need
    # BOOKING_HOLD_MINUTES (open question N4). "instant": bookings are confirmed immediately with
    # payment_status "unpaid"; for development/testing or venues that take no online payment.
    booking_mode: Literal["hold", "instant"] = "hold"
    booking_hold_minutes: int | None = Field(default=None, ge=1, le=1440)
    # A venue with several sports that each have an active activity commission rule: which one applies is a
    # client decision. UNSET (None) = such bookings get NO commission rate and are not accrued until decided.
    commission_activity_tiebreak: Literal["lowest", "highest"] | None = None
    # Customers may cancel a CONFIRMED booking only when this is set and enough notice remains (Q9).
    cancellation_min_notice_hours: int | None = Field(default=None, ge=0, le=8760)
    booking_min_notice_minutes: int | None = Field(default=None, ge=0, le=525600)  # N6
    booking_max_advance_days: int | None = Field(default=None, ge=1, le=730)  # N6

    # --- Payments, push and email (Step 7). Secrets exist ONLY in the backend environment. ---
    # Use Razorpay TEST keys (rzp_test_...) outside production. Unset = the feature is "not configured".
    razorpay_key_id: str | None = None  # public identifier, sent to the app with the order
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None  # separate from the API secret (set in dashboard)
    razorpay_api_base: str = "https://api.razorpay.com/v1"
    firebase_project_id: str | None = None
    # Service-account JSON, either the JSON text itself or a path to the JSON file.
    firebase_service_account: SecretStr | None = None
    resend_api_key: SecretStr | None = None
    # Google Places (address search). Unset = address search is "not configured".
    google_maps_api_key: SecretStr | None = None
    email_from_address: str | None = None  # e.g. "ZURUV <bookings@your-verified-domain>"
    # In-process housekeeping loop (outbox retry, payment reconciliation). 0 disables it.
    background_sweep_seconds: int = Field(default=60, ge=0, le=3600)
    payment_reconcile_after_minutes: int = Field(default=3, ge=1, le=1440)

    # Per-client request cap for write/expensive endpoints (app/core/ratelimit.py). 0 disables it.
    rate_limit_per_minute: int = Field(default=60, ge=0, le=100000)

    # Step 8: calendar used to bucket admin reports by day/week/month and to read date filters.
    # A presentation choice only (not a business rule); any IANA zone works.
    admin_report_timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    admin_export_max_rows: int = Field(default=20000, ge=1, le=200000)

    # ------------------------------------------------------------------ validators
    @field_validator(*_OPTIONAL_TEXT_FIELDS, mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("database_url", "alembic_database_url")
    @classmethod
    def _check_db_scheme(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().startswith(_ALLOWED_DB_SCHEMES):
            raise ValueError("must start with postgresql://, postgres:// or postgresql+asyncpg://")
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def _check_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("must start with '/' and must not end with '/'")
        return value

    @model_validator(mode="after")
    def _apply_environment_rules(self) -> "Settings":
        if self.environment != "production" and "cors_origins" not in self.model_fields_set:
            self.cors_origins = list(_DEV_CORS_DEFAULT)

        if self.environment == "production":
            problems: list[str] = []
            if self.database_url is None:
                problems.append("DATABASE_URL is required")
            if self.supabase_url is None and self.supabase_jwt_secret is None:
                problems.append("SUPABASE_URL (or SUPABASE_JWT_SECRET) is required")
            if "*" in self.cors_origins:
                problems.append("CORS_ORIGINS must not contain '*'")
            if problems:
                raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    # ------------------------------------------------------------------ derived values
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def razorpay_mode(self) -> str:
        """`test` / `live` from the key prefix (Razorpay's own convention); `unconfigured` or `unknown`."""
        key = self.razorpay_key_id
        if not key:
            return "unconfigured"
        if key.startswith("rzp_test_"):
            return "test"
        if key.startswith("rzp_live_"):
            return "live"
        return "unknown"

    @property
    def admin_mfa_required(self) -> bool:
        if self.admin_require_mfa is not None:
            return self.admin_require_mfa
        return self.environment in ("staging", "production")

    @property
    def database_configured(self) -> bool:
        return self.database_url is not None

    @property
    def docs_are_enabled(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        return not self.is_production

    @property
    def jwks_url(self) -> str | None:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    @property
    def jwt_issuer(self) -> str | None:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
