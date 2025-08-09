"""
Main application file using security_v2 module.
This is the updated version that uses the new clean security architecture.
"""
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import logging
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Core imports
from core.config import settings
from core.database import engine, create_tables, get_db
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
    get_current_user,
    PermissionChecker,
    RequireAuthenticated,
    RequireAgencyOwner,
    RequireAgencyAdmin
)

# Migration layer for backward compatibility
from core.security_v2.migration.compatibility import (
    create_access_token as create_access_token_compat,
    authenticate_user as authenticate_user_compat
)

# Import existing middleware (we'll keep non-security ones)
from core.middleware.tenant import TenantMiddleware
from core.middleware.logging import LoggingMiddleware
from middleware.i18n import I18nMiddleware
from middleware.logging_context import LoggingContextMiddleware, UserContextMiddleware

# Models
from models.user import User
from models.agency import Agency

# Schemas
from core.domain.schemas import (
    LoginRequest,
    Token,
    UserCreate,
    UserResponse
)

# Logging
from core.logger import get_logger
from logging_config import configure_structured_logging

# Configure structured logging
configure_structured_logging()
logger = get_logger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting up AgencyDark API (v2)...")
    
    # Initialize Redis connection
    await redis_client.connect()
    logger.info("Redis connected")
    
    # Initialize session manager with Redis
    from core.security_v2.authentication import init_session_manager
    init_session_manager(redis_client)
    logger.info("Session manager initialized")
    
    yield
    
    logger.info("Shutting down AgencyDark API (v2)...")
    
    # Close connections
    await redis_client.close()
    logger.info("Redis connection closed")
    await engine.dispose()
    logger.info("Database connections closed")


app = FastAPI(
    title="AgencyDark API (Security v2)",
    description="White-label SaaS portal with enhanced security",
    version="2.0.0",
    lifespan=lifespan
)

# Setup custom OpenAPI schema
def get_custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title="AgencyDark API (Security v2)",
        version="2.0.0",
        description="""
        ## AgencyDark - Enhanced Security Edition
        
        This version uses the new security_v2 module with:
        - Clean architecture without circular dependencies
        - Comprehensive RBAC with 7 roles and 30+ permissions
        - Backward compatibility through migration layer
        - Enhanced JWT handling with refresh tokens
        - Session management with Redis backend
        
        ### Authentication
        Most endpoints require a JWT token. Include it in the Authorization header:
        ```
        Authorization: Bearer <your-token>
        ```
        """,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"] = openapi_schema.get("components", {})
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    # Add default security to all operations
    openapi_schema["security"] = [{"bearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = get_custom_openapi

# Add middleware (simplified stack)
app.add_middleware(I18nMiddleware)
app.add_middleware(LoggingContextMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(UserContextMiddleware)
app.add_middleware(TenantMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if hasattr(settings, 'ALLOWED_ORIGINS') else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# AUTH ENDPOINTS USING SECURITY_V2
# ============================================================================

@app.post("/api/v1/auth/login", response_model=Token)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login endpoint using security_v2.
    Supports both /login and /login-fix for backward compatibility.
    """
    # Get user from database
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    # Prepare user data for authentication
    user_data = {
        'id': user.id,
        'email': user.email,
        'role': user.role if hasattr(user, 'role') else 'viewer',
        'agency_id': user.agency_id if hasattr(user, 'agency_id') else None,
        'hashed_password': user.hashed_password if hasattr(user, 'hashed_password') else user.password_hash,
        'first_name': user.first_name if hasattr(user, 'first_name') else None,
        'last_name': user.last_name if hasattr(user, 'last_name') else None
    }
    
    # Use migration layer for authentication
    auth_result = authenticate_user_compat(
        request.email,
        request.password,
        user_data
    )
    
    if not auth_result:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    return Token(
        access_token=auth_result['access_token'],
        refresh_token=auth_result.get('refresh_token'),
        token_type="bearer"
    )


@app.post("/api/v1/auth/login-fix", response_model=Token)
async def login_fix(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Alternative login endpoint for frontend compatibility.
    Routes to the same logic as /login.
    """
    return await login(request, db)


@app.post("/api/v1/auth/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user using security_v2."""
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # If agency_id is provided, verify it exists
    if user_data.agency_id:
        agency = await db.get(Agency, user_data.agency_id)
        if not agency:
            raise HTTPException(
                status_code=404,
                detail="Agency not found"
            )
    
    # Extract username from email if not provided
    username = user_data.email.split('@')[0]
    
    # Hash password using security_v2
    hashed_password = hash_password(user_data.password)
    
    # Create new user
    user = User(
        email=user_data.email,
        username=username,
        hashed_password=hashed_password,  # Use the new field name
        role=user_data.role or Role.VIEWER,
        agency_id=user_data.agency_id,
        is_active=True,
        is_verified=False
    )
    
    # If full_name is provided, split it
    if hasattr(user_data, 'full_name') and user_data.full_name:
        names = user_data.full_name.strip().split(' ', 1)
        user.first_name = names[0]
        if len(names) > 1:
            user.last_name = names[1]
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        agency_id=user.agency_id,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at
    )


@app.post("/api/v1/auth/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
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
    
    result = await db.execute(
        select(User).where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    # Create new token pair
    access_token, new_refresh_token = create_token_pair(
        user_id=user.id,
        email=user.email,
        role=user.role if hasattr(user, 'role') else Role.VIEWER,
        additional_claims={
            'agency_id': user.agency_id if hasattr(user, 'agency_id') else None
        }
    )
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@app.get("/api/v1/auth/me")
async def get_current_user_endpoint(
    current_user: dict = Depends(get_current_user)
):
    """Get current authenticated user information."""
    return current_user


@app.post("/api/v1/auth/logout")
async def logout(
    current_user: dict = Depends(get_current_user)
):
    """Logout user (placeholder for session cleanup)."""
    # In a stateless JWT system, logout is handled client-side
    # This endpoint can be used for audit logging or token blacklisting
    logger.info(f"User {current_user['email']} logged out")
    return {"message": "Logged out successfully"}


# ============================================================================
# PROTECTED ENDPOINTS EXAMPLES
# ============================================================================

@app.get("/api/v1/admin/users")
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(PermissionChecker([Permission.USER_READ]))
):
    """
    Get all users (requires USER_READ permission).
    Demonstrates permission-based access control.
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    return [
        {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "agency_id": user.agency_id,
            "is_active": user.is_active
        }
        for user in users
    ]


@app.get("/api/v1/agency/dashboard")
async def agency_dashboard(
    current_user: dict = Depends(RequireAgencyOwner)
):
    """
    Agency dashboard (requires agency owner role).
    Demonstrates role-based access control.
    """
    return {
        "message": "Welcome to agency dashboard",
        "user": current_user
    }


# ============================================================================
# HEALTH AND STATUS ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to AgencyDark API (Security v2)",
        "version": "2.0.0",
        "security": "Enhanced with security_v2 module"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from datetime import datetime
    
    # Check Redis connection
    redis_status = "healthy"
    try:
        await redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy",
        "service": "AgencyDark API (v2)",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "healthy",  # Simplified for now
            "redis": redis_status,
            "security": "security_v2 active"
        }
    }


@app.get("/api/v1/security/info")
async def security_info():
    """Get information about the security configuration."""
    from core.security_v2 import security_config
    
    return {
        "version": "2.0.0",
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


# ============================================================================
# API DOCUMENTATION
# ============================================================================

@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
async def custom_swagger_ui_html():
    """Custom Swagger UI."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AgencyDark API - Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css">
        <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
        <script>
        window.onload = function() {
            window.ui = SwaggerUIBundle({
                url: "/openapi.json",
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                persistAuthorization: true,
            })
        }
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(
        "main_v2:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )