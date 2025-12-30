# backend/services/integration/handlers/__init__.py

"""
Sync Handlers - Business Logic Layer

Contains the business logic for product synchronization.
Uses repositories for data access.
"""

from .product_sync_handler import ProductSyncHandler

__all__ = [
    "ProductSyncHandler",
]
