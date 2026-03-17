# backend/models/integration.py

"""
E-commerce Integration Model
Stores encrypted credentials for Shopify/WooCommerce connections

Aligned with architecture doc: Section 6.1 Shopify Integration

PATCHED (2026-02-21):
- Added UniqueConstraint on ProductIntegrationLink for variant-level dedup
- Added index on external_variant_id for query performance
- Updated docstrings for variant-aware linking
"""

import uuid as uuid_lib
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Column as SAColumn,
)
from sqlalchemy import (
    DateTime,
    ForeignKey,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.product import Product
    from models.user import User


class EcommercePlatform(str, Enum):
    """Supported e-commerce platforms"""

    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class IntegrationStatus(str, Enum):
    """Connection status states - matches architecture doc"""

    ACTIVE = "active"  # Successfully authenticated and working
    ERROR = "error"  # Auth failed or token expired
    PAUSED = "paused"  # User paused the integration
    DISCONNECTED = "disconnected"  # User disconnected


class Integration(SQLModel, table=True):
    """
    Stores e-commerce platform connections and encrypted credentials.
    Each user can have one integration per platform.

    Note: Using user_id now, will migrate to organization_id when
    Organization model is added for full multi-tenancy.
    """

    __tablename__ = "integrations"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4, sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True)
    )

    # Foreign key to user (will become organization_id later)
    user_id: uuid_lib.UUID | None = Field(
        default=None, sa_column=SAColumn(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    )

    # Platform identification
    platform: EcommercePlatform = Field(index=True)
    store_url: str = Field(max_length=255)  # e.g., "mystore.myshopify.com"
    store_name: str | None = Field(default=None, max_length=255)

    # Status tracking
    status: IntegrationStatus = Field(default=IntegrationStatus.ACTIVE, index=True)
    error_message: str | None = Field(default=None, sa_column=SAColumn(Text))

    # ========== Encrypted Credentials (Architecture Doc Aligned) ==========
    # Stored as BYTEA for proper binary encryption
    access_token_encrypted: bytes = Field(sa_column=SAColumn(LargeBinary, nullable=False))
    refresh_token_encrypted: bytes | None = Field(default=None, sa_column=SAColumn(LargeBinary, nullable=True))
    token_expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    # OAuth scopes granted
    scopes: list[str] = Field(default=[], sa_column=Column(JSON))

    # Webhook secret (encrypted)
    webhook_secret_encrypted: bytes | None = Field(default=None, sa_column=SAColumn(LargeBinary, nullable=True))
    # Webhook IDs for cleanup on disconnect
    webhook_ids: list[str] = Field(default=[], sa_column=Column(JSON))

    # ========== OAuth Flow (temporary fields) ==========
    oauth_state: str | None = Field(default=None, max_length=64)

    # ========== Sync Metadata ==========
    last_sync_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    sync_status: str = Field(default="idle", max_length=20)  # idle, syncing, error
    products_synced: int = Field(default=0)
    sync_cursor: str | None = Field(default=None, max_length=500)

    # ========== Flexible Settings (Architecture Doc) ==========
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # ========== Timestamps ==========
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )

    # ========== Relationships ==========
    user: Optional["User"] = Relationship(back_populates="integrations")
    sync_logs: list["IntegrationSyncLog"] = Relationship(back_populates="integration")
    product_links: list["ProductIntegrationLink"] = Relationship(back_populates="integration")


class IntegrationSyncLog(SQLModel, table=True):
    """
    Tracks sync operations for debugging and monitoring.
    Useful for troubleshooting failed syncs and auditing.
    """

    __tablename__ = "integration_sync_logs"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4, sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True)
    )

    integration_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False, index=True)
    )

    # Sync details
    sync_type: str = Field(max_length=50)  # "full", "incremental", "webhook"
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True, default=lambda: datetime.now(UTC))
    )
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_seconds: float | None = Field(default=None)

    # Results
    success: bool = Field(default=False)
    products_created: int = Field(default=0)
    products_updated: int = Field(default=0)
    products_deleted: int = Field(default=0)
    error_details: str | None = Field(default=None, sa_column=SAColumn(Text))

    # Relationship
    integration: Optional["Integration"] = Relationship(back_populates="sync_logs")


class ProductIntegrationLink(SQLModel, table=True):
    """
    Links our Product records to external platform product/variant IDs.
    Enables two-way sync between SSP and Shopify/WooCommerce.

    One SSP Product can have multiple links (one per variant per platform).
    Upsert key: (integration_id, external_product_id, external_variant_id)

    Example for a Shopify product with 3 color variants:
        Product "T-Shirt" → 3 links (Red, Blue, Green), each with
        the same external_product_id but different external_variant_id.
    """

    __tablename__ = "product_integration_links"

    # FIX: Enforce one link per integration + product + variant at the DB level.
    # This prevents duplicate links from race conditions or retry logic.
    # The actual index is created by Alembic migration (fix8), but declaring
    # it here ensures create_all() in tests also enforces it.
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_product_id",
            "external_variant_id",
            name="uq_link_integration_product_variant",
        ),
    )

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4, sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True)
    )

    # Links
    product_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(PG_UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    )
    integration_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False, index=True)
    )

    # External platform identifiers
    external_product_id: str = Field(max_length=100, index=True)
    # FIX: Added index for query performance — every upsert lookup filters on this.
    # Stays nullable until migration backfills existing NULLs (fix8).
    external_variant_id: str | None = Field(default=None, max_length=100, index=True)

    # Sync state
    external_price: float | None = Field(default=None)
    external_compare_at_price: float | None = Field(default=None)
    last_price_push_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_price_pull_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    sync_enabled: bool = Field(default=True)

    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )

    # Relationships
    integration: Optional["Integration"] = Relationship(back_populates="product_links")
    product: Optional["Product"] = Relationship(back_populates="integration_links")
