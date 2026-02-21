# backend/api/v1/routes/payments/wallet.py

"""
Wallet Management Endpoints

Handles BSV wallet address management for MNEE payments.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel, field_validator

from db.session import get_session
from core.deps import get_current_user
from models.user import User
from services.payment import get_mnee_service, MneeValidationError

router = APIRouter(tags=["payments"])


# =============================================================================
# SCHEMAS
# =============================================================================

class WalletAddressUpdate(BaseModel):
    """Request schema for updating wallet address."""
    bsv_wallet_address: str
    
    @field_validator('bsv_wallet_address')
    @classmethod
    def validate_bsv_address(cls, v: str) -> str:
        """Validate BSV address format."""
        if not v:
            raise ValueError('BSV wallet address is required')
        
        # Reject Ethereum addresses explicitly
        if v.startswith('0x'):
            raise ValueError(
                'Ethereum addresses (0x...) are not supported. '
                'MNEE uses BSV addresses starting with "1" or "3".'
            )
        
        # BSV addresses start with 1 or 3
        if not v.startswith('1') and not v.startswith('3'):
            raise ValueError('BSV address must start with "1" or "3"')
        
        # BSV addresses are 25-34 characters
        if len(v) < 25 or len(v) > 34:
            raise ValueError('BSV address must be 25-34 characters')
        
        return v


class WalletInfo(BaseModel):
    """Response schema for wallet info."""
    bsv_wallet_address: str | None
    balance: str | None = None
    balance_raw: int | None = None


class BalanceInfo(BaseModel):
    """Response schema for balance check."""
    address: str
    balance: str
    balance_raw: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/wallet", response_model=WalletInfo)
async def get_wallet(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get current user's wallet address and balance.
    """
    balance = None
    balance_raw = None
    
    # If user has a wallet, fetch balance
    if current_user.bsv_wallet_address:
        try:
            mnee_service = get_mnee_service()
            balance_data = await mnee_service.get_balance(current_user.bsv_wallet_address)
            balance = balance_data.get("balance")
            balance_raw = balance_data.get("balance_raw")
        except Exception:
            # Balance fetch failed, but we can still return the address
            pass
    
    return WalletInfo(
        bsv_wallet_address=current_user.bsv_wallet_address,
        balance=balance,
        balance_raw=balance_raw,
    )


@router.put("/wallet", response_model=WalletInfo)
async def update_wallet(
    data: WalletAddressUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update user's BSV wallet address.
    """
    # Validate address with MNEE service
    try:
        mnee_service = get_mnee_service()
        mnee_service.validate_bsv_address(data.bsv_wallet_address)
    except MneeValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Update user's wallet address
    current_user.bsv_wallet_address = data.bsv_wallet_address
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    
    # Fetch balance for the new address
    balance = None
    balance_raw = None
    try:
        balance_data = await mnee_service.get_balance(data.bsv_wallet_address)
        balance = balance_data.get("balance")
        balance_raw = balance_data.get("balance_raw")
    except Exception:
        pass
    
    return WalletInfo(
        bsv_wallet_address=current_user.bsv_wallet_address,
        balance=balance,
        balance_raw=balance_raw,
    )


@router.delete("/wallet", status_code=status.HTTP_204_NO_CONTENT)
async def remove_wallet(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Remove user's wallet address.
    """
    current_user.bsv_wallet_address = None
    session.add(current_user)
    await session.commit()


@router.get("/balance/{address}", response_model=BalanceInfo)
async def check_balance(
    address: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check balance for any BSV address.
    """
    try:
        mnee_service = get_mnee_service()
        mnee_service.validate_bsv_address(address)
        balance_data = await mnee_service.get_balance(address)
        
        return BalanceInfo(
            address=address,
            balance=balance_data.get("balance", "0"),
            balance_raw=balance_data.get("balance_raw", 0),
        )
    except MneeValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch balance: {str(e)}",
        )
    
    