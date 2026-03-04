"""
Store Scanner — fetches public product catalogs from Shopify / WooCommerce.

No API keys required. Uses the public storefront JSON endpoints:
  - Shopify:      GET https://{store}/products.json?limit=30
  - WooCommerce:  GET https://{store}/wp-json/wc/store/products?per_page=30
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 15.0
MAX_PRODUCTS = 30
USER_AGENT = "ActualPrice-Scanner/1.0 (+https://getactualprice.com)"


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class ScannedProduct:
    title: str
    price: float
    compare_at_price: float | None = None
    product_type: str = ""
    vendor: str = ""
    image_url: str = ""
    url: str = ""


@dataclass
class ScanResult:
    store_name: str = ""
    store_url: str = ""
    platform: str = "unknown"  # "shopify" | "woocommerce" | "unknown"
    products: list[ScannedProduct] = field(default_factory=list)
    error: str = ""


# ── URL normalisation ─────────────────────────────────────────────────

def _normalise_url(raw: str) -> str:
    """Ensure the URL has a scheme and strip trailing slashes."""
    raw = raw.strip().rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw


def _extract_store_name(url: str) -> str:
    """Best-effort store name from the URL hostname."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    # Remove common suffixes
    name = re.sub(r"\.(myshopify\.com|com|net|org|co|io|store|shop)$", "", host)
    name = name.replace("www.", "").replace("-", " ").replace(".", " ")
    return name.strip().title() or "Unknown Store"


# ── Platform detection ────────────────────────────────────────────────

async def _detect_platform(client: httpx.AsyncClient, base_url: str) -> str:
    """Try Shopify first (more common), then WooCommerce."""
    # Shopify check
    try:
        r = await client.get(f"{base_url}/products.json?limit=1", follow_redirects=True)
        if r.status_code == 200:
            data = r.json()
            if "products" in data:
                return "shopify"
    except Exception:
        pass

    # WooCommerce check
    try:
        r = await client.get(
            f"{base_url}/wp-json/wc/store/products?per_page=1",
            follow_redirects=True,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return "woocommerce"
    except Exception:
        pass

    return "unknown"


# ── Shopify scanner ───────────────────────────────────────────────────

async def _scan_shopify(client: httpx.AsyncClient, base_url: str) -> list[ScannedProduct]:
    """Fetch products from Shopify's public /products.json endpoint."""
    url = f"{base_url}/products.json?limit={MAX_PRODUCTS}"
    r = await client.get(url, follow_redirects=True)
    r.raise_for_status()
    data = r.json()

    products: list[ScannedProduct] = []
    for p in data.get("products", []):
        # Use the first variant's price
        variants = p.get("variants", [])
        if not variants:
            continue

        price_str = variants[0].get("price", "0")
        compare_str = variants[0].get("compare_at_price")

        try:
            price = float(price_str)
        except (ValueError, TypeError):
            continue

        if price <= 0:
            continue

        compare_at = None
        if compare_str:
            try:
                compare_at = float(compare_str)
            except (ValueError, TypeError):
                pass

        image_url = ""
        images = p.get("images", [])
        if images:
            image_url = images[0].get("src", "")

        products.append(
            ScannedProduct(
                title=p.get("title", "Untitled"),
                price=price,
                compare_at_price=compare_at,
                product_type=p.get("product_type", ""),
                vendor=p.get("vendor", ""),
                image_url=image_url,
                url=f"{base_url}/products/{p.get('handle', '')}",
            )
        )

    return products


# ── WooCommerce scanner ───────────────────────────────────────────────

async def _scan_woocommerce(client: httpx.AsyncClient, base_url: str) -> list[ScannedProduct]:
    """Fetch products from WooCommerce's public Store API."""
    url = f"{base_url}/wp-json/wc/store/products?per_page={MAX_PRODUCTS}"
    r = await client.get(url, follow_redirects=True)
    r.raise_for_status()
    data = r.json()

    products: list[ScannedProduct] = []
    for p in data:
        # WooCommerce Store API returns prices in cents as strings
        price_str = p.get("prices", {}).get("price", "0")
        try:
            price = float(price_str) / 100  # cents to dollars
        except (ValueError, TypeError):
            continue

        if price <= 0:
            continue

        regular_str = p.get("prices", {}).get("regular_price", "0")
        compare_at = None
        try:
            regular = float(regular_str) / 100
            if regular > price:
                compare_at = regular
        except (ValueError, TypeError):
            pass

        image_url = ""
        images = p.get("images", [])
        if images:
            image_url = images[0].get("src", "")

        permalink = p.get("permalink", "")

        products.append(
            ScannedProduct(
                title=p.get("name", "Untitled"),
                price=price,
                compare_at_price=compare_at,
                product_type=", ".join(
                    c.get("name", "") for c in p.get("categories", [])
                ),
                vendor="",
                image_url=image_url,
                url=permalink,
            )
        )

    return products


# ── Public API ────────────────────────────────────────────────────────

async def scan_store(raw_url: str) -> ScanResult:
    """
    Scan a public storefront and return up to MAX_PRODUCTS products.

    Works with both Shopify and WooCommerce stores.
    No authentication required — uses publicly accessible JSON endpoints.
    """
    base_url = _normalise_url(raw_url)
    store_name = _extract_store_name(base_url)

    result = ScanResult(
        store_name=store_name,
        store_url=base_url,
    )

    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            # Detect platform
            platform = await _detect_platform(client, base_url)
            result.platform = platform

            if platform == "shopify":
                result.products = await _scan_shopify(client, base_url)
            elif platform == "woocommerce":
                result.products = await _scan_woocommerce(client, base_url)
            else:
                result.error = (
                    "Could not detect a Shopify or WooCommerce store at this URL. "
                    "Make sure the store is public and not password-protected."
                )
                return result

            if not result.products:
                result.error = (
                    f"Found a {platform} store but no products. "
                    "The catalog may be empty or the store may be password-protected."
                )

            logger.info(
                "Scanned %s (%s): %d products found",
                store_name,
                platform,
                len(result.products),
            )

    except httpx.TimeoutException:
        result.error = "Store took too long to respond. Please try again."
        logger.warning("Timeout scanning %s", base_url)
    except httpx.HTTPStatusError as e:
        result.error = f"Store returned an error (HTTP {e.response.status_code})."
        logger.warning("HTTP error scanning %s: %s", base_url, e)
    except Exception as e:
        result.error = f"Could not scan the store: {str(e)}"
        logger.exception("Unexpected error scanning %s", base_url)

    return result



