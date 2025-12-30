# backend/services/integration/repositories/__init__.py

"""
Repository Layer - Data Access Abstraction

Provides clean database operations for integration services.
Follows repository pattern - separates data access from business logic.
"""

from .product_repo import ProductRepository
from .link_repo import LinkRepository

__all__ = [
    "ProductRepository",
    "LinkRepository",
]

