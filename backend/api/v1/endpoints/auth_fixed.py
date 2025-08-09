"""
Fixed authentication endpoints that work with current database.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_db
from core.security_v2 import (
    verify_password,
    hash_password,
    create_token_pair,
)
from core.config import settings
from core.domain.schemas import LoginRequest, Token
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Simple login that works with current database."""
    # Direct SQL to avoid ORM issues
    result = await db.execute(
        text("""
            SELECT id, email, hashed_password, role, is_active, agency_id
            FROM users 
            WHERE email = :email
        """),
        {"email": form_data.email}
    )
    user = result.fetchone()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    user_id, email, password_hash, role, is_active, agency_id = user
    
    if not verify_password(form_data.password, password_hash):
        logger.warning(f"Failed login attempt for email: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Create tokens
    access_token, refresh_token = create_token_pair(
        user_id=str(user_id),
        email=email,
        role=role,
        additional_claims={
            "agency_id": str(agency_id) if agency_id else None
        }
    )
    
    # Update last login
    await db.execute(
        text("UPDATE users SET last_login = :now WHERE id = :id"),
        {"now": datetime.utcnow(), "id": user_id}
    )
    await db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.get("/me")
async def get_current_user_info(
    db: AsyncSession = Depends(get_db),
    current_user = Depends()
):
    """Get current user information."""
    from core.security_v2 import get_current_user
    user = await get_current_user(db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Return user data directly from SQL
    result = await db.execute(
        text("""
            SELECT id, email, full_name, role, is_active, is_verified, 
                   agency_id, created_at, updated_at, last_login
            FROM users 
            WHERE id = :id
        """),
        {"id": user["user_id"]}
    )
    user_data = result.fetchone()
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": str(user_data[0]),
        "email": user_data[1],
        "full_name": user_data[2],
        "role": user_data[3],
        "is_active": user_data[4],
        "is_verified": user_data[5],
        "agency_id": str(user_data[6]) if user_data[6] else None,
        "created_at": user_data[7],
        "updated_at": user_data[8],
        "last_login": user_data[9]
    }