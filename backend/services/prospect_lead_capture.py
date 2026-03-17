"""
Prospect Lead Capture Service

Captures leads from the Free Pricing Audit and pushes them to HubSpot CRM.
Falls back to logging if HubSpot is not configured.

Environment variables:
  HUBSPOT_API_KEY — HubSpot private app access token
"""

import os

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")
HUBSPOT_CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts"


async def capture_lead(
    email: str,
    company_name: str | None = None,
    store_url: str | None = None,
    source: str = "free_pricing_audit",
) -> bool:
    """
    Capture a prospect lead.

    1. Always logs the lead (structured logging → your log aggregator)
    2. If HUBSPOT_API_KEY is set, creates/updates a HubSpot contact

    Returns True if CRM push succeeded (or was skipped), False on error.
    """
    # Always log
    logger.info(
        "Lead captured",
        email=email,
        company=company_name,
        store_url=store_url,
        source=source,
    )

    # Push to HubSpot if configured
    if not HUBSPOT_API_KEY:
        logger.debug("HUBSPOT_API_KEY not set — skipping CRM push")
        return True

    try:
        properties = {
            "email": email,
            "lead_source": source,
        }
        if company_name:
            properties["company"] = company_name
        if store_url:
            properties["website"] = store_url

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                HUBSPOT_CONTACTS_URL,
                headers={
                    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"properties": properties},
            )

            if resp.status_code == 409:
                # Contact already exists — update instead
                logger.info(f"HubSpot contact already exists for {email}, updating")
                # Extract existing contact ID from conflict response
                conflict_data = resp.json()
                existing_id = conflict_data.get("message", "").split("Existing ID: ")[-1].strip()

                if existing_id and existing_id.isdigit():
                    update_resp = await client.patch(
                        f"{HUBSPOT_CONTACTS_URL}/{existing_id}",
                        headers={
                            "Authorization": f"Bearer {HUBSPOT_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={"properties": properties},
                    )
                    update_resp.raise_for_status()
                    logger.info(f"HubSpot contact updated: {existing_id}")
                return True

            resp.raise_for_status()
            contact_id = resp.json().get("id")
            logger.info(f"HubSpot contact created: {contact_id} for {email}")
            return True

    except Exception as e:
        logger.error(f"HubSpot CRM push failed for {email}: {e}")
        # Don't block the PDF generation — log and move on
        return False
