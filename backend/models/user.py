# backend/models/user.py
from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import EmailStr


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: EmailStr = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default="USER")
