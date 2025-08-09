"""
Simplified main application using security_v2 with direct SQL queries.
This version bypasses ORM issues to demonstrate the security_v2 functionality.
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncpg
import logging
import uvicorn
from typing import Optional, Dict, Any

# Core imports
from core.redis import redis_client

# New security_v2 imports
from core.security_v2 import (
    # Authentication
    hash_password,
    verify_password,
    create_token_pair,
    verify_token,
    jwt_handler,
    
    # Authorization
    Role,
    Permission,
    PermissionChecker,
    RequireAuthenticated
)

# Schemas
from pydantic import BaseModel, EmailStr

# Logging
from core.logger import get_logger
from logging_config import configure_structured_logging

# Configure structured logging
configure_structured_logging()
logger = get_logger(__name__)

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None

# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "viewer"
    agency_id: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global db_pool
    
    logger.info("Starting up AgencyDark API (v2 Simple)...")
    
    # Create database connection pool
    db_pool = await asyncpg.create_pool(
        host="localhost",
        database="agencydark_dev",
        user="mariuszbudzisz",
        min_size=1,
        max_size=10
    )
    logger.info("Database pool created")
    
    # Initialize Redis connection
    await redis_client.connect()
    logger.info("Redis connected")
    
    # Initialize session manager with Redis
    from core.security_v2.authentication import init_session_manager
    init_session_manager(redis_client)
    logger.info("Session manager initialized")
    
    yield
    
    logger.info("Shutting down AgencyDark API (v2 Simple)...")
    
    # Close connections
    await db_pool.close()
    logger.info("Database pool closed")
    
    await redis_client.disconnect()
    logger.info("Redis disconnected")


app = FastAPI(
    title="AgencyDark API (Security v2 Simple)",
    description="Simplified version with direct SQL queries",
    version="2.0.1",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# DATABASE HELPERS
# ============================================================================

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email using direct SQL."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, email, hashed_password, role, agency_id
            FROM users 
            WHERE email = $1
            """,
            email
        )
        
        if row:
            return dict(row)
        return None


async def create_user(email: str, hashed_password: str, role: str = "viewer", agency_id: Optional[int] = None) -> Dict[str, Any]:
    """Create a new user."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, hashed_password, role, agency_id, is_active, is_verified)
            VALUES ($1, $2, $3, $4, true, false)
            RETURNING id, email, role, agency_id, is_active, is_verified
            """,
            email, hashed_password, role, agency_id
        )
        return dict(row)


async def get_all_users() -> list:
    """Get all users."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, email, role, agency_id
            FROM users
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/api/v1/auth/login", response_model=Token)
async def login(request: LoginRequest):
    """Login endpoint using security_v2."""
    # Get user from database
    user = await get_user_by_email(request.email)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    # Verify password using security_v2
    if not verify_password(request.password, user['hashed_password']):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    # Create tokens using security_v2
    access_token, refresh_token = create_token_pair(
        user_id=user['id'],
        email=user['email'],
        role=user.get('role', 'viewer'),
        additional_claims={
            'agency_id': user.get('agency_id')
        }
    )
    
    logger.info(f"User {user['email']} logged in successfully")
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@app.post("/api/v1/auth/login-fix", response_model=Token)
async def login_fix(request: LoginRequest):
    """Alternative login endpoint for frontend compatibility."""
    return await login(request)


@app.post("/api/v1/auth/register")
async def register(user_data: UserCreate):
    """Register a new user using security_v2."""
    # Check if email already exists
    existing_user = await get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Hash password using security_v2
    hashed_password = hash_password(user_data.password)
    
    # Create new user
    user = await create_user(
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role or Role.VIEWER,
        agency_id=user_data.agency_id
    )
    
    logger.info(f"New user registered: {user['email']}")
    
    return {
        "id": user['id'],
        "email": user['email'],
        "role": user['role'],
        "agency_id": user['agency_id'],
        "message": "User registered successfully"
    }


@app.get("/api/v1/auth/me")
async def get_current_user_endpoint(
    authorization: str = Depends(lambda request: request.headers.get("Authorization"))
):
    """Get current authenticated user information."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    
    # Verify token using security_v2
    payload = verify_token(token, "access")
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    return {
        "user_id": int(payload.get("sub")) if payload.get("sub") else None,
        "email": payload.get("email"),
        "role": payload.get("role"),
        "agency_id": payload.get("agency_id")
    }


@app.post("/api/v1/auth/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )
    
    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )
    
    # Get user details
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, role, agency_id FROM users WHERE id = $1",
            int(user_id)
        )
        
        if not row:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        user = dict(row)
    
    # Create new token pair
    access_token, new_refresh_token = create_token_pair(
        user_id=user['id'],
        email=user['email'],
        role=user.get('role', Role.VIEWER),
        additional_claims={
            'agency_id': user.get('agency_id')
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


# ============================================================================
# PROTECTED ENDPOINTS
# ============================================================================

@app.get("/api/v1/admin/users")
async def get_all_users_endpoint(
    authorization: str = Depends(lambda request: request.headers.get("Authorization"))
):
    """
    Get all users (protected endpoint).
    Demonstrates authorization checking.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    payload = verify_token(token, "access")
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    # Check if user has permission (simplified check)
    user_role = payload.get("role", "viewer")
    if user_role not in [Role.SUPER_ADMIN, Role.AGENCY_OWNER, Role.AGENCY_ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )
    
    users = await get_all_users()
    return users


# ============================================================================
# HEALTH AND STATUS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to AgencyDark API (Security v2 Simple)",
        "version": "2.0.1",
        "security": "Enhanced with security_v2 module",
        "database": "Direct SQL queries (no ORM)"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from datetime import datetime
    
    # Check database
    db_status = "healthy"
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check Redis
    redis_status = "healthy"
    try:
        await redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        "service": "AgencyDark API (v2 Simple)",
        "version": "2.0.1",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": db_status,
            "redis": redis_status,
            "security": "security_v2 active"
        }
    }


@app.get("/api/v1/security/info")
async def security_info():
    """Get information about the security configuration."""
    from core.security_v2 import security_config
    
    return {
        "version": "2.0.1",
        "mode": "simplified (no ORM)",
        "features": {
            "rbac": security_config.ENABLE_RBAC,
            "rate_limiting": security_config.ENABLE_RATE_LIMITING,
            "audit_logging": security_config.ENABLE_AUDIT_LOGGING,
            "api_keys": security_config.ENABLE_API_KEYS,
            "mfa": security_config.ENABLE_MFA,
            "sessions": security_config.ENABLE_SESSION_MANAGEMENT
        },
        "jwt": {
            "algorithm": security_config.JWT_ALGORITHM,
            "access_token_expire_minutes": security_config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_expire_days": security_config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        },
        "password_policy": {
            "min_length": security_config.PASSWORD_MIN_LENGTH,
            "require_uppercase": security_config.PASSWORD_REQUIRE_UPPERCASE,
            "require_lowercase": security_config.PASSWORD_REQUIRE_LOWERCASE,
            "require_numbers": security_config.PASSWORD_REQUIRE_NUMBERS,
            "require_special": security_config.PASSWORD_REQUIRE_SPECIAL
        }
    }


@app.get("/api/v1/test/roles")
async def test_roles():
    """Test endpoint to show available roles."""
    from core.security_v2.authorization import Role
    
    return {
        "roles": [
            {"name": Role.SUPER_ADMIN, "description": "Full system access"},
            {"name": Role.AGENCY_OWNER, "description": "Agency owner with full control"},
            {"name": Role.AGENCY_ADMIN, "description": "Agency administrator"},
            {"name": Role.AGENCY_USER, "description": "Basic agency staff"},
            {"name": Role.MODEL, "description": "Agency model"},
            {"name": Role.CLIENT, "description": "External client"},
            {"name": Role.VIEWER, "description": "Read-only access"}
        ]
    }


@app.get("/api/v1/test/permissions")
async def test_permissions():
    """Test endpoint to show permission system."""
    from core.security_v2.authorization import Permission, rbac_manager
    
    # Get permissions for different roles
    return {
        "permission_count": len(Permission),
        "role_permissions": {
            "agency_owner": len(rbac_manager.get_role_permissions(Role.AGENCY_OWNER)),
            "agency_admin": len(rbac_manager.get_role_permissions(Role.AGENCY_ADMIN)),
            "agency_user": len(rbac_manager.get_role_permissions(Role.AGENCY_USER)),
            "model": len(rbac_manager.get_role_permissions(Role.MODEL)),
            "viewer": len(rbac_manager.get_role_permissions(Role.VIEWER))
        }
    }


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(
        "main_v2_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )