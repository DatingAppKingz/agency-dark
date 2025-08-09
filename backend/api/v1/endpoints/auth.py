"""
Authentication endpoints using security_v2 system.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from core.database import get_db
from core.security_v2 import (
    verify_password,
    hash_password,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_token,
    get_current_user,
    get_current_user_optional,
    session_manager
)
from core.config import settings
from models.user import User, Session, UserRole
from models.agency import Agency
from core.domain.schemas import (
    LoginRequest,
    Token,
    TokenData,
    UserCreate,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    RefreshTokenRequest
)
from core.dependencies import CurrentUser, CurrentUserOptional
from core.email.email_service import email_service
from core.middleware.rate_limit import rate_limit
from core.errors import (
    DuplicateError,
    NotFoundError,
    AuthenticationError,
    ValidationError as AppValidationError
)
from core.logger import get_logger
import asyncio
import secrets
import hashlib

logger = get_logger(__name__)

router = APIRouter()
security = HTTPBearer()


def generate_verification_token() -> str:
    """Generate a secure verification token."""
    return secrets.token_urlsafe(32)


def generate_token_fingerprint() -> tuple[str, str]:
    """Generate a token fingerprint for additional security."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def verify_token_fingerprint(raw: str, hashed: str) -> bool:
    """Verify a token fingerprint."""
    return hashlib.sha256(raw.encode()).hexdigest() == hashed


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, fingerprint: str):
    """Set authentication cookies."""
    # Access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    # Refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    
    # Fingerprint cookie
    response.set_cookie(
        key="__Secure-Fgp",
        value=fingerprint,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


def clear_auth_cookies(response: Response):
    """Clear authentication cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("__Secure-Fgp")


def generate_csrf_token() -> str:
    """Generate CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, expected: str) -> bool:
    """Verify CSRF token."""
    return secrets.compare_digest(token, expected)


@router.post("/register", response_model=UserResponse)
@rate_limit(requests_per_minute=5, requests_per_hour=20)  # Strict limit for registration
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user."""
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise DuplicateError(
            resource="User",
            field="email",
            value=user_data.email
        )
    
    # If agency_id is provided, verify it exists
    if user_data.agency_id:
        agency = await db.get(Agency, user_data.agency_id)
        if not agency:
            raise NotFoundError(
                resource="Agency",
                identifier=user_data.agency_id
            )
    
    # Create new user
    # Extract username from email if not provided
    username = user_data.email.split('@')[0]
    
    user = User(
        email=user_data.email,
        username=username,
        password_hash=hash_password(user_data.password),  # Use security_v2 hash
        role=user_data.role or UserRole.MEMBER,
        agency_id=user_data.agency_id,
        is_active=True,  # For MVP, activate immediately
        is_verified=False
    )
    
    # If full_name is provided, split it into first and last names
    if user_data.full_name:
        names = user_data.full_name.strip().split(' ', 1)
        user.first_name = names[0]
        if len(names) > 1:
            user.last_name = names[1]
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Send verification email asynchronously
    asyncio.create_task(
        email_service.send_verification_email(user.email, generate_verification_token())
    )
    
    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
@rate_limit(requests_per_minute=10, requests_per_hour=100)
async def login(
    response: Response,
    form_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login and receive access tokens."""
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == form_data.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning(f"Failed login attempt for email: {form_data.email}")
        raise AuthenticationError("Invalid email or password")
    
    if not user.is_active:
        raise AuthenticationError("Account is inactive")
    
    # Generate token fingerprint for additional security
    raw_fingerprint, hashed_fingerprint = generate_token_fingerprint()
    
    # Create tokens using security_v2
    access_token, refresh_token = create_token_pair(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        additional_claims={
            "agency_id": str(user.agency_id) if user.agency_id else None,
            "fingerprint": hashed_fingerprint
        }
    )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create session record
    session = Session(
        user_id=user.id,
        token=access_token[:50],  # Store partial token for reference
        expires_at=datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        ip_address=form_data.ip_address if hasattr(form_data, 'ip_address') else None,
        user_agent=form_data.user_agent if hasattr(form_data, 'user_agent') else None
    )
    db.add(session)
    await db.commit()
    
    # Set cookies
    set_auth_cookies(response, access_token, refresh_token, raw_fingerprint)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: CurrentUserOptional,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Logout and invalidate tokens."""
    if current_user and credentials:
        # Invalidate session
        await db.execute(
            text("DELETE FROM sessions WHERE user_id = :user_id"),
            {"user_id": current_user.id}
        )
        await db.commit()
        
        # Add token to blacklist (if using session_manager)
        await session_manager.revoke_token(credentials.credentials)
    
    # Clear cookies
    clear_auth_cookies(response)
    
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    if not refresh_token:
        raise AuthenticationError("Refresh token not provided")
    
    # Decode and verify refresh token
    payload = decode_token(refresh_token, token_type="refresh")
    if not payload:
        raise AuthenticationError("Invalid refresh token")
    
    # Get user
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    
    # Generate new token pair
    raw_fingerprint, hashed_fingerprint = generate_token_fingerprint()
    
    access_token, new_refresh_token = create_token_pair(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        additional_claims={
            "agency_id": str(user.agency_id) if user.agency_id else None,
            "fingerprint": hashed_fingerprint
        }
    )
    
    # Update cookies
    set_auth_cookies(response, access_token, new_refresh_token, raw_fingerprint)
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser
):
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.post("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify user email with token."""
    # This would need proper implementation with token storage
    # For now, just a placeholder
    return {"message": "Email verification endpoint - implement with proper token storage"}


@router.post("/forgot-password")
@rate_limit(requests_per_minute=3, requests_per_hour=10)
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset."""
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    # Always return success to prevent email enumeration
    if user:
        reset_token = generate_verification_token()
        # Store reset token (implement proper storage)
        asyncio.create_task(
            email_service.send_password_reset_email(user.email, reset_token)
        )
    
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Reset password with token."""
    # This would need proper implementation with token storage
    # For now, just validate the new password and update
    
    # Placeholder: In real implementation, verify token first
    # user = await verify_reset_token(request.token)
    
    return {"message": "Password reset endpoint - implement with proper token storage"}


@router.get("/verify-token")
async def verify_access_token(
    current_user: CurrentUserOptional
):
    """Verify if access token is valid."""
    if current_user:
        return {"valid": True, "user_id": str(current_user.id)}
    return {"valid": False}