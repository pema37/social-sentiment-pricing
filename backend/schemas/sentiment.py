# backend/schemas/sentiment.py
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ============== Request Schemas ==============


class SentimentAnalyzeRequest(BaseModel):
    """Analyze a single piece of text"""

    text: str = Field(..., min_length=1)
    source: str = Field(default="manual", max_length=50)
    author: str | None = None
    url: str | None = None


class SentimentBulkItem(BaseModel):
    """Single item for bulk analysis"""

    text: str = Field(..., min_length=1)
    source: str | None = None
    author: str | None = None
    url: str | None = None


class SentimentBulkRequest(BaseModel):
    """Analyze multiple texts at once"""

    items: list[SentimentBulkItem]


# ============== Response Schemas ==============


class SentimentScores(BaseModel):
    """VADER sentiment scores"""

    compound: Decimal = Field(ge=-1, le=1)
    positive: Decimal = Field(ge=0, le=1)
    negative: Decimal = Field(ge=0, le=1)
    neutral: Decimal = Field(ge=0, le=1)


class SentimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    source: str
    raw_text: str
    compound_score: Decimal
    positive_score: Decimal
    negative_score: Decimal
    neutral_score: Decimal
    author: str | None
    url: str | None
    analyzed_at: datetime


class SentimentAnalyzeResponse(BaseModel):
    """Response for single text analysis"""

    text: str
    scores: SentimentScores
    label: str
    saved: bool = False
    sentiment_id: UUID | None = None


class SentimentSummary(BaseModel):
    """Aggregated sentiment for a product"""

    product_id: UUID
    total_mentions: int = 0
    total_records: int = 0
    average_compound: Decimal | None = None
    average_score: Decimal | None = None
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    label_distribution: dict | None = None
    trend: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None


class SentimentResponse(BaseModel):
    """Response matching route expectations"""

    model_config = ConfigDict(from_attributes=True)
    sentiment_id: UUID | None = None
    text: str | None = None
    sentiment_score: float = Field(ge=-1, le=1)
    sentiment_label: str
    confidence: float = Field(ge=0, le=1)
    emotions: dict | None = None
    # AI-powered fields
    topics: list[str] | None = None
    is_sarcastic: bool | None = None
    ai_powered: bool = False


class SocialMentionResponse(BaseModel):
    """Response for social mention data"""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    source: str
    source_id: str | None = None
    content: str
    author: str | None = None
    author_followers: int | None = None
    engagement_count: int | None = None
    url: str | None = None
    published_at: datetime | None = None
    collected_at: datetime
    processed: bool = False


class AIStatusResponse(BaseModel):
    """Response for AI status check"""

    openai_available: bool
    model: str | None = None
    features: list[str] = []
