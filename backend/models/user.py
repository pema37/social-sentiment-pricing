# backend/models/user.py

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

if TYPE_CHECKING:
    from models.integration import Integration


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    email: str = Field(index=True, unique=True)
    username: Optional[str] = Field(default=None, index=True)
    full_name: Optional[str] = Field(default=None, max_length=255) 

    hashed_password: str

    role: str = Field(default="USER")
    is_active: bool = Field(default=True)

    # BSV wallet address for MNEE payments
    bsv_wallet_address: Optional[str] = Field(default=None, max_length=50)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), onupdate=datetime.utcnow),
    )

    # Relationships
    integrations: List["Integration"] = Relationship(back_populates="user")

