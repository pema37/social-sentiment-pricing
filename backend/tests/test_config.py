"""
Test Suite: backend/core/config.py
Covers: Settings class — defaults, required fields, env var parsing,
        CORS origins list property, path resolution.

Place at: backend/tests/test_config.py
Run: pytest backend/tests/test_config.py -v
"""

import sys
from unittest.mock import MagicMock

# Required env vars that have no defaults
REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
    "JWT_SECRET_KEY": "test-secret-key-for-testing-only",
    "ENCRYPTION_KEY": "test-encryption-key-32chars-long!",
}


def _get_settings_class():
    """Get the real Settings class, cleaning up MagicMock pollution if needed."""
    if isinstance(sys.modules.get("core.config"), MagicMock):
        del sys.modules["core.config"]
    from core.config import Settings

    return Settings


def make_settings(**overrides):
    """Create Settings with required env vars + overrides, ignoring .env file."""
    Settings = _get_settings_class()
    env = {**REQUIRED_ENV, **overrides}
    return Settings(**env, _env_file=None)


# =====================================================================
# Path Constants
# =====================================================================


class TestPathConstants:
    def test_backend_dir_exists(self):
        if isinstance(sys.modules.get("core.config"), MagicMock):
            del sys.modules["core.config"]
        from core.config import BACKEND_DIR

        assert BACKEND_DIR.is_dir()

    def test_env_file_path(self):
        if isinstance(sys.modules.get("core.config"), MagicMock):
            del sys.modules["core.config"]
        from core.config import BACKEND_DIR, ENV_FILE

        assert ENV_FILE == BACKEND_DIR / ".env"


# =====================================================================
# Required Fields
# =====================================================================


class TestRequiredFields:
    """Verify DATABASE_URL, JWT_SECRET_KEY, ENCRYPTION_KEY are required (no defaults)."""

    def test_database_url_is_required(self):
        Settings = _get_settings_class()
        field = Settings.model_fields["DATABASE_URL"]
        assert field.is_required(), "DATABASE_URL should have no default"

    def test_jwt_secret_is_required(self):
        Settings = _get_settings_class()
        field = Settings.model_fields["JWT_SECRET_KEY"]
        assert field.is_required(), "JWT_SECRET_KEY should have no default"

    def test_encryption_key_is_required(self):
        Settings = _get_settings_class()
        field = Settings.model_fields["ENCRYPTION_KEY"]
        assert field.is_required(), "ENCRYPTION_KEY should have no default"

    def test_all_required_provided(self):
        s = make_settings()
        assert s.DATABASE_URL == REQUIRED_ENV["DATABASE_URL"]
        assert s.JWT_SECRET_KEY == REQUIRED_ENV["JWT_SECRET_KEY"]
        assert s.ENCRYPTION_KEY == REQUIRED_ENV["ENCRYPTION_KEY"]


# =====================================================================
# Application Defaults
# =====================================================================


class TestApplicationDefaults:
    def test_app_name(self):
        s = make_settings()
        assert s.APP_NAME == "Social Sentiment Pricing API"

    def test_app_version(self):
        s = make_settings()
        assert s.APP_VERSION == "0.1.0"

    def test_debug_default(self):
        s = make_settings()
        assert s.DEBUG is False

    def test_environment_default(self):
        s = make_settings()
        assert s.ENVIRONMENT == "development"

    def test_debug_override(self):
        s = make_settings(DEBUG=True)
        assert s.DEBUG is True

    def test_environment_override(self):
        s = make_settings(ENVIRONMENT="production")
        assert s.ENVIRONMENT == "production"


# =====================================================================
# URL Defaults
# =====================================================================


class TestURLDefaults:
    def test_backend_url(self):
        s = make_settings()
        assert s.BACKEND_URL == "http://localhost:8000"

    def test_frontend_url(self):
        s = make_settings()
        assert s.FRONTEND_URL == "http://localhost:3000"


# =====================================================================
# JWT / Security Defaults
# =====================================================================


class TestSecurityDefaults:
    def test_algorithm(self):
        s = make_settings()
        assert s.ALGORITHM == "HS256"

    def test_access_token_expire(self):
        s = make_settings()
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_reset_token_expire(self):
        s = make_settings()
        assert s.RESET_TOKEN_EXPIRE_MINUTES == 30

    def test_access_token_override(self):
        s = make_settings(ACCESS_TOKEN_EXPIRE_MINUTES=120)
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 120


# =====================================================================
# CORS
# =====================================================================


class TestCORS:
    def test_cors_default(self):
        s = make_settings()
        assert s.CORS_ORIGINS == "*"

    def test_cors_origins_list_wildcard(self):
        s = make_settings()
        assert s.cors_origins_list == ["*"]

    def test_cors_origins_list_multiple(self):
        s = make_settings(CORS_ORIGINS="http://localhost:3000,http://localhost:5173")
        assert s.cors_origins_list == ["http://localhost:3000", "http://localhost:5173"]

    def test_cors_origins_list_trims_whitespace(self):
        s = make_settings(CORS_ORIGINS="http://a.com , http://b.com , http://c.com")
        assert s.cors_origins_list == ["http://a.com", "http://b.com", "http://c.com"]

    def test_cors_origins_single(self):
        s = make_settings(CORS_ORIGINS="https://actualprice.app")
        assert s.cors_origins_list == ["https://actualprice.app"]


# =====================================================================
# Redis / Celery Defaults
# =====================================================================


class TestRedisDefaults:
    def test_redis_url(self):
        s = make_settings()
        assert s.REDIS_URL == "redis://localhost:6379/0"

    def test_celery_broker(self):
        s = make_settings()
        assert s.CELERY_BROKER_URL == "redis://localhost:6379/1"


# =====================================================================
# Monitoring Defaults
# =====================================================================


class TestMonitoringDefaults:
    def test_sentry_dsn_none(self):
        s = make_settings()
        assert s.SENTRY_DSN is None

    def test_sentry_traces_rate(self):
        s = make_settings()
        assert s.SENTRY_TRACES_SAMPLE_RATE == 0.1

    def test_log_level(self):
        s = make_settings()
        assert s.LOG_LEVEL == "INFO"

    def test_log_format(self):
        s = make_settings()
        assert s.LOG_FORMAT == "json"


# =====================================================================
# External API Defaults (all Optional, None)
# =====================================================================


class TestExternalAPIDefaults:
    """
    Optional API keys default to None, but may be set in the real environment.
    We test that (a) the field accepts None and (b) it accepts a string value.
    """

    def test_optional_keys_accept_none(self):
        s = make_settings(
            OPENAI_API_KEY=None,
            GEMINI_API_KEY=None,
            YOUCOM_API_KEY=None,
            REDDIT_CLIENT_ID=None,
            REDDIT_CLIENT_SECRET=None,
            TWITTER_BEARER_TOKEN=None,
            SHOPIFY_CLIENT_ID=None,
            SHOPIFY_CLIENT_SECRET=None,
        )
        assert s.OPENAI_API_KEY is None
        assert s.GEMINI_API_KEY is None
        assert s.SHOPIFY_CLIENT_ID is None

    def test_optional_keys_accept_values(self):
        s = make_settings(
            OPENAI_API_KEY="sk-test",
            GEMINI_API_KEY="gemini-test",
        )
        assert s.OPENAI_API_KEY == "sk-test"
        assert s.GEMINI_API_KEY == "gemini-test"

    def test_reddit_user_agent(self):
        s = make_settings()
        assert s.REDDIT_USER_AGENT == "SocialSentimentPricing/1.0"


# =====================================================================
# MNEE Payment Defaults
# =====================================================================


class TestMNEEDefaults:
    def test_mnee_api_key_empty(self):
        s = make_settings()
        assert s.MNEE_API_KEY == ""

    def test_mnee_environment(self):
        s = make_settings()
        assert s.MNEE_ENVIRONMENT == "sandbox"

    def test_mnee_override(self):
        s = make_settings(MNEE_ENVIRONMENT="production", MNEE_API_KEY="live_key")
        assert s.MNEE_ENVIRONMENT == "production"
        assert s.MNEE_API_KEY == "live_key"


# =====================================================================
# Extra Fields Ignored
# =====================================================================


class TestExtraIgnored:
    def test_extra_fields_ignored(self):
        s = make_settings(NONEXISTENT_FIELD="should_be_ignored")
        assert not hasattr(s, "NONEXISTENT_FIELD")
