"""
Data formatters for AI prompts.
Converts database objects into formatted strings for AI consumption.
"""

from models.product import Product


class DataFormatter:
    """Formats data for AI prompts."""

    # ==========================================
    # Product Formatting
    # ==========================================

    @staticmethod
    def format_products(products: list[Product]) -> str:
        """Format products for AI prompt."""
        if not products:
            return "No products"

        lines = []
        for p in products[:20]:  # Limit to 20 products
            line = f"- {p.name}: ${p.base_price}"
            if p.category:
                line += f" (Category: {p.category})"
            lines.append(line)

        return "\n".join(lines)

    # ==========================================
    # Sentiment Formatting
    # ==========================================

    @staticmethod
    def format_sentiment_history(sentiment_data: list[dict]) -> str:
        """Format sentiment history for AI prompt."""
        if not sentiment_data:
            return "No sentiment data available"

        # Group by date and average
        by_date = {}
        for s in sentiment_data:
            date_key = s["created_at"].strftime("%Y-%m-%d")
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(s["score"])

        lines = []
        for date, scores in sorted(by_date.items(), reverse=True)[:14]:  # Last 14 days
            avg = sum(scores) / len(scores)
            lines.append(f"- {date}: {avg:.2f} (n={len(scores)})")

        return "\n".join(lines)

    @staticmethod
    def format_sentiment_drops(drops: list[dict]) -> str:
        """Format sentiment drops for risk prompt."""
        if not drops:
            return "No significant sentiment drops detected"
        return "\n".join([f"- {d}" for d in drops])

    # ==========================================
    # Mentions Formatting
    # ==========================================

    @staticmethod
    def format_mentions_summary(mentions_data: list[dict]) -> str:
        """Format mentions summary for AI prompt."""
        if not mentions_data:
            return "No mentions data available"

        # Count by platform
        platforms = {}
        for m in mentions_data:
            platform = m.get("platform", "unknown")
            platforms[platform] = platforms.get(platform, 0) + 1

        lines = [f"Total mentions: {len(mentions_data)}"]
        for platform, count in sorted(platforms.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {platform}: {count}")

        return "\n".join(lines)

    @staticmethod
    def format_recent_mentions(mentions: list) -> str:
        """Format recent mentions for prompt."""
        if not mentions:
            return "No recent mentions"

        lines = []
        for m in mentions[:10]:
            content = m.content[:100] if m.content else ""
            score = m.sentiment_score if m.sentiment_score else 0
            lines.append(f"- [{score:.2f}] {content}...")

        return "\n".join(lines)

    @staticmethod
    def format_negative_mentions(mentions: list) -> str:
        """Format negative mentions for risk prompt."""
        if not mentions:
            return "No significant negative mentions"

        lines = []
        for m in mentions[:20]:
            content = m.content[:100] if m.content else ""
            score = m.sentiment_score if m.sentiment_score else 0
            lines.append(f"- [{score:.2f}] {content}")

        return "\n".join(lines)

    # ==========================================
    # Competitor Formatting
    # ==========================================

    @staticmethod
    def format_competitor_data(competitor_data: list[dict]) -> str:
        """Format competitor data for AI prompt."""
        if not competitor_data:
            return "No competitor data available"

        lines = []
        for c in competitor_data[:20]:
            lines.append(f"- {c.get('competitor_name', 'Unknown')}: ${c.get('competitor_price', 0):.2f}")

        return "\n".join(lines)

    @staticmethod
    def format_competitor_prices(competitors: list) -> str:
        """Format competitor prices for opportunity prompt."""
        if not competitors:
            return "No competitor prices available"

        lines = []
        for c in competitors:
            name = c.competitor_name if hasattr(c, "competitor_name") else "Competitor"
            price = c.price if c.price else 0
            lines.append(f"- {name}: ${price:.2f}")

        return "\n".join(lines)

    @staticmethod
    def format_competitor_activities(activities: list[dict]) -> str:
        """Format competitor activities for risk prompt."""
        if not activities:
            return "No recent competitor activities"
        return "\n".join([f"- {a}" for a in activities])

    # ==========================================
    # Alerts Formatting
    # ==========================================

    @staticmethod
    def format_current_alerts(alerts: list) -> str:
        """Format current alerts for risk prompt."""
        if not alerts:
            return "No active alerts"

        lines = []
        for a in alerts[:10]:
            alert_type = a.alert_type if hasattr(a, "alert_type") else "unknown"
            message = a.message if hasattr(a, "message") else ""
            lines.append(f"- {alert_type}: {message}")

        return "\n".join(lines)

    # ==========================================
    # Trends & Events Formatting
    # ==========================================

    @staticmethod
    def format_trends(trends: list[dict]) -> str:
        """Format detected trends."""
        if not trends:
            return "No significant trends detected"
        return "\n".join([f"- {t}" for t in trends])

    @staticmethod
    def format_events(events: list[dict]) -> str:
        """Format notable events."""
        if not events:
            return "No notable events"
        return "\n".join([f"- {e}" for e in events])
