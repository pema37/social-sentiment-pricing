"""
Calculation utilities for trend analysis.
Handles sentiment calculations, trend detection, and metrics.
"""

from datetime import datetime, timedelta, UTC


class TrendCalculators:
    """Calculation methods for trend analysis metrics."""
    
    # ==========================================
    # Sentiment Calculations
    # ==========================================
    
    @staticmethod
    def calculate_avg_sentiment(sentiment_data: list[dict]) -> float:
        """Calculate average sentiment score."""
        if not sentiment_data:
            return 0.0
        scores = [s["score"] for s in sentiment_data]
        return sum(scores) / len(scores)
    
    @staticmethod
    def calculate_sentiment_trend(sentiment_data: list[dict]) -> str:
        """Determine overall sentiment trend."""
        if len(sentiment_data) < 7:
            return "stable"
        
        # Compare first half vs second half
        mid = len(sentiment_data) // 2
        recent = [s["score"] for s in sentiment_data[:mid]]
        older = [s["score"] for s in sentiment_data[mid:]]
        
        recent_avg = sum(recent) / len(recent) if recent else 0
        older_avg = sum(older) / len(older) if older else 0
        
        diff = recent_avg - older_avg
        if diff > 0.1:
            return "rising"
        elif diff < -0.1:
            return "falling"
        return "stable"
    
    @staticmethod
    def calculate_sentiment_volatility(sentiment_data: list[dict]) -> float:
        """Calculate sentiment score volatility (standard deviation)."""
        if len(sentiment_data) < 2:
            return 0.0
        
        scores = [s["score"] for s in sentiment_data]
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return variance ** 0.5
    
    # ==========================================
    # Volume Calculations
    # ==========================================
    
    @staticmethod
    def calculate_volume_change(mentions_data: list[dict], days: int) -> float:
        """Calculate mention volume change percentage."""
        if not mentions_data or days < 14:
            return 0.0
        
        mid_date = datetime.now(UTC) - timedelta(days=days // 2)
        recent = [m for m in mentions_data if m["created_at"] >= mid_date]
        older = [m for m in mentions_data if m["created_at"] < mid_date]
        
        if not older:
            return 0.0
        
        recent_daily = len(recent) / (days // 2)
        older_daily = len(older) / (days // 2)
        
        if older_daily == 0:
            return 100.0 if recent_daily > 0 else 0.0
        
        return ((recent_daily - older_daily) / older_daily) * 100
    
    # ==========================================
    # Competitor Calculations
    # ==========================================
    
    @staticmethod
    def summarize_competitor_changes(competitor_data: list[dict]) -> str:
        """Summarize recent competitor price changes."""
        if not competitor_data:
            return "No competitor data available"
        return f"{len(competitor_data)} competitors tracked"
    
    # ==========================================
    # Product Performance
    # ==========================================
    
    @staticmethod
    def get_top_performing_product(products: list, sentiment_data: list[dict]) -> str:
        """Get the product with highest sentiment."""
        if not products:
            return "N/A"
        
        if not sentiment_data:
            return products[0].name if products else "N/A"
        
        # Calculate average sentiment per product
        product_scores = {}
        for s in sentiment_data:
            pid = str(s.get("product_id", ""))
            if pid not in product_scores:
                product_scores[pid] = []
            product_scores[pid].append(s["score"])
        
        if not product_scores:
            return products[0].name if products else "N/A"
        
        # Find product with highest average
        best_pid = max(product_scores.keys(), key=lambda p: sum(product_scores[p]) / len(product_scores[p]))
        
        # Find product name
        for p in products:
            if str(p.id) == best_pid:
                return p.name
        
        return products[0].name if products else "N/A"
    
    @staticmethod
    def get_worst_performing_product(products: list, sentiment_data: list[dict]) -> str:
        """Get the product with lowest sentiment."""
        if not products:
            return "N/A"
        
        if not sentiment_data:
            return products[-1].name if products else "N/A"
        
        # Calculate average sentiment per product
        product_scores = {}
        for s in sentiment_data:
            pid = str(s.get("product_id", ""))
            if pid not in product_scores:
                product_scores[pid] = []
            product_scores[pid].append(s["score"])
        
        if not product_scores:
            return products[-1].name if products else "N/A"
        
        # Find product with lowest average
        worst_pid = min(product_scores.keys(), key=lambda p: sum(product_scores[p]) / len(product_scores[p]))
        
        # Find product name
        for p in products:
            if str(p.id) == worst_pid:
                return p.name
        
        return products[-1].name if products else "N/A"
    
    # ==========================================
    # Trend Detection
    # ==========================================
    
    @staticmethod
    def detect_basic_trends(sentiment_data: list[dict]) -> list[dict]:
        """Detect basic trends in the data."""
        trends = []
        
        if not sentiment_data:
            return trends
        
        # Check for overall trend
        if len(sentiment_data) >= 7:
            recent_scores = [s["score"] for s in sentiment_data[:7]]
            older_scores = [s["score"] for s in sentiment_data[7:14]] if len(sentiment_data) > 7 else recent_scores
            
            recent_avg = sum(recent_scores) / len(recent_scores)
            older_avg = sum(older_scores) / len(older_scores)
            
            diff = recent_avg - older_avg
            if diff > 0.2:
                trends.append({
                    "type": "sentiment_rise",
                    "description": f"Sentiment increased by {diff:.2f} points"
                })
            elif diff < -0.2:
                trends.append({
                    "type": "sentiment_drop",
                    "description": f"Sentiment decreased by {abs(diff):.2f} points"
                })
        
        # Check for volume spike
        if len(sentiment_data) >= 14:
            recent_count = len([s for s in sentiment_data[:7]])
            older_count = len([s for s in sentiment_data[7:14]])
            
            if older_count > 0 and recent_count > older_count * 1.5:
                trends.append({
                    "type": "volume_spike",
                    "description": f"Mention volume increased {(recent_count/older_count - 1) * 100:.0f}%"
                })
        
        return trends
    
    @staticmethod
    def detect_notable_events(sentiment_data: list[dict], mentions_data: list[dict]) -> list[dict]:
        """Detect notable events (volume spikes, sentiment shifts)."""
        events = []
        
        # Detect sudden sentiment changes
        if len(sentiment_data) >= 3:
            for i in range(len(sentiment_data) - 2):
                current = sentiment_data[i]["score"]
                previous = sentiment_data[i + 1]["score"]
                
                if abs(current - previous) > 0.5:
                    events.append({
                        "type": "sentiment_shift",
                        "date": sentiment_data[i]["created_at"].strftime("%Y-%m-%d"),
                        "description": f"Sudden sentiment change: {previous:.2f} → {current:.2f}"
                    })
                    break  # Only report the most recent
        
        return events



        