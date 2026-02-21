"""
Shopify Orders Mixin - Orders API for outcome measurement.

Methods:
  - fetch_product_sales_data: Revenue + units for a product over a date range

Uses from ShopifyService (via self):
  - _graphql(), _get_shop_domain(), _gid(), _auth_headers()
  - retry_config

Requires: read_orders scope in REQUIRED_SCOPES.
Existing merchants need one-time re-authorization after scope addition.

Place at: backend/services/integration/shopify_orders.py
"""

import logging
from decimal import Decimal
from typing import Optional

from .http_client import RetryableClient

logger = logging.getLogger(__name__)


class ShopifyOrdersMixin:
    """Orders API access for ShopifyService."""

    async def fetch_product_sales_data(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str,
        created_at_min: str,
        created_at_max: str,
    ) -> Optional[dict]:
        """
        Fetch revenue and units sold for a specific product over a date range.

        Uses Shopify GraphQL Orders API to query orders in the window,
        then filters line items for the target product.

        Args:
            store_url: Shopify store URL
            access_token: Decrypted access token
            external_product_id: Numeric Shopify product ID
            created_at_min: ISO datetime string (inclusive)
            created_at_max: ISO datetime string (inclusive)

        Returns:
            {"revenue": Decimal, "units": int} or None if API call fails.

        Requires: read_orders scope.
        """
        shop_domain = self._get_shop_domain(store_url)
        product_gid = self._gid("Product", external_product_id)

        # Shopify's orders query filter syntax
        # https://shopify.dev/docs/api/admin-graphql/2024-01/queries/orders
        query_filter = (
            f"created_at:>='{created_at_min}' "
            f"AND created_at:<='{created_at_max}'"
        )

        query = """
            query FetchOrdersForProduct($query: String!, $cursor: String) {
                orders(first: 50, query: $query, after: $cursor) {
                    edges {
                        node {
                            id
                            lineItems(first: 100) {
                                edges {
                                    node {
                                        product {
                                            id
                                        }
                                        quantity
                                        originalTotalSet {
                                            shopMoney {
                                                amount
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        cursor
                    }
                    pageInfo {
                        hasNextPage
                    }
                }
            }
        """

        total_revenue = Decimal("0")
        total_units = 0
        cursor = None

        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 30.0) as rc:
                # Paginate through all orders in the date range
                for _ in range(20):  # Safety cap: max 20 pages (1000 orders)
                    variables: dict = {"query": query_filter}
                    if cursor:
                        variables["cursor"] = cursor

                    data = await self._graphql(
                        rc, shop_domain, access_token, query, variables
                    )

                    edges = data.get("orders", {}).get("edges", [])
                    page_info = data.get("orders", {}).get("pageInfo", {})

                    for order_edge in edges:
                        order_node = order_edge.get("node", {})
                        line_items = (
                            order_node.get("lineItems", {}).get("edges", [])
                        )

                        for li_edge in line_items:
                            li_node = li_edge.get("node", {})
                            li_product = li_node.get("product")
                            if not li_product:
                                continue

                            # Match product by GID
                            if li_product.get("id") == product_gid:
                                quantity = li_node.get("quantity", 0)
                                amount_str = (
                                    li_node
                                    .get("originalTotalSet", {})
                                    .get("shopMoney", {})
                                    .get("amount", "0")
                                )
                                total_units += quantity
                                total_revenue += Decimal(str(amount_str))

                    # Pagination
                    if page_info.get("hasNextPage") and edges:
                        cursor = edges[-1].get("cursor")
                    else:
                        break

            return {
                "revenue": total_revenue,
                "units": total_units,
            }

        except Exception as e:
            logger.error(
                f"Failed to fetch sales data for product {external_product_id} "
                f"from {store_url}: {e}"
            )
            return None
        

        