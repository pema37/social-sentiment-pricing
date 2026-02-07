# backend/core/config.py
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional, List

BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # ===================
    # Application
    # ===================
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
    # CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    CORS_ORIGINS: str = "*"
    
    @property
    def cors_origins_list(self) -> List[str]:
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
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1  # 10% of transactions
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or console
    
    # ===================
    # External APIs
    # ===================
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    YOUCOM_API_KEY: Optional[str] = None
    
    # Reddit
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "SocialSentimentPricing/1.0"
    
    # Twitter/X (future)
    TWITTER_BEARER_TOKEN: Optional[str] = None
    
    # ===================
    # E-commerce Integrations
    # ===================
    SHOPIFY_CLIENT_ID: Optional[str] = None
    SHOPIFY_CLIENT_SECRET: Optional[str] = None
    WOOCOMMERCE_CONSUMER_KEY: Optional[str] = None
    WOOCOMMERCE_CONSUMER_SECRET: Optional[str] = None
    
    # ===================
    # Notifications
    # ===================
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    
    # ===================
    # Alerting
    # ===================
    ALERT_EMAIL: Optional[str] = None  # Email for critical alerts
    PAGERDUTY_KEY: Optional[str] = None  # PagerDuty integration key

    # ===================
    # MNEE Payments
    # ===================
    MNEE_API_KEY: str = ""
    MNEE_ENVIRONMENT: str = "sandbox"  # sandbox or production
    MNEE_WEBHOOK_SECRET: str = ""
    SSP_MNEE_WALLET_ADDRESS: str = ""  # Your BSV receiving address 
    
    
    class Config:
        env_file = str(ENV_FILE)
        extra = "ignore"


settings = Settings()
