# backend/api/v1/routes/integrations/__init__.py
"""
Integrations API - Modular router combining all integration endpoints.
"""

from fastapi import APIRouter

from .oauth import router as oauth_router
from .crud import router as crud_router
from .sync import router as sync_router
from .links import router as links_router
from .operations import router as operations_router
from .shopify_gdpr import router as shopify_gdpr_router
from .shopify_install import router as shopify_install_router
from .shopify_billing import router as shopify_billing_router 

router = APIRouter(prefix="/integrations", tags=["Integrations"])

router.include_router(oauth_router)
router.include_router(crud_router)
router.include_router(sync_router)
router.include_router(links_router)
router.include_router(operations_router)
router.include_router(shopify_gdpr_router)
router.include_router(shopify_install_router)
router.include_router(shopify_billing_router)  

