# backend/api/v1/routes/pricing/recommendations.py
"""
Price recommendations router - main entry point.

This module combines all recommendation-related endpoints from sub-modules:
- _list_endpoints: list, get, stats (read operations)
- _generation_endpoints: generate, diagnose (analysis operations)
- _approval_endpoints: approve, reject, apply (write operations)

REFACTORED (2026-01-27): Split from single 400+ line file into logical modules
for better maintainability and testing.
"""

from fastapi import APIRouter

from ._approval_endpoints import router as approval_router
from ._generation_endpoints import router as generation_router
from ._list_endpoints import router as list_router

router = APIRouter()

# Include all sub-routers
# Order matters for route matching - more specific routes should come first

# Generation endpoints (includes /diagnose/{id} which must come before /{id})
router.include_router(generation_router)

# List endpoints (includes /stats, /pending, /{id})
router.include_router(list_router)

# Approval endpoints (/{id}/approve, /{id}/reject, /{id}/apply)
router.include_router(approval_router)
