"""Temporary auth fix for column name mismatch."""
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from datetime import datetime, timedelta
import jwt
from pydantic import BaseModel

from core.database import get_db
from core.config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a JWT token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

@router.post("/login-fix", response_model=Token)
async def login_fix(
    response: Response,
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Fixed login endpoint using correct column names."""
    # Find user by email using raw SQL
    result = await db.execute(text("""
        SELECT id, email, hashed_password, full_name, role, is_active, is_verified, agency_id
        FROM users 
        WHERE email = :email
    """), {"email": credentials.email})
    
    user = result.fetchone()
    
    if not user:
        return {"error": "Invalid credentials"}, 401
    
    # Verify password
    if not pwd_context.verify(credentials.password, user.hashed_password):
        return {"error": "Invalid credentials"}, 401
    
    if not user.is_active:
        return {"error": "Account is disabled"}, 403
    
    # Create token
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "agency_id": str(user.agency_id) if user.agency_id else None
        },
        expires_delta=access_token_expires
    )
    
    # Set cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False  # Set to True in production with HTTPS
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current user info from token in cookie."""
    # Get token from cookie
    token = request.cookies.get("access_token")
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Decode token
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get user from database
    result = await db.execute(text("""
        SELECT id, email, full_name, role, is_active, is_verified, agency_id, created_at, updated_at
        FROM users 
        WHERE id = :user_id
    """), {"user_id": user_id})
    
    user = result.fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "first_name": user.full_name.split()[0] if user.full_name else "",
        "last_name": " ".join(user.full_name.split()[1:]) if user.full_name and len(user.full_name.split()) > 1 else "",
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "agency_id": str(user.agency_id) if user.agency_id else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None
    }