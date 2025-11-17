import os
from sqlmodel import SQLModel, create_engine
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")

engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
)


def init_db() -> None:
    # Import models so they are registered with SQLModel.metadata
    import models  # models.py is in the same folder as db.py

    SQLModel.metadata.create_all(engine)
