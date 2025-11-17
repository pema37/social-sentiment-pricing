# ======================================================
# main.py - Social Sentiment Pricing Auth Module
# ======================================================

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from app.auth.security import (
    hash_password, verify_password, create_access_token, decode_access_token,
    save_user, load_users
)
from pydantic import BaseModel, EmailStr

# ----------------------------
# Initialize FastAPI app
# ----------------------------
app = FastAPI(title="Social Sentiment Pricing - Auth Module")

# ----------------------------
# OAuth2 scheme for JWT
# ----------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ----------------------------
# Pydantic models for request validation
# ----------------------------
class RegisterUser(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "USER"  # Default role is USER

class LoginUser(BaseModel):
    email: EmailStr
    password: str

# ======================================================
# Utility function to decode JWT token and get current user
# ======================================================
def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Extract user info from JWT token.
    Raises 401 if token is invalid.
    """
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

# ======================================================
# Utility function to check user role
# ======================================================
def require_role(required_role: str):
    """
    Returns a dependency function that verifies the user's role.
    Raises 403 if role is insufficient.
    """
    def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] != required_role:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient permissions")
        return user
    return role_checker

# ======================================================
# Register endpoint
# ======================================================
@app.post("/api/auth/register")
def register(user: RegisterUser):
    """
    Registers a new user with hashed password and role.
    Stores user in users.json.
    """
    try:
        # Load all existing users
        users = load_users()
        if any(u["email"].lower() == user.email.lower() for u in users):
            raise HTTPException(status_code=400, detail="User already exists")

        # Create user dictionary
        user_dict = {
            "username": user.username,
            "email": user.email,
            "password_hash": hash_password(user.password),
            "role": user.role
        }

        # Save user to JSON file
        save_user(user_dict)

        return {"message": "User created successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print("Register error:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ======================================================
# Login endpoint
# ======================================================
@app.post("/api/auth/login")
def login(user: LoginUser):
    """
    Handles user login and returns a JWT token.
    Email is case-insensitive.
    Password is verified using bcrypt.
    """
    try:
        email_lower = user.email.lower()
        users = load_users()
        u = next((x for x in users if x["email"].lower() == email_lower), None)

        if not u or not verify_password(user.password, u["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"email": u["email"], "role": u["role"]})
        return {"token": token}

    except HTTPException:
        raise
    except Exception as e:
        print("Login error:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ======================================================
# Example protected endpoint for USERS
# ======================================================
@app.get("/api/user/data")
def get_user_data(current_user: dict = Depends(require_role("USER"))):
    """
    Returns a message only for USERS.
    JWT token must be provided in Authorization header.
    """
    return {"message": f"Hello {current_user['email']}! You have USER access."}

# ======================================================
# Example protected endpoint for ADMINS
# ======================================================
@app.get("/api/admin/data")
def get_admin_data(current_user: dict = Depends(require_role("ADMIN"))):
    """
    Returns a message only for ADMINS.
    JWT token must be provided in Authorization header.
    """
    return {"message": f"Hello {current_user['email']}! You have ADMIN access."}
