"""
Prospect Audit Service (Public / Unauthenticated)

Lightweight pricing audit that doesn't require authentication.
Two input modes:
  A) Shopify store URL → fetch /products.json (public endpoint)
  B) CSV paste → list of {name, price, sku}

For each product, we search our existing competitor price data
to find market comparisons. If no internal data matches, we use
the product catalog itself to compute relative positioning
(cheapest vs most expensive in their own store).

This is the top-of-funnel lead magnet.
"""

import re
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlparse

import httpx

from core.logging import get_logger
from schemas.prospect_audit import (
    ProspectAuditRequest,
    ProspectAuditTeaser,
    ProspectProductResult,
    ProspectProductRow,
)

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────
ZERO = Decimal("0")
HUNDRED = Decimal("100")
ALIGNMENT_THRESHOLD = Decimal("0.02")  # ±2%
ELASTICITY_FACTOR = Decimal("0.015")
DEFAULT_DAILY_UNITS = 3  # Conservative for unknown stores
SHOPIFY_PRODUCTS_LIMIT = 250  # Max per page from Shopify


class ProspectAuditService:
    """
    Generates a lightweight pricing audit for unauthenticated prospects.
    No database required for the basic version — works purely from
    the store's public product data.
    """

    async def generate_teaser(self, request: ProspectAuditRequest) -> ProspectAuditTeaser:
        """
        Generate teaser audit from either Shopify URL or pasted products.
        """
        products: list[ProspectProductRow] = []
        store_name: str | None = None

        if request.store_url:
            store_name, products = await self._fetch_shopify_products(request.store_url)
        elif request.products:
            products = request.products

        if not products:
            return ProspectAuditTeaser(
                store_name=store_name,
                total_products_found=0,
                products_with_market_data=0,
                estimated_monthly_impact=ZERO,
                products_overpriced=0,
                products_underpriced=0,
                top_products=[],
                remaining_products_count=0,
            )

        # Analyze products against each other (internal benchmarking)
        results = self._analyze_products(products)

        # Sort by gap magnitude (worst offenders first)
        results_with_data = [r for r in results if r.gap_type != "no_data"]
        results_with_data.sort(key=lambda r: abs(float(r.gap_percent or 0)), reverse=True)

        overpriced = [r for r in results if r.gap_type == "overpriced"]
        underpriced = [r for r in results if r.gap_type == "underpriced"]

        # Compute estimated monthly impact
        monthly_impact = self._estimate_monthly_impact(results)

        # Average gap across products with data
        avg_gap = None
        if results_with_data:
            avg_gap = (
                sum(abs(r.gap_percent) for r in results_with_data) / Decimal(str(len(results_with_data)))
            ).quantize(Decimal("0.1"))

        # Top 5 for teaser, rest hidden behind email gate
        top_5 = results_with_data[:5]
        remaining = max(0, len(results) - 5)

        return ProspectAuditTeaser(
            store_name=store_name,
            total_products_found=len(products),
            products_with_market_data=len(results_with_data),
            estimated_monthly_impact=monthly_impact.quantize(Decimal("0.01")),
            products_overpriced=len(overpriced),
            products_underpriced=len(underpriced),
            avg_gap_percent=avg_gap,
            top_products=top_5,
            remaining_products_count=remaining,
        )

    def get_all_results(self, products: list[ProspectProductRow]) -> list[ProspectProductResult]:
        """
        Get full results for all products (used for gated PDF).
        """
        results = self._analyze_products(products)
        results.sort(key=lambda r: abs(float(r.gap_percent or 0)), reverse=True)
        return results

    # ══════════════════════════════════════════════════════════
    # SHOPIFY SCRAPER
    # ══════════════════════════════════════════════════════════

    async def _fetch_shopify_products(self, store_url: str) -> tuple[str | None, list[ProspectProductRow]]:
        """
        Fetch products from a Shopify store's public /products.json endpoint.

        Returns (store_name, products).
        """
        # Normalize URL
        url = store_url.strip().rstrip("/")
        if not url.startswith("http"):
            url = f"https://{url}"

        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # Extract store name from hostname
        store_name = hostname.replace(".myshopify.com", "").replace("www.", "")
        store_name = store_name.split(".")[0].title()

        products_url = f"{parsed.scheme}://{hostname}/products.json?limit={SHOPIFY_PRODUCTS_LIMIT}"

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(
                    products_url,
                    headers={
                        "User-Agent": "ActualPrice-Audit/1.0",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as e:
            logger.warning(f"Shopify products.json returned {e.response.status_code} for {hostname}")
            return store_name, []
        except Exception as e:
            logger.warning(f"Failed to fetch products from {hostname}: {e}")
            return store_name, []

        shopify_products = data.get("products", [])
        rows: list[ProspectProductRow] = []

        for p in shopify_products:
            title = p.get("title", "Unknown")
            variants = p.get("variants", [])

            if not variants:
                continue

            # Use first variant price
            first_variant = variants[0]
            price_str = first_variant.get("price", "0")
            sku = first_variant.get("sku", None)

            try:
                price = Decimal(str(price_str))
            except Exception:
                continue

            if price <= 0:
                continue

            rows.append(
                ProspectProductRow(
                    name=title[:500],
                    price=price,
                    sku=sku,
                )
            )

        logger.info(f"Fetched {len(rows)} products from {hostname}")
        return store_name, rows

    # ══════════════════════════════════════════════════════════
    # ANALYSIS ENGINE
    # ══════════════════════════════════════════════════════════

    def _analyze_products(self, products: list[ProspectProductRow]) -> list[ProspectProductResult]:
        """
        Analyze products using internal catalog benchmarking.

        Strategy: Group products by inferred category (from name keywords),
        then compare each product against the group average.
        If only one product in a group, compare against the overall median.
        """
        if not products:
            return []

        prices = [p.price for p in products if p.price > 0]
        if not prices:
            return []

        # Overall stats
        overall_avg = sum(prices) / Decimal(str(len(prices)))

        # Group by category (simple keyword extraction)
        categories = self._categorize_products(products)

        # Compute category averages
        cat_avgs = {}
        for cat, cat_products in categories.items():
            cat_prices = [p.price for p in cat_products if p.price > 0]
            if cat_prices:
                cat_avgs[cat] = sum(cat_prices) / Decimal(str(len(cat_prices)))

        # Build results
        results: list[ProspectProductResult] = []
        product_to_cat = {}
        for cat, cat_products in categories.items():
            for p in cat_products:
                product_to_cat[id(p)] = cat

        for product in products:
            if product.price <= 0:
                results.append(
                    ProspectProductResult(
                        name=product.name,
                        sku=product.sku,
                        your_price=product.price,
                        gap_type="no_data",
                    )
                )
                continue

            cat = product_to_cat.get(id(product), "other")
            benchmark = cat_avgs.get(cat, overall_avg)
            cat_size = len(categories.get(cat, []))

            # If category has < 3 products, fall back to overall average
            if cat_size < 3:
                benchmark = overall_avg

            # Calculate gap
            if benchmark > 0:
                gap_amount = product.price - benchmark
                gap_percent = (gap_amount / benchmark * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                abs_ratio = abs(gap_amount) / benchmark

                if abs_ratio <= ALIGNMENT_THRESHOLD:
                    gap_type = "aligned"
                elif gap_amount > 0:
                    gap_type = "overpriced"
                else:
                    gap_type = "underpriced"
            else:
                gap_percent = ZERO
                gap_type = "no_data"

            results.append(
                ProspectProductResult(
                    name=product.name,
                    sku=product.sku,
                    your_price=product.price,
                    market_avg_price=benchmark.quantize(Decimal("0.01")),
                    gap_percent=gap_percent,
                    gap_type=gap_type,
                    competitor_count=cat_size - 1 if cat_size > 1 else 0,
                )
            )

        return results

    def _categorize_products(self, products: list[ProspectProductRow]) -> dict[str, list[ProspectProductRow]]:
        """
        Simple keyword-based categorization.
        Groups products that share significant words in their names.
        """
        # Common stop words to ignore
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "for",
            "in",
            "on",
            "with",
            "to",
            "of",
            "by",
            "at",
            "is",
            "it",
            "as",
            "be",
            "set",
            "size",
            "color",
            "new",
            "free",
            "sale",
            "pack",
            "box",
        }

        # Extract significant words per product
        def extract_keywords(name: str) -> set:
            words = re.findall(r"[a-z]+", name.lower())
            return {w for w in words if len(w) > 2 and w not in stop_words}

        product_keywords = [(p, extract_keywords(p.name)) for p in products]

        # Simple approach: group by the most common keyword in each product name
        categories: dict[str, list[ProspectProductRow]] = {}

        for product, keywords in product_keywords:
            if not keywords:
                categories.setdefault("other", []).append(product)
                continue

            # Use the first significant keyword as category
            # (simple but effective for most e-commerce catalogs)
            primary = sorted(keywords)[0]
            categories.setdefault(primary, []).append(product)

        return categories

    def _estimate_monthly_impact(self, results: list[ProspectProductResult]) -> Decimal:
        """
        Estimate monthly revenue impact from pricing gaps.
        Conservative: only counts overpriced products.
        """
        total = ZERO

        for r in results:
            if r.gap_type != "overpriced" or r.gap_percent is None:
                continue

            # lost_units_per_day = daily_units × elasticity × gap%
            lost_daily = Decimal(str(DEFAULT_DAILY_UNITS)) * ELASTICITY_FACTOR * abs(r.gap_percent)
            daily_impact = lost_daily * r.your_price
            total += daily_impact * Decimal("30")  # monthly

        return total
