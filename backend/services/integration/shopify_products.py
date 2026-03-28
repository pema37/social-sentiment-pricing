"""
Shopify Products Mixin - Product fetching and parsing.

All product data fetched via Shopify GraphQL Admin API 2025-10 —
REST /products.json is NOT used here.

Methods:
  - fetch_products: Paginated product listing (cursor-based)
  - fetch_single_product: Single product by numeric ID
  - _parse_graphql_product: Parse GraphQL node → ExternalProduct

Uses from ShopifyService (via self):
  - _graphql(), _graphql_url(), _get_shop_domain(), _auth_headers()
  - _gid(), _numeric_id(), _parse_datetime()
  - retry_config

Place at: backend/services/integration/shopify_products.py
"""

import logging

import httpx

from .circuit_breaker import CircuitOpenError
from .http_client import RetryableClient
from .schemas import (
    ExternalProduct,
    ExternalProductVariant,
    ProductSyncResult,
)

logger = logging.getLogger(__name__)


class ShopifyProductsMixin:
    """Product fetching and parsing for ShopifyService."""

    _PRODUCT_FIELDS = """
        fragment ProductFields on Product {
            id
            title
            bodyHtml
            vendor
            productType
            tags
            status
            createdAt
            updatedAt
            images(first: 10) {
                edges { node { url } }
            }
            variants(first: 100) {
                edges {
                    node {
                        id
                        title
                        price
                        sku
                        compareAtPrice
                        inventoryQuantity
                    }
                }
            }
        }
    """

    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ProductSyncResult:
        """Fetch products with cursor-based pagination."""
        shop_domain = self._get_shop_domain(store_url)
        safe_limit = min(limit, 250)

        after_clause = f', after: "{cursor}"' if cursor else ""
        query = f"""
            {self._PRODUCT_FIELDS}
            query FetchProducts {{
                products(first: {safe_limit}{after_clause}) {{
                    edges {{
                        node {{ ...ProductFields }}
                        cursor
                    }}
                    pageInfo {{ hasNextPage }}
                }}
            }}
        """
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 30.0) as rc:
                data = await self._graphql(rc, shop_domain, access_token, query)

            edges = data.get("products", {}).get("edges", [])
            page_info = data.get("products", {}).get("pageInfo", {})
            products = [self._parse_graphql_product(e["node"]) for e in edges]
            next_cursor = edges[-1]["cursor"] if edges and page_info.get("hasNextPage") else None

            return ProductSyncResult(
                success=True,
                products=products,
                has_more=page_info.get("hasNextPage", False),
                next_cursor=next_cursor,
            )
        except CircuitOpenError:
            return ProductSyncResult(success=False, error="Service temporarily unavailable")
        except httpx.HTTPStatusError as e:
            error_map = {401: "Unauthorized", 429: "Rate limited"}
            return ProductSyncResult(
                success=False,
                error=error_map.get(e.response.status_code, f"HTTP {e.response.status_code}"),
            )
        except (httpx.RequestError, ValueError) as e:
            return ProductSyncResult(success=False, error=str(e))

    async def fetch_single_product(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str,
    ) -> ExternalProduct | None:
        """Fetch one product by numeric ID."""
        shop_domain = self._get_shop_domain(store_url)
        gid = self._gid("Product", external_product_id)

        query = f"""
            {self._PRODUCT_FIELDS}
            query FetchProduct($id: ID!) {{
                product(id: $id) {{ ...ProductFields }}
            }}
        """
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
                data = await self._graphql(rc, shop_domain, access_token, query, {"id": gid})
            node = data.get("product")
            return self._parse_graphql_product(node) if node else None
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
            return None

    def _parse_graphql_product(self, node: dict) -> ExternalProduct:
        """
        Parse a GraphQL product node into ExternalProduct.

        GraphQL returns:
          - IDs as GIDs (gid://shopify/Product/123) → we extract numeric
          - variants/images as edges[] → we flatten
          - tags as list of strings → direct use
          - prices as strings → we convert to float
        """
        # Parse variants
        variant_edges = node.get("variants", {}).get("edges", [])
        variants = [
            ExternalProductVariant(
                id=self._numeric_id(v["node"]["id"]),
                title=v["node"].get("title", ""),
                price=float(v["node"]["price"]) if v["node"].get("price") else 0,
                sku=v["node"].get("sku"),
                inventory_quantity=v["node"].get("inventoryQuantity"),
                compare_at_price=(float(v["node"]["compareAtPrice"]) if v["node"].get("compareAtPrice") else None),
            )
            for v in variant_edges
        ]

        # Parse images
        image_edges = node.get("images", {}).get("edges", [])
        images = [e["node"]["url"] for e in image_edges if e.get("node", {}).get("url")]

        # Tags: GraphQL returns a list, REST returned comma-separated string
        tags = node.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        return ExternalProduct(
            id=self._numeric_id(node.get("id", "")),
            title=node.get("title", ""),
            price=variants[0].price if variants else None,
            compare_at_price=variants[0].compare_at_price if variants else None,
            sku=variants[0].sku if variants else None,
            description=node.get("bodyHtml", ""),
            inventory_quantity=variants[0].inventory_quantity if variants else None,
            product_type=node.get("productType", ""),
            vendor=node.get("vendor", ""),
            tags=tags,
            images=images,
            variants=variants,
            created_at=self._parse_datetime(node.get("createdAt")),
            updated_at=self._parse_datetime(node.get("updatedAt")),
        )
