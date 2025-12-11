# backend/core/config.py

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional, List

# Get absolute path to backend/.env
BACKEND_DIR = Path(__file__).parent.parent
ENV_FILE = BACKEND_DIR / ".env"

class Settings(BaseSettings):
    # ===================
    # Application
    # ===================
    APP_NAME: str = "Social Sentiment Pricing API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
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
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # ===================
    # Redis / Celery
    # ===================
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    
    # ===================
    # External APIs
    # ===================
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # Reddit
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "SocialSentimentPricing/1.0"
    
    # Twitter/X (future)
    TWITTER_BEARER_TOKEN: Optional[str] = None
    
    # ===================
    # E-commerce Integrations
    # ===================
    # Shopify
    SHOPIFY_CLIENT_ID: Optional[str] = None
    SHOPIFY_CLIENT_SECRET: Optional[str] = None
    
    # WooCommerce (future)
    WOOCOMMERCE_CONSUMER_KEY: Optional[str] = None
    WOOCOMMERCE_CONSUMER_SECRET: Optional[str] = None
    
    # ===================
    # Notifications
    # ===================
    # SendGrid
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = None
    
    # Slack
    SLACK_WEBHOOK_URL: Optional[str] = None

    class Config:
        env_file = str(ENV_FILE)  # Absolute path to backend/.env
        extra = "ignore"


settings = Settings()
