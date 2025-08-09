"""
Example auth endpoints with enhanced validation.

This demonstrates how to use the comprehensive validation schemas
to ensure all inputs are properly validated and sanitized.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import verify_password, get_password_hash, create_access_token
from core.auth.cookie_utils import set_auth_cookies, clear_auth_cookies
from core.auth.csrf import generate_csrf_token
from core.config import settings
from core.logger import get_logger

# Import our enhanced validation schemas
from core.validation import (
    UserCreateSchema,
    UserUpdateSchema,
    PasswordChangeSchema,
    ValidationError
)
from core.validation.validators import validate_email, validate_password

from models.user import User, UserRole
from core.dependencies import CurrentUser

logger = get_logger(__name__)

router = APIRouter()


@router.post("/register/validated", response_model=dict)
async def register_with_validation(
    request: Request,
    response: Response,
    user_data: UserCreateSchema,  # Using our enhanced validation schema
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user with comprehensive input validation.
    
    This endpoint demonstrates:
    - Email validation with typo detection
    - Username validation with reserved word checking
    - Password strength validation
    - XSS prevention in user-provided fields
    - SQL injection prevention
    """
    try:
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if username already exists
        result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create new user with validated data
        user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            first_name=user_data.full_name.split(' ')[0] if user_data.full_name else None,
            last_name=' '.join(user_data.full_name.split(' ')[1:]) if user_data.full_name else None,
            phone=user_data.phone,
            role=UserRole.MEMBER,
            agency_id=user_data.agency_id,
            is_active=True,
            is_verified=False
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Create tokens
        access_token_data = {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = create_access_token(data=access_token_data)
        refresh_token = create_access_token(
            data={"user_id": str(user.id)},
            expires_delta=timedelta(days=30)
        )
        
        # Set auth cookies
        set_auth_cookies(
            response=response,
            access_token=access_token,
            refresh_token=refresh_token
        )
        
        # Generate CSRF token
        csrf_token = generate_csrf_token(response)
        
        logger.info(f"New user registered: {user.email} with username: {user.username}")
        
        return {
            "message": "Registration successful",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "full_name": user_data.full_name,
                "role": user.role.value
            },
            "csrf_token": csrf_token
        }
        
    except ValidationError as e:
        # Handle our custom validation errors
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Validation failed",
                "field": e.field,
                "error": e.message
            }
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.put("/profile/validated", response_model=dict)
async def update_profile_with_validation(
    update_data: UserUpdateSchema,  # Using enhanced validation
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile with validation.
    
    All fields are validated for:
    - XSS attempts
    - SQL injection
    - Format compliance
    """
    try:
        # Update only provided fields
        if update_data.email:
            # Check if new email is already taken
            result = await db.execute(
                select(User).where(
                    User.email == update_data.email,
                    User.id != current_user.id
                )
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            current_user.email = update_data.email
            current_user.is_verified = False  # Require re-verification
        
        if update_data.full_name is not None:
            names = update_data.full_name.split(' ', 1)
            current_user.first_name = names[0]
            current_user.last_name = names[1] if len(names) > 1 else None
        
        if update_data.phone is not None:
            current_user.phone = update_data.phone
        
        current_user.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(current_user)
        
        logger.info(f"Profile updated for user: {current_user.email}")
        
        return {
            "message": "Profile updated successfully",
            "user": {
                "id": str(current_user.id),
                "email": current_user.email,
                "username": current_user.username,
                "full_name": current_user.full_name,
                "phone": current_user.phone
            }
        }
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Validation failed",
                "field": e.field,
                "error": e.message
            }
        )


@router.post("/change-password/validated")
async def change_password_with_validation(
    password_data: PasswordChangeSchema,  # Using enhanced validation
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """
    Change password with comprehensive validation.
    
    Validates:
    - Current password is correct
    - New password meets complexity requirements
    - New password doesn't contain username/email
    - Passwords match
    """
    try:
        # Verify current password
        if not verify_password(password_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Additional validation: new password shouldn't be same as current
        if verify_password(password_data.new_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password"
            )
        
        # Update password
        current_user.password_hash = get_password_hash(password_data.new_password)
        current_user.updated_at = datetime.utcnow()
        
        # Invalidate all existing sessions for security
        # (In a real implementation, you would invalidate all refresh tokens)
        
        await db.commit()
        
        logger.info(f"Password changed for user: {current_user.email}")
        
        return {
            "message": "Password changed successfully"
        }
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Validation failed",
                "field": e.field,
                "error": e.message
            }
        )