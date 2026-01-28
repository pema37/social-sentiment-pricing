# backend/services/pricing/__init__.py
"""
Pricing Services - Rule evaluation, recommendation generation, and approval workflow.

Services:
    - RuleEvaluator: Evaluates pricing rules against current conditions
    - SignalProcessor: Processes sentiment and market signals
    - ConfidenceCalculator: Calculates confidence scores for recommendations
    - RecommendationService: Generates price recommendations
    - ApprovalService: Core approval/rejection workflow
    - AutoApprovalService: Batch auto-approval processing
    - EcommercePushService: Push prices to connected platforms (Shopify, WooCommerce)
    
New (Refactored):
    - PriceSyncService: Sync live prices from e-commerce stores
    - SettingsService: Manage user pricing settings with defaults
    - CompetitorFallbackService: Generate competitor-based recommendations
    - PriceCalculator, BoundaryEnforcer, ReasoningGenerator: Calculation helpers
"""

from .rule_evaluator import RuleEvaluator
from .signal_processor import SignalProcessor
from .confidence_calculator import ConfidenceCalculator
from .recommendation_service import RecommendationService
from .approval_service import ApprovalService
from .auto_approval_service import AutoApprovalService
from .ecommerce_push_service import EcommercePushService

# New refactored modules
from .price_sync_service import PriceSyncService
from .settings_service import SettingsService
from .competitor_fallback import CompetitorFallbackService
from .recommendation_helpers import (
    PriceCalculator,
    BoundaryEnforcer,
    ReasoningGenerator,
)

__all__ = [
    # Rule & Signal Processing
    "RuleEvaluator",
    "SignalProcessor",
    "ConfidenceCalculator",
    
    # Recommendations
    "RecommendationService",
    
    # Approval Workflow
    "ApprovalService",
    "AutoApprovalService",
    
    # E-commerce Integration
    "EcommercePushService",
    
    # New - Supporting Services
    "PriceSyncService",
    "SettingsService",
    "CompetitorFallbackService",
    
    # New - Helpers
    "PriceCalculator",
    "BoundaryEnforcer",
    "ReasoningGenerator",
]



