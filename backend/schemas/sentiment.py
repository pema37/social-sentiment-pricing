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


class SentimentBulkRequest(BaseModel):
    """Analyze multiple texts at once"""
    product_id: UUID
    items: List[SentimentAnalyzeRequest]


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
    total_mentions: int
    average_compound: Decimal
    positive_count: int
    negative_count: int
    neutral_count: int
    trend: str
    period_start: datetime
    period_end: datetime



class SentimentResponse(BaseModel):
    """Response matching route expectations"""
    sentiment_id: Optional[UUID] = None
    text: Optional[str] = None
    sentiment_score: Decimal = Field(ge=-1, le=1)
    sentiment_label: str
    confidence: Decimal = Field(ge=0, le=1)
    emotions: Optional[dict] = None

    class Config:
        from_attributes = True
