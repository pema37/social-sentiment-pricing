# backend/models/user.py

from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)

    email: str = Field(index=True, unique=True)
    username: Optional[str] = Field(default=None, index=True)

    hashed_password: str

    role: str = Field(default="USER")
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
