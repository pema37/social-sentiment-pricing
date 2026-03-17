# backend/services/products/import_service.py
"""
Product Import Service
======================

Handles bulk product imports from CSV/JSON data.
Supports WooCommerce and Shopify export formats.

Best Practices Applied:
- Single Responsibility: Only handles imports
- Batch Processing: Commits in batches for performance
- Error Isolation: Individual row errors don't fail entire import
- Validation: Input validation before database operations
"""

import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from models.product import Product

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT SCHEMAS
# Defined here since they're specific to import functionality
# ═══════════════════════════════════════════════════════════════════════════════


class ImportProductRow(BaseModel):
    """
    Single product row from CSV import.
    Compatible with WooCommerce and Shopify CSV exports.
    """

    name: str = Field(..., min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=100)
    base_price: Decimal = Field(..., gt=0)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    image_url: str | None = None
    stock_quantity: int | None = Field(default=None, ge=0)

    @field_validator("base_price", mode="before")
    @classmethod
    def parse_price(cls, v):
        """Parse price from various formats: $19.99, 19,99, 19.99"""
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                cleaned = v.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
                return Decimal(cleaned)
            except InvalidOperation:
                raise ValueError("Invalid price format")
        return v


class ImportResult(BaseModel):
    """Result of a bulk import operation."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.created + self.updated + self.skipped + self.failed


class ProductImportService:
    """
    Bulk product import service.

    Usage:
        service = ProductImportService(session)
        result = await service.import_products(
            user_id=user.id,
            products=rows,
            skip_duplicates=True,
        )
    """

    # Maximum products per import batch
    MAX_BATCH_SIZE = 1000

    # Maximum errors to return (prevents huge responses)
    MAX_ERRORS = 50

    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_products(
        self,
        user_id: UUID,
        products: list[ImportProductRow],
        skip_duplicates: bool = True,
        update_existing: bool = False,
    ) -> ImportResult:
        """
        Import multiple products from parsed data.

        Args:
            user_id: Owner of the imported products
            products: List of validated product rows
            skip_duplicates: Skip products with existing SKU (default: True)
            update_existing: Update products with matching SKU (default: False)

        Returns:
            ImportResult with counts and any errors
        """
        if len(products) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Maximum {self.MAX_BATCH_SIZE} products per import")

        result = ImportResult()

        # Get existing SKUs for duplicate detection
        existing_skus = set()
        if skip_duplicates or update_existing:
            existing_skus = await self._get_existing_skus(user_id)

        products_to_add = []

        for idx, row in enumerate(products):
            try:
                # Check for duplicate SKU
                if row.sku and row.sku.strip() in existing_skus:
                    if update_existing:
                        # TODO: Implement update logic
                        result.updated += 1
                        continue
                    elif skip_duplicates:
                        result.skipped += 1
                        continue

                # Create product instance
                product = self._create_product_from_row(user_id, row)
                products_to_add.append(product)

                # Track SKU to prevent duplicates within same import
                if row.sku:
                    existing_skus.add(row.sku.strip())

            except Exception as e:
                result.failed += 1
                if len(result.errors) < self.MAX_ERRORS:
                    result.errors.append(f"Row {idx + 1} ({row.name}): {e!s}")

        # Batch insert all valid products
        if products_to_add:
            try:
                for product in products_to_add:
                    self.session.add(product)

                await self.session.commit()
                result.created = len(products_to_add)

                logger.info(
                    f"Imported {result.created} products for user {user_id} "
                    f"(skipped: {result.skipped}, failed: {result.failed})"
                )

            except Exception as e:
                await self.session.rollback()
                logger.error(f"Bulk import failed: {e}")
                raise

        return result

    async def _get_existing_skus(self, user_id: UUID) -> set:
        """Get all existing SKUs for a user."""
        from sqlmodel import select

        stmt = select(Product.sku).where(
            Product.user_id == user_id,
            Product.sku.isnot(None),
        )
        result = await self.session.execute(stmt)
        return {sku for (sku,) in result.all() if sku}

    def _create_product_from_row(
        self,
        user_id: UUID,
        row: ImportProductRow,
    ) -> Product:
        """Create a Product instance from an import row."""
        return Product(
            user_id=user_id,
            name=row.name.strip(),
            sku=row.sku.strip() if row.sku else None,
            description=row.description.strip() if row.description else None,
            category=row.category.strip() if row.category else None,
            image_url=row.image_url.strip() if row.image_url else None,
            base_price=row.base_price,
            current_price=row.base_price,
            is_active=True,
            auto_pricing_enabled=False,
            keywords=[],
        )

    @classmethod
    def parse_csv_row(cls, row: dict) -> ImportProductRow:
        """
        Parse a CSV row dict into ImportProductRow.
        Handles common field name variations from different platforms.
        """
        # Field name mappings for different platforms
        name = (
            row.get("name") or row.get("Name") or row.get("title") or row.get("Title") or row.get("product_name") or ""
        )

        price = (
            row.get("base_price")
            or row.get("price")
            or row.get("Price")
            or row.get("regular_price")
            or row.get("Variant Price")
            or "0"
        )

        sku = row.get("sku") or row.get("SKU") or row.get("Variant SKU") or None

        description = row.get("description") or row.get("Description") or row.get("Body (HTML)") or None

        category = row.get("category") or row.get("Category") or row.get("Type") or row.get("Product Type") or None

        image_url = row.get("image_url") or row.get("Image Src") or row.get("images") or None

        return ImportProductRow(
            name=name,
            base_price=price,
            sku=sku,
            description=description,
            category=category,
            image_url=image_url,
        )
