# backend/services/competitor_matching/utils.py

"""
Utility functions for competitor matching.

Pure functions with no side effects - easy to test and reuse.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict
from urllib.parse import urlparse


# ─────────────────────────────────────────────────────────────────────────────
# Known Merchants Registry
# ─────────────────────────────────────────────────────────────────────────────

KNOWN_MERCHANTS: Dict[str, Dict] = {
    # Major US Retailers
    "amazon.com": {"name": "Amazon", "reliability": 0.95, "is_marketplace": True},
    "amazon.ca": {"name": "Amazon Canada", "reliability": 0.95, "is_marketplace": True},
    "amazon.co.uk": {"name": "Amazon UK", "reliability": 0.95, "is_marketplace": True},
    "ebay.com": {"name": "eBay", "reliability": 0.85, "is_marketplace": True},
    "walmart.com": {"name": "Walmart", "reliability": 0.95, "is_marketplace": False},
    "target.com": {"name": "Target", "reliability": 0.95, "is_marketplace": False},
    "bestbuy.com": {"name": "Best Buy", "reliability": 0.95, "is_marketplace": False},
    "costco.com": {"name": "Costco", "reliability": 0.95, "is_marketplace": False},
    
    # Electronics
    "newegg.com": {"name": "Newegg", "reliability": 0.90, "is_marketplace": True},
    "bhphotovideo.com": {"name": "B&H Photo", "reliability": 0.95, "is_marketplace": False},
    "adorama.com": {"name": "Adorama", "reliability": 0.90, "is_marketplace": False},
    "microcenter.com": {"name": "Micro Center", "reliability": 0.90, "is_marketplace": False},
    
    # Home & Garden
    "homedepot.com": {"name": "Home Depot", "reliability": 0.95, "is_marketplace": False},
    "lowes.com": {"name": "Lowe's", "reliability": 0.95, "is_marketplace": False},
    "wayfair.com": {"name": "Wayfair", "reliability": 0.90, "is_marketplace": True},
    "overstock.com": {"name": "Overstock", "reliability": 0.85, "is_marketplace": True},
    
    # Fashion
    "zappos.com": {"name": "Zappos", "reliability": 0.95, "is_marketplace": False},
    "nordstrom.com": {"name": "Nordstrom", "reliability": 0.95, "is_marketplace": False},
    "macys.com": {"name": "Macy's", "reliability": 0.90, "is_marketplace": False},
    "kohls.com": {"name": "Kohl's", "reliability": 0.90, "is_marketplace": False},
    "jcpenney.com": {"name": "JCPenney", "reliability": 0.85, "is_marketplace": False},
    
    # Beauty
    "sephora.com": {"name": "Sephora", "reliability": 0.95, "is_marketplace": False},
    "ulta.com": {"name": "Ulta", "reliability": 0.95, "is_marketplace": False},
    
    # Pets
    "chewy.com": {"name": "Chewy", "reliability": 0.95, "is_marketplace": False},
    "petco.com": {"name": "Petco", "reliability": 0.90, "is_marketplace": False},
    "petsmart.com": {"name": "PetSmart", "reliability": 0.90, "is_marketplace": False},
    
    # Office
    "staples.com": {"name": "Staples", "reliability": 0.90, "is_marketplace": False},
    "officedepot.com": {"name": "Office Depot", "reliability": 0.90, "is_marketplace": False},
    
    # International / Discount
    "aliexpress.com": {"name": "AliExpress", "reliability": 0.70, "is_marketplace": True},
    "wish.com": {"name": "Wish", "reliability": 0.60, "is_marketplace": True},
    "etsy.com": {"name": "Etsy", "reliability": 0.80, "is_marketplace": True},
    "temu.com": {"name": "Temu", "reliability": 0.65, "is_marketplace": True},
}

# Domains to skip (not product pages)
SKIP_DOMAINS = frozenset({
    "google.com", "google.ca", "google.co.uk",
    "bing.com", "yahoo.com", "duckduckgo.com",
    "youtube.com", "vimeo.com",
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "pinterest.com", "reddit.com", "tiktok.com",
    "wikipedia.org", "wikimedia.org",
    "linkedin.com", "medium.com",
})


# ─────────────────────────────────────────────────────────────────────────────
# Domain Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_domain(url: str) -> str:
    """
    Extract clean domain from URL.
    
    Args:
        url: Full URL string
        
    Returns:
        Clean domain (e.g., "amazon.com")
        
    Examples:
        >>> extract_domain("https://www.amazon.com/dp/B09V3KXJPB")
        "amazon.com"
        >>> extract_domain("http://shop.walmart.com/product/123")
        "shop.walmart.com"
    """
    if not url:
        return ""
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        
        return domain
    except Exception:
        return ""


def get_merchant_name(domain: str) -> str:
    """
    Get display name for a merchant domain.
    
    Args:
        domain: Clean domain string
        
    Returns:
        Merchant name or capitalized domain
    """
    if not domain:
        return "Unknown"
    
    merchant_info = KNOWN_MERCHANTS.get(domain)
    if merchant_info:
        return merchant_info["name"]
    
    # Try to make a nice name from domain
    name = domain.split(".")[0]
    return name.replace("-", " ").replace("_", " ").title()


def get_merchant_reliability(domain: str) -> float:
    """
    Get reliability score for a merchant.
    
    Args:
        domain: Clean domain string
        
    Returns:
        Reliability score 0-1 (default 0.5 for unknown)
    """
    if not domain:
        return 0.3
    
    merchant_info = KNOWN_MERCHANTS.get(domain)
    if merchant_info:
        return merchant_info.get("reliability", 0.8)
    
    return 0.5  # Unknown merchant


def is_marketplace(domain: str) -> bool:
    """Check if domain is a marketplace (multiple sellers)."""
    merchant_info = KNOWN_MERCHANTS.get(domain)
    if merchant_info:
        return merchant_info.get("is_marketplace", False)
    return False


def is_skip_domain(domain: str) -> bool:
    """Check if domain should be skipped."""
    return domain in SKIP_DOMAINS


# ─────────────────────────────────────────────────────────────────────────────
# Price Parsing
# ─────────────────────────────────────────────────────────────────────────────

# Price regex patterns (ordered by specificity)
PRICE_PATTERNS = [
    # $1,234.56 or $ 1,234.56
    (r'\$\s*([\d,]+\.?\d*)', "USD"),
    # 1,234.56 USD or 1234.56 dollars
    (r'([\d,]+\.?\d*)\s*(?:USD|dollars?)', "USD"),
    # USD 1,234.56
    (r'USD\s*([\d,]+\.?\d*)', "USD"),
    # €1.234,56 (European format)
    (r'€\s*([\d.]+,?\d*)', "EUR"),
    # £1,234.56
    (r'£\s*([\d,]+\.?\d*)', "GBP"),
    # CAD $1,234.56
    (r'CAD\s*\$?\s*([\d,]+\.?\d*)', "CAD"),
    # Price: 1234.56
    (r'[Pp]rice:?\s*\$?\s*([\d,]+\.?\d*)', "USD"),
    # Generic number (fallback)
    (r'([\d,]+\.\d{2})\b', "USD"),
]


def parse_price(value) -> Optional[Decimal]:
    """
    Parse price from various input types.
    
    Args:
        value: Price value (string, int, float, or None)
        
    Returns:
        Decimal price or None if parsing fails
        
    Examples:
        >>> parse_price("$1,234.56")
        Decimal('1234.56')
        >>> parse_price(99.99)
        Decimal('99.99')
        >>> parse_price("invalid")
        None
    """
    if value is None:
        return None
    
    # Handle numeric types
    if isinstance(value, (int, float)):
        try:
            price = Decimal(str(value))
            if _is_valid_price(price):
                return price
        except InvalidOperation:
            pass
        return None
    
    # Handle string
    if isinstance(value, str):
        return extract_price_from_text(value)
    
    # Handle Decimal
    if isinstance(value, Decimal):
        return value if _is_valid_price(value) else None
    
    return None


def extract_price_from_text(text: str) -> Optional[Decimal]:
    """
    Extract price from text string.
    
    Args:
        text: Text that may contain a price
        
    Returns:
        First valid price found or None
    """
    if not text:
        return None
    
    text = text.strip()
    
    for pattern, currency in PRICE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            price_str = match.group(1)
            
            # Handle European format (1.234,56)
            if currency == "EUR" and "," in price_str:
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                # Standard format - remove thousands separator
                price_str = price_str.replace(",", "")
            
            try:
                price = Decimal(price_str)
                if _is_valid_price(price):
                    return price
            except InvalidOperation:
                continue
    
    return None


def _is_valid_price(price: Decimal) -> bool:
    """
    Check if price is in valid range.
    
    Filters out obvious errors like $0.00 or $999,999.99
    """
    return Decimal("0.01") <= price <= Decimal("100000")


# ─────────────────────────────────────────────────────────────────────────────
# Text Similarity
# ─────────────────────────────────────────────────────────────────────────────

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate simple word-overlap similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score 0-1
    """
    if not text1 or not text2:
        return 0.0
    
    # Tokenize and normalize
    words1 = set(_tokenize(text1))
    words2 = set(_tokenize(text2))
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0


def calculate_keyword_match(text: str, keywords: List[str]) -> float:
    """
    Calculate how many keywords appear in text.
    
    Args:
        text: Text to search in
        keywords: Keywords to look for
        
    Returns:
        Match ratio 0-1
    """
    if not text or not keywords:
        return 0.0
    
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    
    return matches / len(keywords)


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words."""
    # Remove special characters, split, lowercase
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    
    # Filter out very short words and common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
    
    return [w for w in words if len(w) > 1 and w not in stop_words]


# ─────────────────────────────────────────────────────────────────────────────
# Query Building
# ─────────────────────────────────────────────────────────────────────────────

def build_shopping_query(
    product_name: str,
    keywords: Optional[List[str]] = None,
    include_buy: bool = False,
) -> str:
    """
    Build optimized search query for shopping search.
    
    Args:
        product_name: Product name
        keywords: Additional keywords
        include_buy: Add "buy" keyword for broader results
        
    Returns:
        Optimized query string
    """
    # Start with product name
    query_parts = [product_name.strip()]
    
    # Add keywords not already in product name
    if keywords:
        name_lower = product_name.lower()
        new_keywords = [k for k in keywords if k.lower() not in name_lower]
        query_parts.extend(new_keywords[:3])  # Max 3 extra keywords
    
    # Optionally add "buy" for shopping intent
    if include_buy:
        query_parts.append("buy")
    
    return " ".join(query_parts)


def clean_product_title(title: str) -> str:
    """
    Clean up a product title from search results.
    
    Removes common noise like "FREE SHIPPING", "SALE", etc.
    """
    if not title:
        return ""
    
    # Patterns to remove
    noise_patterns = [
        r'\bFREE\s+SHIPPING\b',
        r'\bSALE\b',
        r'\bNEW\b',
        r'\bHOT\b',
        r'\b\d+%\s*OFF\b',
        r'\|.*$',  # Everything after |
        r'-\s*$',  # Trailing dash
    ]
    
    cleaned = title
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned



