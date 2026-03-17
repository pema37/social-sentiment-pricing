# backend/schemas/health.py

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    api: str
    version: str
    database: str
    uptime_seconds: float
    timestamp_utc: str
