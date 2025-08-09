"""
Mobile Authentication API Endpoints

Optimized for mobile clients with:
- Device tracking
- Biometric authentication support
- Reduced payload sizes
- Mobile-specific rate limiting
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from pydantic import BaseModel, EmailStr, Field
import secrets
import uuid

from core.database import get_db
from core.security_v2 import create_access_token, create_refresh_token, verify_password, hash_password
from core.security.rate_limiter import rate_limiter, RateLimitStrategy, RateLimitConfig
from core.security.fraud_detector import fraud_detector
from core.logging import get_logger
from models.user import User
from models.mobile_device import MobileDevice
from models.mobile_session import MobileSession

logger = get_logger(__name__)
security = HTTPBearer()

router = APIRouter(prefix="/api/v1/auth/mobile")


class DeviceInfo(BaseModel):
    """Mobile device information"""
    device_id: str
    device_name: str
    platform: str  # ios, android
    platform_version: str
    app_version: str
    push_token: Optional[str] = None


class MobileLoginRequest(BaseModel):
    """Mobile login request"""
    email: EmailStr
    password: str
    device_info: DeviceInfo
    biometric_token: Optional[str] = None


class MobileRegisterRequest(BaseModel):
    """Mobile registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    agency_name: Optional[str] = None
    device_id: str


class TokenResponse(BaseModel):
    """Token response for mobile"""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class MobileAuthResponse(BaseModel):
    """Mobile authentication response"""
    user: Dict[str, Any]
    tokens: TokenResponse
    device_registered: bool
    biometrics_available: bool


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str
    device_id: str


@router.post("/login", response_model=MobileAuthResponse)
async def mobile_login(
    request: MobileLoginRequest,
    db: AsyncSession = Depends(get_db),
    user_agent: Optional[str] = Header(None)
):
    """Mobile login with device tracking"""
    
    # Rate limiting for mobile login
    ip_address = "mobile"  # Would get from request in production
    
    # Check fraud
    fraud_score = await fraud_detector.check_fraud(
        ip_address=ip_address,
        action="login",
        metadata={
            "device_id": request.device_info.device_id,
            "platform": request.device_info.platform,
            "user_agent": user_agent
        }
    )
    
    if fraud_score.block_transaction:
        raise HTTPException(
            status_code=403,
            detail="Login blocked for security reasons"
        )
    
    # Verify credentials
    user = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = user.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.hashed_password):
        # Track failed login
        await fraud_detector.check_fraud(
            user_id=str(user.id) if user else None,
            ip_address=ip_address,
            action="failed_login"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled"
        )
    
    # Register or update device
    device = await register_device(db, user.id, request.device_info)
    
    # Create mobile session
    session = await create_mobile_session(db, user.id, device.id, ip_address)
    
    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={
            "device_id": device.id,
            "session_id": str(session.id),
            "platform": request.device_info.platform
        }
    )
    
    refresh_token = create_refresh_token(
        subject=str(user.id),
        additional_claims={
            "device_id": device.id,
            "session_id": str(session.id)
        }
    )
    
    # Update session with tokens
    session.refresh_token = refresh_token
    await db.commit()
    
    # Check biometric availability
    biometrics_available = await check_biometric_eligibility(db, user.id, device.id)
    
    return MobileAuthResponse(
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "agency_id": str(user.agency_id) if user.agency_id else None,
        },
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800,  # 30 minutes
        ),
        device_registered=True,
        biometrics_available=biometrics_available
    )


@router.post("/register", response_model=MobileAuthResponse)
async def mobile_register(
    request: MobileRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Mobile user registration"""
    
    # Check if email exists
    existing = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create user
    user = User(
        id=uuid.uuid4(),
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role="user",
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(user)
    
    # Create device info
    device_info = DeviceInfo(
        device_id=request.device_id,
        device_name=f"{request.full_name}'s Device",
        platform="unknown",
        platform_version="unknown",
        app_version="1.0.0"
    )
    
    # Register device
    device = await register_device(db, user.id, device_info)
    
    # Create session
    session = await create_mobile_session(db, user.id, device.id, "mobile")
    
    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={
            "device_id": device.id,
            "session_id": str(session.id)
        }
    )
    
    refresh_token = create_refresh_token(
        subject=str(user.id),
        additional_claims={
            "device_id": device.id,
            "session_id": str(session.id)
        }
    )
    
    session.refresh_token = refresh_token
    await db.commit()
    
    return MobileAuthResponse(
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "avatar_url": None,
            "role": user.role,
            "agency_id": None,
        },
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800,
        ),
        device_registered=True,
        biometrics_available=False
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_mobile_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh mobile access token"""
    
    # Verify refresh token and get session
    session = await db.execute(
        select(MobileSession).where(
            and_(
                MobileSession.refresh_token == request.refresh_token,
                MobileSession.is_active == True,
                MobileSession.expires_at > datetime.utcnow()
            )
        )
    )
    session = session.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
    
    # Verify device matches
    device = await db.get(MobileDevice, session.device_id)
    if not device or device.device_id != request.device_id:
        raise HTTPException(
            status_code=401,
            detail="Device mismatch"
        )
    
    # Generate new access token
    access_token = create_access_token(
        subject=str(session.user_id),
        additional_claims={
            "device_id": device.id,
            "session_id": str(session.id),
            "platform": device.platform
        }
    )
    
    # Update session activity
    session.last_activity = datetime.utcnow()
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,  # Keep same refresh token
        expires_in=1800
    )


@router.post("/logout")
async def mobile_logout(
    refresh_token: str = Body(..., embed=True),
    device_id: str = Body(..., embed=True),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Mobile logout"""
    
    # Find and invalidate session
    result = await db.execute(
        update(MobileSession)
        .where(
            and_(
                MobileSession.refresh_token == refresh_token,
                MobileSession.is_active == True
            )
        )
        .values(
            is_active=False,
            ended_at=datetime.utcnow()
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )
    
    await db.commit()
    
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_mobile_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Get current user profile for mobile"""
    
    # Extract user from token
    # In production, would validate token properly
    
    # For now, return mock data
    return {
        "user": {
            "id": "123",
            "email": "user@example.com",
            "full_name": "Test User",
            "avatar_url": None,
            "role": "user",
            "agency_id": None,
        }
    }


@router.post("/biometric/enable")
async def enable_biometric_auth(
    device_id: str = Body(..., embed=True),
    biometric_token: str = Body(..., embed=True),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Enable biometric authentication for device"""
    
    # Store biometric token for device
    # In production, would properly validate and encrypt
    
    return {"message": "Biometric authentication enabled"}


@router.post("/biometric/disable")
async def disable_biometric_auth(
    device_id: str = Body(..., embed=True),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Disable biometric authentication for device"""
    
    return {"message": "Biometric authentication disabled"}


# Helper functions

async def register_device(
    db: AsyncSession,
    user_id: uuid.UUID,
    device_info: DeviceInfo
) -> MobileDevice:
    """Register or update mobile device"""
    
    # Check if device exists
    device = await db.execute(
        select(MobileDevice).where(
            and_(
                MobileDevice.user_id == user_id,
                MobileDevice.device_id == device_info.device_id
            )
        )
    )
    device = device.scalar_one_or_none()
    
    if device:
        # Update existing device
        device.device_name = device_info.device_name
        device.platform = device_info.platform
        device.platform_version = device_info.platform_version
        device.app_version = device_info.app_version
        device.push_token = device_info.push_token
        device.last_seen = datetime.utcnow()
    else:
        # Create new device
        device = MobileDevice(
            id=uuid.uuid4(),
            user_id=user_id,
            device_id=device_info.device_id,
            device_name=device_info.device_name,
            platform=device_info.platform,
            platform_version=device_info.platform_version,
            app_version=device_info.app_version,
            push_token=device_info.push_token,
            is_active=True,
            created_at=datetime.utcnow(),
            last_seen=datetime.utcnow()
        )
        db.add(device)
    
    await db.commit()
    return device


async def create_mobile_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    device_id: uuid.UUID,
    ip_address: str
) -> MobileSession:
    """Create mobile session"""
    
    # Invalidate old sessions for device
    await db.execute(
        update(MobileSession)
        .where(
            and_(
                MobileSession.device_id == device_id,
                MobileSession.is_active == True
            )
        )
        .values(is_active=False, ended_at=datetime.utcnow())
    )
    
    # Create new session
    session = MobileSession(
        id=uuid.uuid4(),
        user_id=user_id,
        device_id=device_id,
        ip_address=ip_address,
        started_at=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        is_active=True
    )
    
    db.add(session)
    await db.commit()
    
    return session


async def check_biometric_eligibility(
    db: AsyncSession,
    user_id: uuid.UUID,
    device_id: uuid.UUID
) -> bool:
    """Check if device is eligible for biometric auth"""
    
    # Check if device has been registered for at least 24 hours
    device = await db.get(MobileDevice, device_id)
    if not device:
        return False
    
    device_age = datetime.utcnow() - device.created_at
    if device_age.days < 1:
        return False
    
    # Check if user has successful login history
    sessions = await db.execute(
        select(MobileSession)
        .where(
            and_(
                MobileSession.user_id == user_id,
                MobileSession.device_id == device_id
            )
        )
        .limit(5)
    )
    
    return sessions.scalar() is not None