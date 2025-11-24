# backend/schemas/user.py

from typing import Optional
from sqlmodel import SQLModel
from pydantic import EmailStr

# BASE USER (shared fields)
class UserBase(SQLModel):
    email: EmailStr
    username: Optional[str] = None
    is_active: bool = True


# CREATE USER (register)
class UserCreate(SQLModel):
    email: EmailStr
    password: str
    username: Optional[str] = None


# READ USER (response model)
class UserRead(SQLModel):
    id: int
    email: EmailStr
    username: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True  


# UPDATE CURRENT USER (partial update)
class UserUpdateMe(SQLModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None  # plain password to be hashed

    class Config:         
        from_attributes = True   
