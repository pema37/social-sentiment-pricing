# backend/models/integration.py

"""
E-commerce Integration Model
Stores encrypted credentials for Shopify/WooCommerce connections

Aligned with architecture doc: Section 6.1 Shopify Integration

PATCHED (2026-02-21):
- Added UniqueConstraint on ProductIntegrationLink for variant-level dedup
- Added index on external_variant_id for query performance
- Updated docstrings for variant-aware linking

PATCHED (2026-03-29):
- Added @property access_token guard on Integration model.
  The model stores credentials as access_token_encrypted (LargeBinary).
  Any code referencing integration.access_token directly raises AttributeError
  at runtime — the property guard makes this fail loudly with a helpful message
  instead of silently (e.g. via getattr with a None default).
  Correct usage: decrypt_token(integration.access_token_encrypted)
"""

import uuid as uuid_lib
from datetime import UTC, datetime
from enum import StrEnum
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


class EcommercePlatform(StrEnum):
    """Supported e-commerce platforms"""

    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class IntegrationStatus(StrEnum):
    """Connection status states - matches architecture doc"""

    ACTIVE = "active"       # Successfully authenticated and working
    ERROR = "error"         # Auth failed or token expired
    PAUSED = "paused"       # User paused the integration
    DISCONNECTED = "disconnected"  # User disconnected


class Integration(SQLModel, table=True):
    """
    Stores e-commerce platform connections and encrypted credentials.
    Each user can have one integration per platform.

    Note: Using user_id now, will migrate to organization_id when
    Organization model is added for full multi-tenancy.

    CREDENTIAL PATTERN:
      Store:  integration.access_token_encrypted = encrypt_token(plaintext)
      Fetch:  decrypt_token(integration.access_token_encrypted)
      Never:  integration.access_token  ← raises AttributeError by design
    """

    __tablename__ = "integrations"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True),
    )

    # Foreign key to user (will become organization_id later)
    user_id: uuid_lib.UUID | None = Field(
        default=None,
        sa_column=SAColumn(
            PG_UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )

    # Platform identification
    platform: EcommercePlatform = Field(index=True)
    store_url: str = Field(max_length=255)
    store_name: str | None = Field(default=None, max_length=255)

    # Status tracking
    status: IntegrationStatus = Field(default=IntegrationStatus.ACTIVE, index=True)
    error_message: str | None = Field(default=None, sa_column=SAColumn(Text))

    # ========== Encrypted Credentials ==========
    # Stored as BYTEA for proper binary encryption.
    # Access via decrypt_token(integration.access_token_encrypted).
    # The @property access_token below raises AttributeError on direct access.
    access_token_encrypted: bytes = Field(
        sa_column=SAColumn(LargeBinary, nullable=False)
    )
    refresh_token_encrypted: bytes | None = Field(
        default=None,
        sa_column=SAColumn(LargeBinary, nullable=True),
    )
    token_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # OAuth scopes granted
    scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Webhook secret (encrypted)
    webhook_secret_encrypted: bytes | None = Field(
        default=None,
        sa_column=SAColumn(LargeBinary, nullable=True),
    )
    webhook_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # ========== OAuth Flow ==========
    oauth_state: str | None = Field(default=None, max_length=64)

    # ========== Sync Metadata ==========
    last_sync_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    sync_status: str = Field(default="idle", max_length=20)  # idle, syncing, error
    products_synced: int = Field(default=0)
    sync_cursor: str | None = Field(default=None, max_length=500)

    # ========== Flexible Settings ==========
    settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # ========== Timestamps ==========
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
        ),
    )

    # ========== Relationships ==========
    user: Optional["User"] = Relationship(back_populates="integrations")
    sync_logs: list["IntegrationSyncLog"] = Relationship(back_populates="integration")
    product_links: list["ProductIntegrationLink"] = Relationship(back_populates="integration")

    # ========== Property Guard ==========
    # Raises AttributeError with a helpful message when any code accidentally
    # references integration.access_token instead of decrypting explicitly.
    # Works cleanly with SQLAlchemy — access_token is not a mapped column so
    # there is no InstrumentedAttribute conflict. The @property descriptor takes
    # precedence over instance __dict__ lookups.
    @property
    def access_token(self) -> None:  # type: ignore[override]
        raise AttributeError(
            "Do not access integration.access_token directly. "
            "Use: decrypt_token(integration.access_token_encrypted)"
        )

    @access_token.setter
    def access_token(self, value: object) -> None:  # type: ignore[override]
        raise AttributeError(
            "Do not set integration.access_token directly. "
            "Use: integration.access_token_encrypted = encrypt_token(plaintext)"
        )


class IntegrationSyncLog(SQLModel, table=True):
    """
    Tracks sync operations for debugging and monitoring.
    """

    __tablename__ = "integration_sync_logs"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True),
    )

    integration_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(
            PG_UUID(as_uuid=True),
            ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    sync_type: str = Field(max_length=50)  # "full", "incremental", "webhook"
    started_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            index=True,
            default=lambda: datetime.now(UTC),
        ),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    duration_seconds: float | None = Field(default=None)

    success: bool = Field(default=False)
    products_created: int = Field(default=0)
    products_updated: int = Field(default=0)
    products_deleted: int = Field(default=0)
    error_details: str | None = Field(default=None, sa_column=SAColumn(Text))

    integration: Optional["Integration"] = Relationship(back_populates="sync_logs")


class ProductIntegrationLink(SQLModel, table=True):
    """
    Links SSP Product records to external platform product/variant IDs.
    Enables two-way sync between SSP and Shopify/WooCommerce.

    One SSP Product can have multiple links (one per variant per platform).
    Upsert key: (integration_id, external_product_id, external_variant_id)
    """

    __tablename__ = "product_integration_links"

    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_product_id",
            "external_variant_id",
            name="uq_link_integration_product_variant",
        ),
    )

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True),
    )

    product_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(
            PG_UUID(as_uuid=True),
            ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    integration_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(
            PG_UUID(as_uuid=True),
            ForeignKey("integrations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )

    external_product_id: str = Field(max_length=100, index=True)
    external_variant_id: str | None = Field(default=None, max_length=100, index=True)

    external_price: float | None = Field(default=None)
    external_compare_at_price: float | None = Field(default=None)
    last_price_push_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_price_pull_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    sync_enabled: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(UTC),
            onupdate=lambda: datetime.now(UTC),
        ),
    )

    integration: Optional["Integration"] = Relationship(back_populates="product_links")
    product: Optional["Product"] = Relationship(back_populates="integration_links")




    