# backend/core/config.py
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # ===================
    # Application
    # ===================
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )
    APP_NAME: str = "Social Sentiment Pricing API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production

    # ===================
    # Database
    # ===================
    DATABASE_URL: str

    # ===================
    # URLs
    # ===================
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # ===================
    # Security / JWT
    # ===================
    JWT_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY: str

    # ===================
    # CORS
    # ===================
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # ===================
    # Redis / Celery
    # ===================
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # ===================
    # Monitoring & Observability
    # ===================
    SENTRY_DSN: str | None = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1  # 10% of transactions
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or console

    # ===================
    # External APIs
    # ===================
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    YOUCOM_API_KEY: str | None = None

    # Reddit
    REDDIT_CLIENT_ID: str | None = None
    REDDIT_CLIENT_SECRET: str | None = None
    REDDIT_USER_AGENT: str = "SocialSentimentPricing/1.0"

    # Twitter/X (future)
    TWITTER_BEARER_TOKEN: str | None = None

    # ===================
    # E-commerce Integrations
    # ===================
    SHOPIFY_CLIENT_ID: str | None = None
    SHOPIFY_CLIENT_SECRET: str | None = None
    WOOCOMMERCE_CONSUMER_KEY: str | None = None
    WOOCOMMERCE_CONSUMER_SECRET: str | None = None

    # ===================
    # Notifications
    # ===================
    SENDGRID_API_KEY: str | None = None
    SENDGRID_FROM_EMAIL: str | None = None
    SLACK_WEBHOOK_URL: str | None = None

    # ===================
    # Alerting
    # ===================
    ALERT_EMAIL: str | None = None  # Email for critical alerts
    PAGERDUTY_KEY: str | None = None  # PagerDuty integration key

    # ===================
    # Feature Flags
    # ===================
    # Must be explicitly set to True in env; never defaults to True in production.
    DEMO_MODE: bool = False

    # ===================
    # MNEE Payments
    # ===================
    MNEE_API_KEY: str = ""
    MNEE_ENVIRONMENT: str = "sandbox"  # sandbox or production
    MNEE_WEBHOOK_SECRET: str = ""
    SSP_MNEE_WALLET_ADDRESS: str = ""  # Your BSV receiving address
    SSP_ETH_WALLET_ADDRESS: str = ""  # Your ETH receiving address


settings = Settings()


