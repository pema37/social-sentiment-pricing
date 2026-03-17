"""
Audit Email Delivery Route

POST /api/v1/audit/retrospective/email — Generate audit PDF and send via email
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.logging import get_logger
from db.session import get_session
from models.user import User
from schemas.retrospective_audit import AuditRequest
from services.audit_pdf_generator import generate_audit_pdf
from services.notification.audit_email_service import AuditEmailService
from services.retrospective_audit_service import RetrospectiveAuditService

logger = get_logger(__name__)

router = APIRouter(prefix="/audit", tags=["Retrospective Audit"])


class AuditEmailRequest(BaseModel):
    """Request to email an audit PDF."""

    to_email: EmailStr
    lookback_days: int = Field(default=90, ge=7, le=365)
    store_name: str | None = Field(default=None, max_length=255)
    personal_note: str | None = Field(
        default=None, max_length=1000, description="Optional personal message included in the email body"
    )


class AuditEmailResponse(BaseModel):
    success: bool
    message: str
    message_id: str | None = None


@router.post("/retrospective/email", response_model=AuditEmailResponse)
async def email_audit_pdf(
    request: AuditEmailRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a retrospective audit and email the PDF to a prospect.

    This is the "Share via Email" button on the audit dashboard.
    Generates a fresh audit, builds the branded PDF, and sends it
    via SendGrid with the big red headline number in the email body.
    """
    # Generate the audit
    audit_request = AuditRequest(lookback_days=request.lookback_days)
    service = RetrospectiveAuditService(session, str(current_user.id))
    audit = await service.generate_audit(audit_request)

    if audit.summary.total_products_analyzed == 0:
        raise HTTPException(status_code=422, detail="No products with competitor data to audit.")

    # Build PDF
    pdf_bytes = generate_audit_pdf(audit)

    # Format headline number
    impact = float(audit.summary.total_estimated_impact)
    headline = f"${impact:,.0f}"

    # Send email
    email_service = AuditEmailService()
    sender_name = getattr(current_user, "full_name", None) or "ActualPrice"

    result = await email_service.send_audit_pdf(
        to_email=request.to_email,
        pdf_bytes=pdf_bytes,
        store_name=request.store_name,
        headline_impact=headline,
        lookback_days=request.lookback_days,
        sender_name=sender_name,
        personal_note=request.personal_note,
    )

    if result.success:
        logger.info(f"Audit email sent to {request.to_email} by user {current_user.id}, impact={headline}")
        return AuditEmailResponse(
            success=True,
            message=f"Audit sent to {request.to_email}",
            message_id=result.message_id,
        )
    else:
        logger.error(f"Audit email failed: {result.error}")
        raise HTTPException(status_code=502, detail=f"Failed to send email: {result.error}")
