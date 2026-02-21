# backend/api/v1/routes/trust_scoring.py

"""
API endpoints for Trust Scoring / Bot Detection.

Provides endpoints for:
- Author trust scoring
- Content spam/quality analysis
- Campaign detection
- Weighted sentiment calculation
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from core.deps import get_current_user
from models.user import User
from schemas.trust_scoring import (
    # Author scoring
    AuthorScoreRequest,
    AuthorScoreResponse,
    BatchAuthorScoreRequest,
    BatchAuthorScoreResponse,
    ComponentScores,
    # Content analysis
    ContentAnalysisRequest,
    ContentAnalysisResponse,
    BatchContentAnalysisRequest,
    BatchContentAnalysisResponse,
    SpamIndicators,
    # Campaign detection
    CampaignDetectionRequest,
    CampaignDetectionResponse,
    CampaignSignalResponse,
    # Weighted sentiment
    WeightedSentimentRequest,
    WeightedSentimentResponse,
    RawSentimentStats,
    AdjustedSentimentStats,
    QualityMetrics,
    # Quick checks
    QuickSpamCheckRequest,
    QuickSpamCheckResponse,
    QuickTrustCheckRequest,
    QuickTrustCheckResponse,
    # Stats
    TrustScoringStatsResponse,
    # Enums
    TrustLevelEnum,
    RiskFlagEnum,
)
from services.trust_scoring import (
    get_trust_scoring_service,
    TrustScoringService,
    AuthorProfile,
    calculate_spam_score,
    is_bot_username,
)

from services.trust_scoring import (
    get_trust_scoring_service,
    TrustScoringService,
    AuthorProfile,
    calculate_spam_score,
    is_bot_username,
)

router = APIRouter(prefix="/trust", tags=["Trust Scoring"])


# ─────────────────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────────────────

def get_service() -> TrustScoringService:
    """Get trust scoring service instance."""
    return get_trust_scoring_service()


# ─────────────────────────────────────────────────────────────────────────────
# Author Scoring Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/author/score",
    response_model=AuthorScoreResponse,
    summary="Score author trustworthiness",
    description="Calculate trust score for a social media author based on account metrics.",
)
async def score_author(
    request: AuthorScoreRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Score a single author's trustworthiness."""
    try:
        profile = AuthorProfile(
            author_id=request.author_id,
            username=request.username,
            source=request.source,
            follower_count=request.follower_count,
            following_count=request.following_count,
            post_count=request.post_count,
            created_at=request.account_created_at,
            is_verified=request.is_verified,
        )
        
        score = service.author_scorer.score_author(profile)
        
        return AuthorScoreResponse(
            author_id=score.author_id,
            source=score.source,
            trust_score=score.trust_score,
            trust_level=TrustLevelEnum(score.trust_level.value),
            risk_flags=[RiskFlagEnum(f.value) for f in score.risk_flags],
            risk_score=score.risk_score,
            component_scores=ComponentScores(
                account_age=score.account_age_score,
                followers=score.follower_score,
                engagement=score.engagement_score,
                history=score.history_score,
                verification_bonus=score.verification_bonus,
            ),
            confidence=score.confidence,
            calculated_at=score.calculated_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scoring author: {str(e)}")


@router.post(
    "/author/score/batch",
    response_model=BatchAuthorScoreResponse,
    summary="Score multiple authors",
    description="Calculate trust scores for multiple authors in one request.",
)
async def score_authors_batch(
    request: BatchAuthorScoreRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Score multiple authors at once."""
    scores = []
    total_trust = 0.0
    
    for author_req in request.authors:
        try:
            profile = AuthorProfile(
                author_id=author_req.author_id,
                username=author_req.username,
                source=author_req.source,
                follower_count=author_req.follower_count,
                following_count=author_req.following_count,
                post_count=author_req.post_count,
                created_at=author_req.account_created_at,
                is_verified=author_req.is_verified,
            )
            
            score = service.author_scorer.score_author(profile)
            total_trust += score.trust_score
            
            scores.append(AuthorScoreResponse(
                author_id=score.author_id,
                source=score.source,
                trust_score=score.trust_score,
                trust_level=TrustLevelEnum(score.trust_level.value),
                risk_flags=[RiskFlagEnum(f.value) for f in score.risk_flags],
                risk_score=score.risk_score,
                component_scores=ComponentScores(
                    account_age=score.account_age_score,
                    followers=score.follower_score,
                    engagement=score.engagement_score,
                    history=score.history_score,
                    verification_bonus=score.verification_bonus,
                ),
                confidence=score.confidence,
                calculated_at=score.calculated_at,
            ))
        except Exception as e:
            # Log error but continue with other authors
            continue
    
    return BatchAuthorScoreResponse(
        scores=scores,
        total=len(scores),
        avg_trust_score=total_trust / len(scores) if scores else 0.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Content Analysis Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/content/analyze",
    response_model=ContentAnalysisResponse,
    summary="Analyze content quality",
    description="Analyze content for spam, duplicates, and manipulation patterns.",
)
async def analyze_content(
    request: ContentAnalysisRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Analyze a single piece of content."""
    try:
        analysis = service.content_analyzer.analyze(
            content_id=request.content_id,
            text=request.text,
            author_username=request.author_username,
        )
        
        spam_score = calculate_spam_score(request.text, request.author_username)
        
        return ContentAnalysisResponse(
            content_id=analysis.content_id,
            word_count=analysis.word_count,
            is_duplicate=analysis.is_duplicate,
            duplicate_count=analysis.duplicate_count,
            content_quality_score=analysis.content_quality_score,
            originality_score=analysis.originality_score,
            risk_flags=[RiskFlagEnum(f.value) for f in analysis.risk_flags],
            spam_indicators=SpamIndicators(
                excessive_hashtags=analysis.has_excessive_hashtags,
                excessive_links=analysis.has_excessive_links,
                keyword_stuffing=analysis.has_keyword_stuffing,
                all_caps=analysis.has_all_caps,
                spam_phrases=analysis.has_spam_phrases,
            ),
            is_spam=spam_score >= 0.5,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing content: {str(e)}")


@router.post(
    "/content/analyze/batch",
    response_model=BatchContentAnalysisResponse,
    summary="Analyze multiple content pieces",
    description="Analyze multiple content pieces for spam and quality.",
)
async def analyze_content_batch(
    request: BatchContentAnalysisRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Analyze multiple pieces of content."""
    analyses = []
    spam_count = 0
    duplicate_count = 0
    
    for content_req in request.contents:
        try:
            analysis = service.content_analyzer.analyze(
                content_id=content_req.content_id,
                text=content_req.text,
                author_username=content_req.author_username,
            )
            
            spam_score = calculate_spam_score(content_req.text, content_req.author_username)
            is_spam = spam_score >= 0.5
            
            if is_spam:
                spam_count += 1
            if analysis.is_duplicate:
                duplicate_count += 1
            
            analyses.append(ContentAnalysisResponse(
                content_id=analysis.content_id,
                word_count=analysis.word_count,
                is_duplicate=analysis.is_duplicate,
                duplicate_count=analysis.duplicate_count,
                content_quality_score=analysis.content_quality_score,
                originality_score=analysis.originality_score,
                risk_flags=[RiskFlagEnum(f.value) for f in analysis.risk_flags],
                spam_indicators=SpamIndicators(
                    excessive_hashtags=analysis.has_excessive_hashtags,
                    excessive_links=analysis.has_excessive_links,
                    keyword_stuffing=analysis.has_keyword_stuffing,
                    all_caps=analysis.has_all_caps,
                    spam_phrases=analysis.has_spam_phrases,
                ),
                is_spam=is_spam,
            ))
        except Exception:
            continue
    
    return BatchContentAnalysisResponse(
        analyses=analyses,
        total=len(analyses),
        spam_count=spam_count,
        duplicate_count=duplicate_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Campaign Detection Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/campaign/detect",
    response_model=CampaignDetectionResponse,
    summary="Detect coordinated campaigns",
    description="Analyze mentions for coordinated manipulation campaigns.",
)
async def detect_campaign(
    request: CampaignDetectionRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Detect coordinated campaign activity."""
    try:
        # Convert to dict format expected by service
        mentions = [
            {
                "mention_id": m.mention_id,
                "author_id": m.author_id,
                "content": m.content,
                "published_at": m.published_at,
                "sentiment_score": m.sentiment_score,
                "source": m.source,
            }
            for m in request.mentions
        ]
        
        result = service.detect_campaign(
            mentions=mentions,
            product_id=request.product_id,
            time_window_hours=request.time_window_hours,
        )
        
        return CampaignDetectionResponse(
            product_id=result.product_id,
            time_window_hours=result.time_window_hours,
            is_campaign_detected=result.is_campaign_detected,
            campaign_confidence=result.campaign_confidence,
            signals=[
                CampaignSignalResponse(
                    signal_type=s.signal_type,
                    strength=s.strength,
                    description=s.description,
                )
                for s in result.signals
            ],
            metrics={
                "posts_analyzed": result.posts_analyzed,
                "unique_authors": result.unique_authors,
                "timing_anomaly_score": result.timing_anomaly_score,
                "content_similarity_score": result.content_similarity_score,
            },
            suspicious_author_count=len(result.suspicious_author_ids),
            suspicious_content_count=len(result.suspicious_content_ids),
            analyzed_at=result.analyzed_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting campaign: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Weighted Sentiment Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/sentiment/weighted",
    response_model=WeightedSentimentResponse,
    summary="Calculate trust-adjusted sentiment",
    description="Calculate sentiment with bot/manipulation filtering applied.",
)
async def calculate_weighted_sentiment(
    request: WeightedSentimentRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Calculate trust-adjusted sentiment for mentions."""
    try:
        # Convert to dict format with optional author metadata
        mentions = []
        for m in request.mentions:
            mention_dict = {
                "mention_id": m.mention_id,
                "author_id": m.author_id,
                "content": m.content,
                "published_at": m.published_at,
                "sentiment_score": m.sentiment_score,
                "source": m.source,
                "username": m.author_id,  # Default to author_id
            }
            
            # Add author metadata if provided
            if request.author_metadata and m.author_id in request.author_metadata:
                metadata = request.author_metadata[m.author_id]
                mention_dict.update({
                    "username": metadata.get("username", m.author_id),
                    "follower_count": metadata.get("follower_count"),
                    "account_created_at": metadata.get("account_created_at"),
                    "is_verified": metadata.get("is_verified", False),
                })
            
            mentions.append(mention_dict)
        
        result = service.calculate_trust_adjusted_sentiment(
            mentions=mentions,
            product_id=request.product_id,
            period_hours=request.period_hours,
            check_campaign=request.check_campaign,
        )
        
        return WeightedSentimentResponse(
            product_id=result.product_id,
            period_hours=result.period_hours,
            raw=RawSentimentStats(
                sentiment=result.raw_average_sentiment,
                mention_count=result.raw_mention_count,
            ),
            adjusted=AdjustedSentimentStats(
                sentiment=result.adjusted_average_sentiment,
                effective_mentions=result.effective_mention_count,
            ),
            quality=QualityMetrics(
                high_trust_ratio=result.high_trust_ratio,
                filtered_count=result.filtered_count,
                confidence=result.confidence,
            ),
            trust_breakdown=result.trust_level_breakdown,
            campaign_detected=result.filtered_count > result.raw_mention_count * 0.3,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating sentiment: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Quick Check Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/check/spam",
    response_model=QuickSpamCheckResponse,
    summary="Quick spam check",
    description="Quickly check if content is likely spam.",
)
async def quick_spam_check(
    request: QuickSpamCheckRequest,
    current_user: User = Depends(get_current_user),
):
    """Quick spam check for content."""
    spam_score = calculate_spam_score(request.text, request.username)
    
    reasons = []
    if spam_score >= 0.5:
        # Determine reasons
        from services.trust_scoring.utils import (
            has_spam_phrases,
            has_excessive_caps,
            has_keyword_stuffing,
            get_content_metrics,
        )
        
        metrics = get_content_metrics(request.text)
        
        if has_spam_phrases(request.text):
            reasons.append("Contains spam phrases")
        if metrics["hashtag_count"] > 5:
            reasons.append("Excessive hashtags")
        if metrics["link_count"] > 2:
            reasons.append("Excessive links")
        if has_excessive_caps(request.text):
            reasons.append("Excessive caps")
        if has_keyword_stuffing(request.text):
            reasons.append("Keyword stuffing")
        if request.username and is_bot_username(request.username):
            reasons.append("Bot-like username")
    
    return QuickSpamCheckResponse(
        is_spam=spam_score >= 0.5,
        spam_score=spam_score,
        reasons=reasons,
    )


@router.post(
    "/check/trust",
    response_model=QuickTrustCheckResponse,
    summary="Quick trust check",
    description="Quickly check if an author is trustworthy.",
)
async def quick_trust_check(
    request: QuickTrustCheckRequest,
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Quick trust check for an author."""
    from datetime import timedelta
    
    created_at = None
    if request.account_age_days is not None:
        created_at = datetime.now(timezone.utc) - timedelta(days=request.account_age_days)
    
    score = service.score_author(
        author_id=request.author_id,
        username=request.username,
        source=request.source,
        follower_count=request.follower_count,
        created_at=created_at,
    )
    
    return QuickTrustCheckResponse(
        is_trustworthy=score.trust_score >= 0.4,
        trust_score=score.trust_score,
        trust_level=TrustLevelEnum(score.trust_level.value),
        risk_flags=[f.value for f in score.risk_flags],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Statistics & Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=TrustScoringStatsResponse,
    summary="Get service statistics",
    description="Get trust scoring service statistics and cache info.",
)
async def get_stats(
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Get service statistics."""
    stats = service.get_stats()
    
    return TrustScoringStatsResponse(
        content_analyzer=stats["content_analyzer"],
        config=stats["config"],
        cache_stats={
            "hash_cache_size": stats["content_analyzer"].get("hash_cache_size", 0),
            "fuzzy_cache_size": stats["content_analyzer"].get("fuzzy_cache_size", 0),
            "recent_content_size": stats["content_analyzer"].get("recent_content_size", 0),
        },
    )


@router.post(
    "/cache/clear",
    summary="Clear caches",
    description="Clear all trust scoring caches.",
)
async def clear_caches(
    current_user: User = Depends(get_current_user),
    service: TrustScoringService = Depends(get_service),
):
    """Clear all caches."""
    service.clear_caches()
    return {"success": True, "message": "All caches cleared"}




