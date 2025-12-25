"""
Wallet Management Routes

Handles BSV wallet address storage and balance checking.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from core.deps import get_current_user
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class WalletAddressUpdate(BaseModel):
    """Request to update wallet address."""
    bsv_wallet_address: str = Field(
        ...,
        min_length=25,
        max_length=34,
        description="BSV wallet address (starts with 1 or 3)"
    )
    
    @field_validator("bsv_wallet_address")
    @classmethod
    def validate_bsv_address(cls, v: str) -> str:
        """Validate BSV address format."""
        v = v.strip()
        
        # Reject Ethereum addresses
        if v.startswith("0x"):
            raise ValueError(
                "Ethereum addresses (0x...) are not supported. "
                "MNEE uses BSV addresses starting with '1' or '3'."
            )
        
        # Check BSV format
        if not v.startswith(("1", "3")):
            raise ValueError("BSV address must start with '1' or '3'")
        
        # Base58 check (no 0, O, I, l)
        valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        if not all(c in valid_chars for c in v):
            raise ValueError("Invalid characters in BSV address")
        
        return v


class WalletResponse(BaseModel):
    """Wallet information response."""
    bsv_wallet_address: Optional[str] = None
    balance: Optional[str] = None
    balance_raw: Optional[int] = None
    
    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    """Balance check response."""
    address: str
    balance: str
    balance_raw: int


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "/wallet",
    response_model=WalletResponse,
    summary="Get wallet info",
    description="Get current user's BSV wallet address and balance"
)
async def get_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's wallet address and optionally check balance."""
    wallet_address = getattr(current_user, "bsv_wallet_address", None)
    
    response = WalletResponse(bsv_wallet_address=wallet_address)
    
    # Optionally fetch balance if wallet is set
    if wallet_address:
        try:
            from services.payment import get_mnee_service
            mnee = get_mnee_service()
            balance_data = await mnee.get_balance(wallet_address)
            response.balance = balance_data.get("balance")
            response.balance_raw = balance_data.get("balance_raw")
        except Exception as e:
            logger.warning(f"Failed to fetch balance: {e}")
            # Don't fail the request, just return without balance
    
    return response


@router.put(
    "/wallet",
    response_model=WalletResponse,
    summary="Update wallet address",
    description="Save or update BSV wallet address for payments"
)
async def update_wallet(
    request: WalletAddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's BSV wallet address."""
    # Update user's wallet address
    current_user.bsv_wallet_address = request.bsv_wallet_address
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"User {current_user.id} updated wallet address")
    
    return WalletResponse(bsv_wallet_address=current_user.bsv_wallet_address)


@router.delete(
    "/wallet",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove wallet address",
    description="Remove saved BSV wallet address"
)
async def remove_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove user's wallet address."""
    current_user.bsv_wallet_address = None
    
    db.add(current_user)
    await db.commit()
    
    logger.info(f"User {current_user.id} removed wallet address")


@router.get(
    "/balance/{address}",
    response_model=BalanceResponse,
    summary="Check any address balance",
    description="Check MNEE balance for any BSV address (for testing)"
)
async def check_balance(
    address: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check MNEE balance for any BSV address.
    
    Useful for:
    - Testing API connectivity
    - Verifying payment received
    - Checking other addresses
    """
    try:
        from services.payment import get_mnee_service, MneeValidationError
        
        mnee = get_mnee_service()
        balance_data = await mnee.get_balance(address)
        
        return BalanceResponse(
            address=address,
            balance=balance_data["balance"],
            balance_raw=balance_data["balance_raw"],
        )
        
    except MneeValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message),
        )
    except Exception as e:
        logger.error(f"Balance check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to check balance. Please try again.",
        )
