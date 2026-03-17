# backend/models/user.py
import uuid as uuid_lib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.integration import Integration


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    email: str = Field(index=True, unique=True)
    username: str | None = Field(default=None, index=True)
    full_name: str | None = Field(default=None, max_length=255)
    hashed_password: str
    role: str = Field(default="USER")
    is_active: bool = Field(default=True)

    # Wallet addresses for MNEE payments
    bsv_wallet_address: str | None = Field(default=None, max_length=50)
    eth_wallet_address: str | None = Field(default=None, max_length=42)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), onupdate=lambda: datetime.now(UTC)),
    )

    # Relationships
    integrations: list["Integration"] = Relationship(back_populates="user")
