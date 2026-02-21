# backend/schemas/sentiment.py
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


# ============== Request Schemas ==============

class SentimentAnalyzeRequest(BaseModel):
    """Analyze a single piece of text"""
    text: str = Field(..., min_length=1)
    source: str = Field(default="manual", max_length=50)
    author: Optional[str] = None
    url: Optional[str] = None


class SentimentBulkItem(BaseModel):
    """Single item for bulk analysis"""
    text: str = Field(..., min_length=1)
    source: Optional[str] = None
    author: Optional[str] = None
    url: Optional[str] = None


class SentimentBulkRequest(BaseModel):
    """Analyze multiple texts at once"""
    items: List[SentimentBulkItem]


# ============== Response Schemas ==============

class SentimentScores(BaseModel):
    """VADER sentiment scores"""
    compound: Decimal = Field(ge=-1, le=1)
    positive: Decimal = Field(ge=0, le=1)
    negative: Decimal = Field(ge=0, le=1)
    neutral: Decimal = Field(ge=0, le=1)


class SentimentRead(BaseModel):
    id: UUID
    product_id: UUID
    source: str
    raw_text: str
    compound_score: Decimal
    positive_score: Decimal
    negative_score: Decimal
    neutral_score: Decimal
    author: Optional[str]
    url: Optional[str]
    analyzed_at: datetime

    class Config:
        from_attributes = True


class SentimentAnalyzeResponse(BaseModel):
    """Response for single text analysis"""
    text: str
    scores: SentimentScores
    label: str
    saved: bool = False
    sentiment_id: Optional[UUID] = None


class SentimentSummary(BaseModel):
    """Aggregated sentiment for a product"""
    product_id: UUID
    total_mentions: int = 0
    total_records: int = 0
    average_compound: Optional[Decimal] = None
    average_score: Optional[Decimal] = None
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    label_distribution: Optional[dict] = None
    trend: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class SentimentResponse(BaseModel):
    """Response matching route expectations"""
    sentiment_id: Optional[UUID] = None
    text: Optional[str] = None
    sentiment_score: float = Field(ge=-1, le=1)
    sentiment_label: str
    confidence: float = Field(ge=0, le=1)
    emotions: Optional[dict] = None
    # AI-powered fields
    topics: Optional[List[str]] = None
    is_sarcastic: Optional[bool] = None
    ai_powered: bool = False

    class Config:
        from_attributes = True


class SocialMentionResponse(BaseModel):
    """Response for social mention data"""
    id: UUID
    product_id: UUID
    source: str
    source_id: Optional[str] = None
    content: str
    author: Optional[str] = None
    author_followers: Optional[int] = None
    engagement_count: Optional[int] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    collected_at: datetime
    processed: bool = False

    class Config:
        from_attributes = True


class AIStatusResponse(BaseModel):
    """Response for AI status check"""
    openai_available: bool
    model: Optional[str] = None
    features: List[str] = []
