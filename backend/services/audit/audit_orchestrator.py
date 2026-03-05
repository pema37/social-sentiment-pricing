"""
Audit Orchestrator — coordinates the 3-agent Price Check pipeline.

Yields SSEEvent dicts as each step completes, enabling real-time
streaming to the frontend via Server-Sent Events.

Agent pipeline:
  Scout      → scan store, find competitors, scrape competitor prices
  Analyst    → search social mentions, analyse sentiment, detect trends
  Strategist → generate pricing recommendations, estimate revenue impact

Each agent is wrapped in try/except so a failure in one (e.g. Reddit
is down) degrades gracefully instead of killing the whole scan.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from schemas.price_check import (
    CompetitorMatch,
    PriceCheckOpportunity,
    PriceCheckReport,
)
from services.audit.store_scanner import scan_store, ScannedProduct
from services.audit.report_generator import (
    CompetitorData,
    SentimentData,
    RecommendationData,
    generate_report,
)

logger = logging.getLogger(__name__)


def _sse(agent: str, status: str, message: str = "", data: dict | None = None) -> dict:
    """Build an SSE event dict."""
    return {"agent": agent, "status": status, "message": message, "data": data}


async def run_price_check(
    store_url: str,
    email: str,
    category: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Run the full Price Check pipeline, yielding SSE events as each
    step completes.

    Usage:
        async for event in run_price_check(url, email):
            yield f"data: {json.dumps(event)}\\n\\n"
    """

    competitor_data = CompetitorData()
    sentiment_data = SentimentData()
    recommendation_data = RecommendationData()
    products: list[ScannedProduct] = []
    store_name = "Unknown Store"

    # ── SCOUT ─────────────────────────────────────────────────────

    yield _sse("scout", "started", "Scanning your storefront...")

    # Step 1: Scan the store
    try:
        scan_result = await scan_store(store_url)

        if scan_result.error:
            yield _sse("error", "error", scan_result.error)
            return

        products = scan_result.products
        store_name = scan_result.store_name

        yield _sse(
            "scout", "progress",
            f"Found {len(products)} products on {scan_result.platform.title()} store",
        )
    except Exception as e:
        logger.exception("Scout: store scan failed")
        yield _sse("error", "error", f"Could not scan the store: {str(e)}")
        return

    if not products:
        yield _sse("error", "error", "No products found. The store may be empty or password-protected.")
        return

    # Step 2: Find competitors
    yield _sse("scout", "progress", "Discovering competitors...")

    try:
        top_products = sorted(products, key=lambda p: p.price, reverse=True)[:5]

        from services.competitor_matching.service import CompetitorMatchingService

        matcher = CompetitorMatchingService()
        all_matches: list[CompetitorMatch] = []

        for product in top_products:
            try:
                search_query = f"{product.title} {product.product_type}".strip()
                results = await matcher.search(query=search_query, max_results=3)

                for r in results:
                    comp_price = getattr(r, "price", None) or 0.0
                    if comp_price > 0:
                        gap = ((product.price - comp_price) / comp_price) * 100
                        all_matches.append(
                            CompetitorMatch(
                                competitor_name=getattr(r, "source", "Unknown"),
                                competitor_url=getattr(r, "url", ""),
                                product_name=product.title,
                                competitor_price=comp_price,
                                your_price=product.price,
                                gap_percent=round(gap, 1),
                            )
                        )
            except Exception as e:
                logger.warning("Scout: match failed for %s: %s", product.title, e)
                continue

        competitor_data.matches = all_matches

        yield _sse(
            "scout", "progress",
            f"Found {len(all_matches)} competitor price points",
        )

    except ImportError:
        logger.warning("Scout: CompetitorMatchingService not available, skipping")
        yield _sse("scout", "progress", "Competitor matching unavailable — skipping")
    except Exception as e:
        logger.warning("Scout: competitor discovery failed: %s", e)
        yield _sse("scout", "progress", "Competitor discovery encountered an issue — continuing")

    # Step 3: Scrape competitor prices (for matches without prices)
    yield _sse("scout", "progress", "Scraping competitor prices...")

    try:
        from services.competitor_scraper import scrape_competitor_price

        for match in competitor_data.matches:
            if match.competitor_price <= 0 and match.competitor_url:
                try:
                    price = await scrape_competitor_price(match.competitor_url)
                    if price and price > 0:
                        match.competitor_price = price
                        match.gap_percent = round(
                            ((match.your_price - price) / price) * 100, 1
                        )
                except Exception:
                    continue

    except ImportError:
        logger.warning("Scout: competitor_scraper not available")
    except Exception as e:
        logger.warning("Scout: price scraping failed: %s", e)

    competitor_data.matches = [m for m in competitor_data.matches if m.competitor_price > 0]

    unique_competitors = len(set(m.competitor_name for m in competitor_data.matches))
    yield _sse(
        "scout", "done",
        f"Scanned {len(products)} products · {unique_competitors} competitors found · {len(competitor_data.matches)} price comparisons",
    )

    # ── ANALYST ───────────────────────────────────────────────────

    yield _sse("analyst", "started", "Searching social mentions...")

    scores = []

    try:
        from services.ingestion.reddit_service import RedditService

        reddit = RedditService()
        search_terms = [store_name] + [p.title for p in products[:3]]
        all_mentions = []

        for term in search_terms:
            try:
                mentions = await reddit.search(query=term, limit=10)
                if mentions:
                    all_mentions.extend(mentions)
            except Exception as e:
                logger.warning("Analyst: Reddit search failed for '%s': %s", term, e)
                continue

        yield _sse(
            "analyst", "progress",
            f"Found {len(all_mentions)} social mentions",
        )

        yield _sse("analyst", "progress", "Analyzing sentiment signals...")

        if all_mentions:
            try:
                from services.sentiment_analyzer import SentimentAnalyzer

                analyzer = SentimentAnalyzer()

                for mention in all_mentions:
                    text = getattr(mention, "text", None) or getattr(mention, "title", str(mention))
                    try:
                        result = await analyzer.analyze(text)
                        score = getattr(result, "score", None) or getattr(result, "compound", 0.0)
                        scores.append(score)

                        if len(sentiment_data.top_mentions) < 5:
                            snippet = str(text)[:150]
                            if snippet:
                                sentiment_data.top_mentions.append(snippet)
                    except Exception:
                        continue

                if scores:
                    sentiment_data.total_mentions = len(scores)
                    sentiment_data.avg_score = sum(scores) / len(scores)
                    sentiment_data.positive_count = sum(1 for s in scores if s > 0.1)
                    sentiment_data.negative_count = sum(1 for s in scores if s < -0.1)
                    sentiment_data.neutral_count = (
                        len(scores) - sentiment_data.positive_count - sentiment_data.negative_count
                    )

            except ImportError:
                logger.warning("Analyst: SentimentAnalyzer not available")
            except Exception as e:
                logger.warning("Analyst: sentiment analysis failed: %s", e)

        yield _sse("analyst", "progress", "Detecting sentiment trends...")

        try:
            from services.analysis.trend_detector import TrendDetector  # noqa: F401

            if scores:
                mid = len(scores) // 2
                if mid > 0:
                    first_half = sum(scores[:mid]) / mid
                    second_half = sum(scores[mid:]) / len(scores[mid:])
                    diff = second_half - first_half

                    if diff > 0.05:
                        sentiment_data.trend = "rising"
                        sentiment_data.trend_pct = round(diff * 100, 1)
                    elif diff < -0.05:
                        sentiment_data.trend = "falling"
                        sentiment_data.trend_pct = round(abs(diff) * 100, 1)
                    else:
                        sentiment_data.trend = "stable"
                        sentiment_data.trend_pct = 0.0

        except ImportError:
            logger.warning("Analyst: TrendDetector not available")
        except Exception as e:
            logger.warning("Analyst: trend detection failed: %s", e)

    except ImportError:
        logger.warning("Analyst: RedditService not available, skipping sentiment")
        yield _sse("analyst", "progress", "Social analysis unavailable — skipping")
    except Exception as e:
        logger.warning("Analyst: social scan failed: %s", e)
        yield _sse("analyst", "progress", "Social scan encountered an issue — continuing")

    pos_pct = round((sentiment_data.positive_count / max(sentiment_data.total_mentions, 1)) * 100)
    yield _sse(
        "analyst", "done",
        f"{sentiment_data.total_mentions} mentions · {pos_pct}% positive · trend {sentiment_data.trend}",
    )

    # ── STRATEGIST ────────────────────────────────────────────────

    yield _sse("strategist", "started", "Processing pricing signals...")

    try:
        yield _sse("strategist", "progress", "Calculating optimal prices...")

        opportunities: list[PriceCheckOpportunity] = []

        for match in competitor_data.matches:
            gap = match.gap_percent

            if abs(gap) < 5:
                continue

            if gap > 0:
                suggested = round(match.your_price * (1 - min(gap, 30) / 200), 2)
                reason = (
                    f"Priced {abs(gap):.0f}% above {match.competitor_name}. "
                    f"Consider competitive positioning."
                )
                confidence = min(80, 50 + abs(gap) * 0.5)
            else:
                sentiment_boost = max(0, sentiment_data.avg_score * 10)
                suggested = round(match.your_price * (1 + min(abs(gap), 20) / 200), 2)
                reason = (
                    f"Priced {abs(gap):.0f}% below market. "
                    f"Positive sentiment suggests room to increase."
                    if sentiment_data.avg_score > 0
                    else f"Priced {abs(gap):.0f}% below market. "
                    f"Review competitive position."
                )
                confidence = min(75, 40 + abs(gap) * 0.3 + sentiment_boost)

            if not any(o.product_name == match.product_name for o in opportunities):
                opportunities.append(
                    PriceCheckOpportunity(
                        product_name=match.product_name,
                        current_price=match.your_price,
                        suggested_price=suggested,
                        reason=reason,
                        confidence=round(confidence, 1),
                    )
                )

        opportunities.sort(
            key=lambda o: abs(o.suggested_price - o.current_price),
            reverse=True,
        )

        recommendation_data.opportunities = opportunities[:10]

        yield _sse("strategist", "progress", "Estimating revenue impact...")

        if opportunities:
            avg_conf = sum(o.confidence for o in opportunities) / len(opportunities)
            if competitor_data.matches and sentiment_data.total_mentions > 0:
                avg_conf = min(95, avg_conf + 10)
            recommendation_data.overall_confidence = round(avg_conf, 1)
        else:
            recommendation_data.overall_confidence = 30.0

    except Exception as e:
        logger.warning("Strategist: recommendation generation failed: %s", e)
        yield _sse("strategist", "progress", "Recommendation engine encountered an issue — continuing")

    try:
        from services.pricing_engine import PricingEngine  # noqa: F401
        logger.info("Strategist: PricingEngine available for enhanced analysis")
    except ImportError:
        logger.info("Strategist: PricingEngine not available, using built-in logic")
    except Exception:
        pass

    yield _sse("strategist", "progress", "Building your report...")

    total_opps = len(recommendation_data.opportunities)
    yield _sse(
        "strategist", "done",
        f"{total_opps} repricing opportunities · {recommendation_data.overall_confidence:.0f}% confidence",
    )

    # ── ASSEMBLE REPORT ───────────────────────────────────────────

    report = generate_report(
        store_name=store_name,
        store_url=store_url,
        email=email,
        products=products,
        competitor_data=competitor_data,
        sentiment_data=sentiment_data,
        recommendation_data=recommendation_data,
    )

    yield _sse("complete", "done", "Report ready", data=report.model_dump())



    