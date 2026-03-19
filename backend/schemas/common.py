# backend/schemas/common.py

from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper."""

    model_config = ConfigDict(from_attributes=True)
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginationParams:
    """Dependency for pagination query parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
