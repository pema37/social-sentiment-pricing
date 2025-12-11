# backend/models/integration.py

"""
E-commerce Integration Model
Stores encrypted credentials for Shopify/WooCommerce connections

Aligned with architecture doc: Section 6.1 Shopify Integration
"""

import uuid as uuid_lib
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from sqlalchemy import Column as SAColumn, Text, LargeBinary, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

if TYPE_CHECKING:
    from models.user import User
    from models.product import Product


class EcommercePlatform(str, Enum):
    """Supported e-commerce platforms"""
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class IntegrationStatus(str, Enum):
    """Connection status states - matches architecture doc"""
    ACTIVE = "active"             # Successfully authenticated and working
    ERROR = "error"               # Auth failed or token expired
    PAUSED = "paused"             # User paused the integration
    DISCONNECTED = "disconnected" # User disconnected


class Integration(SQLModel, table=True):
    """
    Stores e-commerce platform connections and encrypted credentials.
    Each user can have one integration per platform.
    
    Note: Using user_id now, will migrate to organization_id when 
    Organization model is added for full multi-tenancy.
    """
    __tablename__ = "integrations"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True)
    )
    
    # Foreign key to user (will become organization_id later)
    user_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    )
    
    # Platform identification
    platform: EcommercePlatform = Field(index=True)
    store_url: str = Field(max_length=255)  # e.g., "mystore.myshopify.com"
    store_name: Optional[str] = Field(default=None, max_length=255)
    
    # Status tracking
    status: IntegrationStatus = Field(default=IntegrationStatus.ACTIVE, index=True)
    error_message: Optional[str] = Field(default=None, sa_column=SAColumn(Text))
    
    # ========== Encrypted Credentials (Architecture Doc Aligned) ==========
    # Stored as BYTEA for proper binary encryption
    access_token_encrypted: bytes = Field(sa_column=SAColumn(LargeBinary, nullable=False))
    refresh_token_encrypted: Optional[bytes] = Field(
        default=None, 
        sa_column=SAColumn(LargeBinary, nullable=True)
    )
    token_expires_at: Optional[datetime] = Field(default=None)
    
    # OAuth scopes granted
    scopes: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # Webhook secret (encrypted)
    webhook_secret_encrypted: Optional[bytes] = Field(
        default=None,
        sa_column=SAColumn(LargeBinary, nullable=True)
    )
    # Webhook IDs for cleanup on disconnect
    webhook_ids: List[str] = Field(default=[], sa_column=Column(JSON))
    
    # ========== OAuth Flow (temporary fields) ==========
    oauth_state: Optional[str] = Field(default=None, max_length=64)
    
    # ========== Sync Metadata ==========
    last_sync_at: Optional[datetime] = Field(default=None)
    sync_status: str = Field(default="idle", max_length=20)  # idle, syncing, error
    products_synced: int = Field(default=0)
    sync_cursor: Optional[str] = Field(default=None, max_length=500)
    
    # ========== Flexible Settings (Architecture Doc) ==========
    settings: dict = Field(default={}, sa_column=Column(JSON))
    
    # ========== Timestamps ==========
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )
    
    # ========== Relationships ==========
    user: Optional["User"] = Relationship(back_populates="integrations")
    sync_logs: List["IntegrationSyncLog"] = Relationship(back_populates="integration")
    product_links: List["ProductIntegrationLink"] = Relationship(back_populates="integration")


class IntegrationSyncLog(SQLModel, table=True):
    """
    Tracks sync operations for debugging and monitoring.
    Useful for troubleshooting failed syncs and auditing.
    """
    __tablename__ = "integration_sync_logs"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True)
    )
    
    integration_id: uuid_lib.UUID = Field(
        sa_column=SAColumn(PG_UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False, index=True)
    )
    
    # Sync details
    sync_type: str = Field(max_length=50)  # "full", "incremental", "webhook"
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        index=True
    )
    completed_at: Optional[datetime] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)
    
    # Results
    success: bool = Field(default=False)
    products_created: int = Field(default=0)
    products_updated: int = Field(default=0)
    products_deleted: int = Field(default=0)
    error_details: Optional[str] = Field(default=None, sa_column=SAColumn(Text))
    
    # Relationship
    integration: Optional["Integration"] = Relationship(back_populates="sync_logs")


class ProductIntegrationLink(SQLModel, table=True):
    """
    Links our Product records to external platform product IDs.
    Enables two-way sync between SSP and Shopify/WooCommerce.
    
    One SSP product can be linked to multiple platforms.
    """
    __tablename__ = "product_integration_links"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=SAColumn(PG_UUID(as_uuid=True), primary_key=True)
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
    external_variant_id: Optional[str] = Field(default=None, max_length=100)
    
    # Sync state
    external_price: Optional[float] = Field(default=None)
    external_compare_at_price: Optional[float] = Field(default=None)
    last_price_push_at: Optional[datetime] = Field(default=None)
    last_price_pull_at: Optional[datetime] = Field(default=None)
    sync_enabled: bool = Field(default=True)
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    # Relationships
    integration: Optional["Integration"] = Relationship(back_populates="product_links")
    product: Optional["Product"] = Relationship(back_populates="integration_links")

