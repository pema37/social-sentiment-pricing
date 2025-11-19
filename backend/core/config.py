# core/config.py
# ----------------------------
# This module loads environment variables and parses the database URL.
# We use python-dotenv to load the .env file and urllib to parse the DATABASE_URL.
# The parsed values are stored in variables for easy access throughout the project.
# ----------------------------

import os
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables from .env file
load_dotenv()

# Get the DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Parse the database URL into components
if DATABASE_URL:
    url = urlparse(DATABASE_URL)
    DB_HOST = url.hostname
    DB_PORT = url.port or 5432  # default PostgreSQL port if not specified
    DB_NAME = url.path[1:]  # remove leading '/'
    DB_USER = url.username
    DB_PASSWORD = url.password
else:
    DB_HOST = DB_PORT = DB_NAME = DB_USER = DB_PASSWORD = None

# JWT secret key (example, used elsewhere in authentication)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
