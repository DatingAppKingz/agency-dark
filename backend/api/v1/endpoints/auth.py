from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    generate_verification_token
)
from backend.core.config import settings
from backend.core.domain.models import User, Session, Agency, UserRole
from backend.core.domain.schemas import (
    LoginRequest,
    Token,
    TokenData,
    UserCreate,
    UserResponse,
    PasswordResetRequest,
    PasswordResetConfirm,
    RefreshTokenRequest
)
from backend.core.dependencies import CurrentUser, CurrentUserOptional


router = APIRouter()
security = HTTPBearer()


@router.post("/register", response_model=UserResponse)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # If agency_id is provided, verify it exists
    if user_data.agency_id:
        agency = await db.get(Agency, user_data.agency_id)
        if not agency:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agency not found"
            )
    
    # Create new user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role or UserRole.AGENCY_MEMBER,
        agency_id=user_data.agency_id,
        is_active=True,  # For MVP, activate immediately
        is_verified=False
    )
    
    # Generate email verification token
    user.email_verification_token = generate_verification_token()
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # TODO: Send verification email
    
    return user


@router.post("/login", response_model=Token)
async def login(
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
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create tokens
    access_token = create_access_token(
        data={"user_id": str(user.id), "email": user.email, "role": user.role.value}
    )
    refresh_token = create_refresh_token(
        data={"user_id": str(user.id)}
    )
    
    # Store refresh token in database
    session = Session(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=credentials.user_agent,
        ip_address=credentials.ip_address
    )
    db.add(session)
    
    # Update last login
    user.last_login = datetime.utcnow()
    
    await db.commit()
    
    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax"
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=Token)
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided"
        )
    
    # Verify refresh token
    payload = verify_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Get user
    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or inactive"
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
    
    # Update cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax"
    )
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Logout current user."""
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
    
    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token")
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """Get current user information."""
    return current_user


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
        
        # TODO: Send password reset email
    
    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset/confirm")
async def confirm_password_reset(
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
    user.hashed_password = get_password_hash(reset_confirm.new_password)
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
    
    return {"message": "Password reset successfully"}