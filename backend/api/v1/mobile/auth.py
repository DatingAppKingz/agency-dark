"""
Mobile authentication endpoints with device management
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import secrets

from core.database import get_db
from core.security import create_access_token, get_password_hash, verify_password
from core.auth.dependencies import get_current_user
from core.auth.session_manager import SessionManager
from core.auth.device_detector import DeviceDetector
from modules.users.domain.models import User
from modules.users.infrastructure.repositories import UserRepository

router = APIRouter(prefix="/mobile/auth", tags=["mobile-auth"])

session_manager = SessionManager()
device_detector = DeviceDetector()


class MobileLoginRequest(BaseModel):
    """Mobile login request"""
    email: str
    password: str
    device_id: str = Field(..., description="Unique device identifier")
    device_name: Optional[str] = Field(None, description="Device name (e.g., iPhone 12)")
    device_type: str = Field(..., description="Device type (ios/android)")
    push_token: Optional[str] = Field(None, description="Push notification token")
    biometric_enabled: bool = Field(False, description="Whether biometric auth is enabled")


class MobileLoginResponse(BaseModel):
    """Mobile login response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict
    device_registered: bool
    biometric_token: Optional[str] = None


class DeviceRegistrationRequest(BaseModel):
    """Device registration request"""
    device_id: str
    device_name: Optional[str]
    device_type: str
    push_token: Optional[str]
    device_model: Optional[str]
    os_version: Optional[str]


class BiometricAuthRequest(BaseModel):
    """Biometric authentication request"""
    device_id: str
    biometric_token: str


@router.post("/login", response_model=MobileLoginResponse)
async def mobile_login(
    request: Request,
    login_data: MobileLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Mobile login with device registration
    """
    # Verify credentials
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(login_data.email)
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is not active")
    
    # Detect device info
    user_agent = request.headers.get("user-agent", "")
    device_info = device_detector.detect(user_agent)
    
    # Create session with device info
    session_data = {
        "user_id": str(user.id),
        "device_id": login_data.device_id,
        "device_name": login_data.device_name or device_info.get("device", "Unknown"),
        "device_type": login_data.device_type,
        "device_model": device_info.get("model"),
        "os_version": device_info.get("os_version"),
        "app_version": request.headers.get("x-app-version"),
        "ip_address": request.client.host,
        "push_token": login_data.push_token
    }
    
    session = await session_manager.create_session(
        user_id=user.id,
        device_fingerprint=login_data.device_id,
        session_data=session_data
    )
    
    # Create tokens
    access_token_expires = timedelta(minutes=60)  # Shorter for mobile
    refresh_token_expires = timedelta(days=30)
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "session_id": session.id,
            "device_id": login_data.device_id
        },
        expires_delta=access_token_expires
    )
    
    refresh_token = create_access_token(
        data={
            "sub": str(user.id),
            "session_id": session.id,
            "type": "refresh"
        },
        expires_delta=refresh_token_expires
    )
    
    # Generate biometric token if requested
    biometric_token = None
    if login_data.biometric_enabled:
        biometric_token = secrets.token_urlsafe(32)
        await session_manager.store_biometric_token(
            user_id=user.id,
            device_id=login_data.device_id,
            token=biometric_token
        )
    
    # Register/update device
    device_registered = await _register_device(
        db,
        user.id,
        login_data.device_id,
        login_data.device_name,
        login_data.device_type,
        login_data.push_token
    )
    
    return MobileLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_token_expires.total_seconds()),
        user={
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "agency_id": str(user.agency_id) if user.agency_id else None
        },
        device_registered=device_registered,
        biometric_token=biometric_token
    )


@router.post("/biometric", response_model=MobileLoginResponse)
async def biometric_login(
    request: Request,
    auth_data: BiometricAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login using biometric authentication
    """
    # Verify biometric token
    user_id = await session_manager.verify_biometric_token(
        device_id=auth_data.device_id,
        token=auth_data.biometric_token
    )
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid biometric token")
    
    # Get user
    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)
    
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is not active")
    
    # Create new session
    session = await session_manager.create_session(
        user_id=user.id,
        device_fingerprint=auth_data.device_id,
        session_data={
            "device_id": auth_data.device_id,
            "auth_method": "biometric"
        }
    )
    
    # Create tokens
    access_token_expires = timedelta(minutes=60)
    refresh_token_expires = timedelta(days=30)
    
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "session_id": session.id,
            "device_id": auth_data.device_id
        },
        expires_delta=access_token_expires
    )
    
    refresh_token = create_access_token(
        data={
            "sub": str(user.id),
            "session_id": session.id,
            "type": "refresh"
        },
        expires_delta=refresh_token_expires
    )
    
    return MobileLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_token_expires.total_seconds()),
        user={
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "agency_id": str(user.agency_id) if user.agency_id else None
        },
        device_registered=True,
        biometric_token=auth_data.biometric_token
    )


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token
    """
    # Decode refresh token
    from core.security import decode_token
    
    try:
        payload = decode_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get("sub")
        session_id = payload.get("session_id")
        
        # Verify session is still valid
        session = await session_manager.get_session(session_id)
        if not session or session.user_id != user_id:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Create new access token
        access_token_expires = timedelta(minutes=60)
        
        new_access_token = create_access_token(
            data={
                "sub": user_id,
                "session_id": session_id,
                "device_id": session.device_fingerprint
            },
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds())
        }
        
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/logout")
async def mobile_logout(
    device_id: str = Header(..., alias="X-Device-ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Logout from mobile device
    """
    # Revoke all sessions for this device
    await session_manager.revoke_device_sessions(
        user_id=current_user.id,
        device_id=device_id
    )
    
    # Remove biometric token
    await session_manager.remove_biometric_token(
        user_id=current_user.id,
        device_id=device_id
    )
    
    return {"message": "Logged out successfully"}


@router.post("/devices/register")
async def register_device(
    device_data: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Register or update device information
    """
    registered = await _register_device(
        db,
        current_user.id,
        device_data.device_id,
        device_data.device_name,
        device_data.device_type,
        device_data.push_token,
        device_data.device_model,
        device_data.os_version
    )
    
    return {
        "device_registered": registered,
        "device_id": device_data.device_id
    }


@router.get("/devices")
async def get_devices(
    current_user: User = Depends(get_current_user)
):
    """
    Get all registered devices for user
    """
    devices = await session_manager.get_user_devices(current_user.id)
    
    return {
        "devices": [
            {
                "device_id": device["device_id"],
                "device_name": device["device_name"],
                "device_type": device["device_type"],
                "last_active": device["last_active"],
                "push_enabled": bool(device.get("push_token"))
            }
            for device in devices
        ]
    }


@router.delete("/devices/{device_id}")
async def remove_device(
    device_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Remove a registered device
    """
    # Revoke sessions for device
    await session_manager.revoke_device_sessions(
        user_id=current_user.id,
        device_id=device_id
    )
    
    # Remove device registration
    # This would be implemented in your device management system
    
    return {"message": "Device removed successfully"}


async def _register_device(
    db: AsyncSession,
    user_id: str,
    device_id: str,
    device_name: Optional[str],
    device_type: str,
    push_token: Optional[str],
    device_model: Optional[str] = None,
    os_version: Optional[str] = None
) -> bool:
    """
    Register or update device in database
    """
    # This would be implemented with a proper Device model
    # For now, we'll store in session data
    
    device_data = {
        "device_id": device_id,
        "device_name": device_name,
        "device_type": device_type,
        "push_token": push_token,
        "device_model": device_model,
        "os_version": os_version,
        "registered_at": datetime.utcnow().isoformat()
    }
    
    # Store in session manager (simplified)
    await session_manager.update_device_info(user_id, device_id, device_data)
    
    return True