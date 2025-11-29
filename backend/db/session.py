# backend/db/session.py

import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in the environment (.env file).")

# VERY IMPORTANT FIXES:
# - pool_pre_ping=True  → avoids stale/closed SSL connections
# - pool_recycle=300    → recycles connections every 5 minutes
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Proper session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,  # SQLModel's Session
)


def get_db():
    """FastAPI dependency — use this everywhere in routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Optional legacy alias if some parts still import get_session()
def get_session():
    yield from get_db()
