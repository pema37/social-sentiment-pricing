# backend/services/db.py

import os
from urllib.parse import urlparse
import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv
from pathlib import Path

# -------------------------------------------------------------
# Load the .env file manually.
# The .env file is located in the project root, not inside /services,
# so we move up three directories from this file.
# -------------------------------------------------------------
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# -------------------------------------------------------------
# Read the DATABASE_URL from the environment variables.
# This URL contains all connection details in a single string.
# -------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # If the DATABASE_URL is missing, we stop execution immediately
    # because the application cannot connect to the database.
    raise Exception("DATABASE_URL not found in .env")

# -------------------------------------------------------------
# Parse the DATABASE_URL into individual components:
# host, port, database name, username and password.
# Example:
# postgresql://user:password@host:port/dbname
# -------------------------------------------------------------
result = urlparse(DATABASE_URL)

DB_HOST = result.hostname
DB_PORT = result.port
DB_NAME = result.path.lstrip("/")     # Remove leading "/"
DB_USER = result.username
DB_PASSWORD = result.password

# -------------------------------------------------------------
# Function: get_db_connection()
# Creates a new PostgreSQL connection using psycopg2.
# Returned connection MUST be closed after use.
# -------------------------------------------------------------
def get_db_connection():
    """
    Creates and returns a PostgreSQL connection using parameters
    extracted from DATABASE_URL. Raises OperationalError if the
    connection fails.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode="require",   # Neon requires SSL mode
        )
        return conn
    except OperationalError as e:
        # Prints the error for debugging and re-raises it so the application
        # does not continue silently.
        print("DATABASE CONNECTION ERROR ->", e)
        raise e
