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
"""

from .rule_evaluator import RuleEvaluator
from .signal_processor import SignalProcessor
from .confidence_calculator import ConfidenceCalculator
from .recommendation_service import RecommendationService
from .approval_service import ApprovalService
from .auto_approval_service import AutoApprovalService
from .ecommerce_push_service import EcommercePushService

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
]


