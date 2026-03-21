# backend/schemas/user.py

import uuid

from pydantic import ConfigDict, EmailStr
from sqlmodel import SQLModel


# BASE USER (shared fields)
class UserBase(SQLModel):
    email: EmailStr
    username: str | None = None
    is_active: bool = True


# CREATE USER (register)
class UserCreate(SQLModel):
    email: EmailStr
    password: str
    username: str | None = None


# READ USER (response model)
class UserRead(SQLModel):
    id: uuid.UUID
    email: EmailStr
    username: str | None = None
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# UPDATE CURRENT USER (partial update)
class UserUpdateMe(SQLModel):
    username: str | None = None
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = None  # plain password to be hashed

    model_config = ConfigDict(from_attributes=True)
