# backend/models/user.py

import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid_lib.UUID = Field(
        default_factory=uuid_lib.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )

    email: str = Field(index=True, unique=True)
    username: Optional[str] = Field(default=None, index=True)

    hashed_password: str

    role: str = Field(default="USER")
    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc)),
    )

