# backend/services/products/__init__.py
"""
Product Services Package

Provides modular business logic for product operations:
- ProductService: CRUD operations
- ProductImportService: Bulk CSV import
- cascade_delete_product: FK-safe deletion

Best Practices Applied:
- Single Responsibility: Each service does one thing
- Dependency Injection: Services receive session, don't create it
- Separation of Concerns: Business logic isolated from routing
"""

from .product_service import ProductService
from .import_service import ProductImportService
from .cascade_delete import cascade_delete_product

__all__ = [
    "ProductService",
    "ProductImportService", 
    "cascade_delete_product",
]

