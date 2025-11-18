from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    role: str = Field(default="user", index=True)  # e.g. "user" / "admin"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # One-to-many: User → Products
    products: List["Product"] = Relationship(back_populates="owner")


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # Owner of this product (the app’s user)
    owner_id: int = Field(foreign_key="user.id", index=True)

    name: str
    sku: Optional[str] = Field(default=None, index=True)  # internal SKU
    base_price: float
    currency: str = Field(default="USD", max_length=3)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship back to User
    owner: Optional[User] = Relationship(back_populates="products")

    # One-to-many: Product → CompetitorProduct links
    competitor_links: List["CompetitorProduct"] = Relationship(
        back_populates="product"
    )


class Competitor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    website: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # One-to-many: Competitor → CompetitorProduct links
    products: List["CompetitorProduct"] = Relationship(
        back_populates="competitor"
    )


class CompetitorProduct(SQLModel, table=True):
    """
    Link table between your Product and a competitor’s version of it.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    product_id: int = Field(foreign_key="product.id", index=True)
    competitor_id: int = Field(foreign_key="competitor.id", index=True)

    competitor_sku: Optional[str] = None
    competitor_url: Optional[str] = None
    last_seen_price: Optional[float] = None
    currency: str = Field(default="USD", max_length=3)

    product: Optional[Product] = Relationship(back_populates="competitor_links")
    competitor: Optional[Competitor] = Relationship(back_populates="products")

    