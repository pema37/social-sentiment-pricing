# backend/db/session.py

import os
from sqlmodel import create_engine, Session
from dotenv import load_dotenv
from ..core.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD



# Load environment variables from the .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in the environment (.env file).")

engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    with Session(engine) as session:
        yield session
