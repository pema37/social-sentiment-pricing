# backend/models/__init__.py

from .user import User
from .product import Product
from .sentiment import Sentiment
from .price_history import PriceHistory

__all__ = ["User", "Product", "Sentiment", "PriceHistory"]

