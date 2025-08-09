"""
Minimal authentication endpoint that bypasses SQLAlchemy issues.
Temporary solution for manual testing.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
import asyncpg
from passlib.context import CryptContext
import jwt
import uuid

from core.config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

@router.post("/login-minimal", response_model=Token)
async def login_minimal(credentials: LoginRequest):
    """Minimal login endpoint for testing."""
    # Connect directly to database
    conn = await asyncpg.connect(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    
    try:
        # Get user from database
        user = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.full_name, u.hashed_password, u.role, 
                   u.is_active, u.is_verified, u.agency_id,
                   a.name as agency_name, a.slug as agency_slug
            FROM users u
            LEFT JOIN agencies a ON u.agency_id = a.id
            WHERE u.email = $1
            """,
            credentials.email
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Verify password
        if not pwd_context.verify(credentials.password, user['hashed_password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user['is_active']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user['id']), "email": user['email'], "role": user['role']}
        )
        
        # Return token and user info
        return Token(
            access_token=access_token,
            user={
                "id": str(user['id']),
                "email": user['email'],
                "full_name": user['full_name'],
                "role": user['role'],
                "agency_id": str(user['agency_id']) if user['agency_id'] else None,
                "agency_name": user['agency_name'],
                "agency_slug": user['agency_slug'],
                "is_active": user['is_active'],
                "is_verified": user['is_verified']
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
    finally:
        await conn.close()

@router.get("/me-minimal")
async def get_current_user_minimal(authorization: str = None):
    """Get current user from token - minimal version."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user from database
        conn = await asyncpg.connect(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            user = await conn.fetchrow(
                """
                SELECT u.id, u.email, u.full_name, u.role, 
                       u.is_active, u.is_verified, u.agency_id,
                       a.name as agency_name, a.slug as agency_slug
                FROM users u
                LEFT JOIN agencies a ON u.agency_id = a.id
                WHERE u.id = $1
                """,
                uuid.UUID(user_id)
            )
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return {
                "id": str(user['id']),
                "email": user['email'],
                "full_name": user['full_name'],
                "role": user['role'],
                "agency_id": str(user['agency_id']) if user['agency_id'] else None,
                "agency_name": user['agency_name'],
                "agency_slug": user['agency_slug'],
                "is_active": user['is_active'],
                "is_verified": user['is_verified']
            }
            
        finally:
            await conn.close()
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )