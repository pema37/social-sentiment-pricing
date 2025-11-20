# main.py

from fastapi import FastAPI
from backend.api.v1.routes.auth import router as auth_router
from backend.services.db import get_db_connection

# -------------------------------------------------------------
# Create the FastAPI instance.
# The 'title' is optional but useful for documentation (Swagger UI).
# -------------------------------------------------------------
app = FastAPI(title="Social Sentiment Pricing API")

# -------------------------------------------------------------
# GET /db-test
# Simple endpoint used to verify that the backend can connect to
# the PostgreSQL database successfully.
# This endpoint should NOT exist in production.
# -------------------------------------------------------------
@app.get("/db-test")
def test_db():
    """
    Attempts to open and close a database connection.
    If no exception is raised, the connection is considered valid.
    """
    conn = get_db_connection()  # Try to connect
    conn.close()                # Close after successful connection
    return {"status": "Database connection successful"}

# -------------------------------------------------------------
# Include all API routes for authentication-related operations.
# These routes will be accessible under the prefix /api/v1
# Example: /api/v1/login
# -------------------------------------------------------------
app.include_router(auth_router, prefix="/api/v1")
