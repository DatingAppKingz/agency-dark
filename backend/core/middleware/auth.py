from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import status
from fastapi.responses import JSONResponse
from jose import JWTError
import logging

from core.security import decode_token
from core.database import get_db_sync
from core.domain.models import User

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to extract user from JWT token and set on request state."""
    
    async def dispatch(self, request: Request, call_next):
        # Paths that don't require authentication
        excluded_paths = [
            "/", "/health", "/api/docs", "/api/redoc", "/openapi.json",
            "/api/v1/auth/login", "/api/v1/auth/register", 
            "/api/v1/auth/refresh", "/api/v1/auth/password-reset/request",
            "/api/v1/auth/password-reset/confirm"
        ]
        
        # Check if path is excluded or is a verification endpoint
        if (request.url.path in excluded_paths or 
            request.url.path.startswith("/api/v1/auth/verify-email/")):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Continue without user for optional auth endpoints
            return await call_next(request)
        
        token = auth_header.split(" ")[1]
        
        try:
            # Verify token and extract user data
            payload = decode_token(token)
            if payload:
                request.state.user_id = payload.get("user_id")
                request.state.user_email = payload.get("email")
                request.state.user_role = payload.get("role")
                
                # For tenant isolation
                with get_db_sync() as db:
                    user = db.query(User).filter(User.id == payload.get("user_id")).first()
                    if user and user.agency_id:
                        request.state.tenant_id = str(user.agency_id)
                
                logger.debug(f"Authenticated user: {request.state.user_email}")
        except JWTError as e:
            logger.warning(f"JWT validation error: {e}")
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
        
        response = await call_next(request)
        return response