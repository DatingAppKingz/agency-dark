from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_verification_token,
    generate_token_fingerprint,
    verify_token_fingerprint
)
from core.auth.token_blacklist import token_blacklist_service
from core.auth.cookie_utils import set_auth_cookies, clear_auth_cookies
from core.auth.csrf import generate_csrf_token, verify_csrf_token
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

logger = get_logger(__name__)


router = APIRouter()
security = HTTPBearer()


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
        password_hash=get_password_hash(user_data.password),
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
    
    # Generate email verification token
    user.email_verification_token = generate_verification_token()
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Send verification email asynchronously
    asyncio.create_task(
        email_service.send_verification_email(
            to_email=user.email,
            user_name=user.full_name or user.email,
            verification_token=user.email_verification_token
        )
    )
    
    return user


@router.post("/login", response_model=Token)
@rate_limit(requests_per_minute=10, requests_per_hour=100, burst_size=3)  # Allow some burst for login
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password."""
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        # Add failed login attempt tracking
        await _track_failed_login(credentials.email, request.client.host if request.client else None, db)
        raise AuthenticationError("Incorrect email or password")
    
    if not user.is_active:
        raise AppValidationError(
            message="User account is disabled",
            fields={"account": "This account has been disabled"}
        )
    
    # Check for account lockout
    if await _is_account_locked(user.id, db):
        raise AppValidationError(
            message="Account temporarily locked due to multiple failed login attempts",
            fields={"account": "Too many failed login attempts. Please try again later."}
        )
    
    # Generate token fingerprint for additional security
    raw_fingerprint, fingerprint_hash = generate_token_fingerprint()
    
    # Create tokens with fingerprint
    access_token_data = {
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "fingerprint": fingerprint_hash
    }
    
    refresh_token_data = {
        "user_id": str(user.id),
        "fingerprint": fingerprint_hash
    }
    
    # Adjust token expiration based on remember_me
    access_token_expires = None  # Use default
    refresh_token_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
    
    if credentials.remember_me:
        # Extend refresh token to 30 days for remember me
        refresh_token_days = 30
    else:
        # Shorter refresh token for non-remember me sessions (7 days)
        refresh_token_days = 7
    
    access_token = create_access_token(data=access_token_data, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(data=refresh_token_data)
    
    # Extract user agent and IP
    user_agent = request.headers.get("User-Agent", "Unknown")
    ip_address = request.client.host if request.client else None
    
    # Store refresh token in database with remember_me consideration
    session = Session(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=refresh_token_days),
        user_agent=user_agent,
        ip_address=ip_address,
        fingerprint=fingerprint_hash,  # Store fingerprint hash
        remember_me=credentials.remember_me
    )
    db.add(session)
    
    # Update last login and clear failed attempts
    user.last_login = datetime.utcnow()
    user.failed_login_attempts = 0
    user.last_failed_login = None
    
    await db.commit()
    
    # Set auth cookies using our utility
    set_auth_cookies(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Set fingerprint cookie (not httponly, needs to be readable by JS)
    response.set_cookie(
        key="__Secure-Fgp",
        value=raw_fingerprint,
        max_age=refresh_token_days * 24 * 60 * 60,
        secure=settings.ENVIRONMENT == "production",
        samesite="strict" if settings.ENVIRONMENT == "production" else "lax",
        httponly=False
    )
    
    # Generate CSRF token for the session
    csrf_token = generate_csrf_token(response)
    
    # Return tokens (for backward compatibility, but cookies are primary)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        csrf_token=csrf_token  # Include CSRF token in response
    )


@router.post("/refresh", response_model=Token)
@rate_limit(requests_per_minute=30, burst_size=5)  # Higher limit for refresh as it's needed frequently
async def refresh_token(
    request: Request,
    response: Response,
    refresh_data: Optional[RefreshTokenRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    # Get refresh token from request body or cookie
    refresh_token = None
    if refresh_data and refresh_data.refresh_token:
        refresh_token = refresh_data.refresh_token
    else:
        refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise AuthenticationError("Refresh token not provided")
    
    # Verify refresh token
    payload = decode_token(refresh_token, token_type="refresh")
    if not payload:
        raise AuthenticationError("Invalid refresh token")
    
    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti and await token_blacklist_service.is_token_blacklisted(jti, db):
        raise AuthenticationError("Token has been revoked")
    
    # Find session
    result = await db.execute(
        select(Session).where(
            Session.refresh_token == refresh_token,
            Session.is_active == True,
            Session.expires_at > datetime.utcnow()
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise AuthenticationError("Invalid or expired refresh token")
    
    # Get user
    user = await db.get(User, session.user_id)
    if not user:
        raise NotFoundError("User", session.user_id)
    if not user.is_active:
        raise AppValidationError(
            message="User account is inactive",
            fields={"account": "This account has been disabled"}
        )
    
    # Create new tokens
    new_access_token = create_access_token(
        data={"user_id": str(user.id), "email": user.email, "role": user.role.value}
    )
    new_refresh_token = create_refresh_token(
        data={"user_id": str(user.id)}
    )
    
    # Update session with new refresh token
    session.refresh_token = new_refresh_token
    session.expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session.refreshed_at = datetime.utcnow()
    
    await db.commit()
    
    # Update cookies with new tokens
    set_auth_cookies(
        response=response,
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Logout current user."""
    # Get current token to blacklist it
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_token(token)
        if payload and "jti" in payload:
            # Blacklist the current access token
            await token_blacklist_service.blacklist_token(
                token=token,
                jti=payload["jti"],
                user_id=str(current_user.id),
                expires_at=datetime.fromtimestamp(payload["exp"]),
                reason="User logout",
                db=db
            )
    
    # Invalidate all user sessions
    result = await db.execute(
        select(Session).where(
            Session.user_id == current_user.id,
            Session.is_active == True
        )
    )
    sessions = result.scalars().all()
    
    for session in sessions:
        session.is_active = False
    
    await db.commit()
    
    # Clear all auth cookies
    clear_auth_cookies(response)
    response.delete_cookie(key="__Secure-Fgp")  # Also clear fingerprint
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """Get current user information."""
    return current_user


@router.get("/csrf-token")
async def get_csrf_token(response: Response):
    """Get a new CSRF token. This endpoint is used to obtain a CSRF token for forms."""
    csrf_token = generate_csrf_token(response)
    return {"csrf_token": csrf_token}


@router.post("/verify-email/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify user email with token."""
    result = await db.execute(
        select(User).where(
            User.email_verification_token == token,
            User.is_verified == False
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    user.is_verified = True
    user.email_verification_token = None
    user.verified_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Email verified successfully"}


@router.post("/password-reset/request")
@rate_limit(requests_per_minute=3, requests_per_hour=10)  # Very strict limit to prevent abuse
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset token."""
    result = await db.execute(
        select(User).where(User.email == reset_request.email)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Generate reset token
        user.password_reset_token = generate_verification_token()
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        await db.commit()
        
        # Send password reset email asynchronously
        asyncio.create_task(
            email_service.send_password_reset_email(
                to_email=user.email,
                user_name=user.full_name or user.email,
                reset_token=user.password_reset_token
            )
        )
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: Request,
    reset_confirm: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Reset password with token."""
    result = await db.execute(
        select(User).where(
            User.password_reset_token == reset_confirm.token,
            User.password_reset_expires > datetime.utcnow()
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    user.password_hash = get_password_hash(reset_confirm.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    
    # Invalidate all sessions
    result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.is_active == True
        )
    )
    sessions = result.scalars().all()
    
    for session in sessions:
        session.is_active = False
    
    await db.commit()
    
    # Send password changed notification
    asyncio.create_task(
        email_service.send_password_changed_email(
            to_email=user.email,
            user_name=user.full_name or user.email,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent")
        )
    )
    
    return {"message": "Password reset successfully"}


async def _track_failed_login(email: str, ip_address: Optional[str], db: AsyncSession):
    """Track failed login attempts for security."""
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    if user:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        user.last_failed_login = datetime.utcnow()
        await db.commit()


async def _is_account_locked(user_id: str, db: AsyncSession) -> bool:
    """Check if account is locked due to failed attempts."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return False
    
    # Lock account after 5 failed attempts for 30 minutes
    if user.failed_login_attempts and user.failed_login_attempts >= 5:
        if user.last_failed_login:
            lockout_duration = timedelta(minutes=30)
            if datetime.utcnow() - user.last_failed_login < lockout_duration:
                return True
            else:
                # Reset failed attempts after lockout period
                user.failed_login_attempts = 0
                user.last_failed_login = None
                await db.commit()
    
    return False