# ======================================================
# security.py
# ======================================================

import json
import os
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

# ----------------------------
# Configurações do JWT
# ----------------------------
SECRET_KEY = "YOUR_SECRET_KEY_CHANGE_THIS"  # muda para algo secreto
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# ----------------------------
# Passlib context para bcrypt
# ----------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ======================================================
# PASSWORD HASHING
# ======================================================
def hash_password(password: str) -> str:
    """
    Hash the password using bcrypt (truncate to 72 bytes to avoid Windows issues)
    """
    password_bytes = password.encode("utf-8")[:72]
    password_truncated = password_bytes.decode("utf-8", errors="ignore")
    return pwd_context.hash(password_truncated)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify the password against the hash (truncate to 72 bytes)
    """
    password_bytes = plain_password.encode("utf-8")[:72]
    password_truncated = password_bytes.decode("utf-8", errors="ignore")
    return pwd_context.verify(password_truncated, hashed_password)

# ======================================================
# JWT TOKEN FUNCTIONS
# ======================================================
def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    Create a JWT token with optional expiration
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    Decode JWT token safely
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# ======================================================
# USERS JSON PERSISTENCE
# ======================================================
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def load_users() -> list:
    """
    Load users from JSON file safely
    """
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_user(user: dict):
    """
    Save a single user to JSON file
    """
    users = load_users()
    users.append(user)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)
