# ======================================================
# User Model (SQLModel)
# Represents the users stored in the database.
# Includes basic fields for authentication and role-based access.
# All fields are fully typed and validated.
# ======================================================

from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import EmailStr


class User(SQLModel, table=True):
    """
    Database model representing an application user.
    Inherits from SQLModel to support both Pydantic validation
    and SQLAlchemy ORM features.

    'table=True' indicates that SQLModel will generate a real
    database table named 'user'.
    """

    # Auto-increment primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Public username used for identification inside the platform
    # Indexed for faster lookup
    username: str = Field(index=True)

    # Email used as unique identifier for login
    # EmailStr ensures proper validation
    # Indexed + unique constraint prevents duplicates
    email: EmailStr = Field(index=True, unique=True)

    # Securely hashed password (never store plaintext passwords)
    password_hash: str

    # Defines user access level (USER or ADMIN)
    # Defaults to normal USER
    role: str = Field(default="USER")
