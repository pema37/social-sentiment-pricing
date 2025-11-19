# test_config.py
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import psycopg2
from psycopg2 import OperationalError
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Get DATABASE_URL and JWT_SECRET_KEY from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# Parse DATABASE_URL into components: host, port, database, user, password
# urlparse splits a full URL into parts like scheme, hostname, port, path, username, password.
# This is useful because DATABASE_URL is in the form:
# postgresql://user:password@host:port/dbname?sslmode=require
# So we can easily extract DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
if DATABASE_URL:
    result = urlparse(DATABASE_URL)
    DB_HOST = result.hostname
    DB_PORT = result.port
    DB_NAME = result.path.lstrip('/')  # Remove leading slash from path
    DB_USER = result.username
    DB_PASSWORD = result.password
else:
    # Set all DB variables to None if DATABASE_URL is not provided
    DB_HOST = DB_PORT = DB_NAME = DB_USER = DB_PASSWORD = None

# Print out database connection info for verification
print("DB_HOST:", DB_HOST)
print("DB_PORT:", DB_PORT)
print("DB_NAME:", DB_NAME)
print("DB_USER:", DB_USER)
print("DB_PASSWORD:", DB_PASSWORD)

# Test connection to the database using psycopg2
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"  # match SSL requirement in DATABASE_URL
    )
    print("Database connection: OK")
    conn.close()  # Close connection after test
except OperationalError as e:
    print("Error connecting to the database:", e)
