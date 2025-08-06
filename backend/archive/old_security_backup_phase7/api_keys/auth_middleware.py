"""
API Key authentication middleware for FastAPI.
"""
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security.api_keys.key_manager import api_key_manager
from models.platform_api_key import PlatformAPIKey
from models.user import User
from core.logger import get_logger

logger = get_logger(__name__)


class APIKeyBearer(HTTPBearer):
    """Custom HTTPBearer for API key authentication."""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.scheme_name = "API Key"
    
    async def __call__(
        self, 
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> Optional[str]:
        """Extract API key from Authorization header or X-API-Key header."""
        # First try Authorization header
        credentials = await super().__call__(request)
        if credentials and credentials.scheme.lower() == "bearer":
            return credentials.credentials
        
        # Then try X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Finally try query parameter (for webhooks)
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key
        
        if self.auto_error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key required"
            )
        
        return None


# Create reusable security scheme
api_key_scheme = APIKeyBearer()


async def get_current_api_key(
    request: Request,
    api_key: str = Depends(api_key_scheme),
    db: AsyncSession = Depends(get_db)
) -> PlatformAPIKey:
    """
    Validate API key and return the key object.
    
    Args:
        request: FastAPI request object
        api_key: API key from header
        db: Database session
        
    Returns:
        Validated API key object
        
    Raises:
        HTTPException: If key is invalid
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key required"
        )
    
    # Extract request information
    client_ip = request.client.host if request.client else None
    origin = request.headers.get("Origin")
    user_agent = request.headers.get("User-Agent")
    
    # Validate the key
    validated_key = await api_key_manager.validate_api_key(
        db=db,
        api_key_string=api_key,
        ip_address=client_ip,
        origin=origin,
        user_agent=user_agent
    )
    
    if not validated_key:
        logger.warning(
            f"Invalid API key attempt from {client_ip} "
            f"with key prefix: {api_key[:8]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired API key"
        )
    
    # Check rate limits
    is_allowed, remaining = await api_key_manager.check_rate_limit(
        api_key=validated_key,
        db=db
    )
    
    if not is_allowed:
        logger.warning(
            f"Rate limit exceeded for API key {validated_key.key_prefix}... "
            f"from IP: {client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Remaining-Minute": str(remaining["minute"]),
                "X-RateLimit-Remaining-Hour": str(remaining["hour"]),
                "X-RateLimit-Remaining-Day": str(remaining["day"])
            }
        )
    
    # Add rate limit headers to response
    request.state.rate_limit_remaining = remaining
    
    # Store API key in request state for logging
    request.state.api_key = validated_key
    
    return validated_key


async def get_api_key_user(
    api_key: PlatformAPIKey = Depends(get_current_api_key),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get the user associated with an API key.
    
    Args:
        api_key: Validated API key
        db: Database session
        
    Returns:
        User object
    """
    # Load user from API key
    await db.refresh(api_key, ["user"])
    
    if not api_key.user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key user not found"
        )
    
    return api_key.user


def require_api_key_scope(required_scope: str):
    """
    Dependency to require a specific API key scope.
    
    Args:
        required_scope: The scope required for the endpoint
        
    Returns:
        Dependency function
    """
    async def verify_scope(
        request: Request,
        api_key: PlatformAPIKey = Depends(get_current_api_key)
    ) -> PlatformAPIKey:
        """Verify the API key has the required scope."""
        # Check if key has required scope
        from core.security.api_keys.key_generator import APIKeyScopeValidator
        
        validator = APIKeyScopeValidator()
        has_permission = validator.check_scope_permission(
            required_scope=required_scope,
            available_scopes=api_key.scopes
        )
        
        if not has_permission:
            logger.warning(
                f"API key {api_key.key_prefix}... lacks required scope: {required_scope}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required scope: {required_scope}"
            )
        
        # Store used scope for logging
        request.state.api_key_scope_used = required_scope
        
        return api_key
    
    return verify_scope


def require_any_api_key_scope(scopes: list):
    """
    Dependency to require any of the specified API key scopes.
    
    Args:
        scopes: List of scopes, any of which is sufficient
        
    Returns:
        Dependency function
    """
    async def verify_any_scope(
        request: Request,
        api_key: PlatformAPIKey = Depends(get_current_api_key)
    ) -> PlatformAPIKey:
        """Verify the API key has any of the required scopes."""
        # Check if key has any required scope
        from core.security.api_keys.key_generator import APIKeyScopeValidator
        
        validator = APIKeyScopeValidator()
        
        for scope in scopes:
            has_permission = validator.check_scope_permission(
                required_scope=scope,
                available_scopes=api_key.scopes
            )
            if has_permission:
                # Store used scope for logging
                request.state.api_key_scope_used = scope
                return api_key
        
        logger.warning(
            f"API key {api_key.key_prefix}... lacks any required scope: {scopes}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key lacks required scopes: {', '.join(scopes)}"
        )
    
    return verify_any_scope


def require_all_api_key_scopes(scopes: list):
    """
    Dependency to require all of the specified API key scopes.
    
    Args:
        scopes: List of scopes, all of which are required
        
    Returns:
        Dependency function
    """
    async def verify_all_scopes(
        request: Request,
        api_key: PlatformAPIKey = Depends(get_current_api_key)
    ) -> PlatformAPIKey:
        """Verify the API key has all required scopes."""
        # Check if key has all required scopes
        from core.security.api_keys.key_generator import APIKeyScopeValidator
        
        validator = APIKeyScopeValidator()
        missing_scopes = []
        
        for scope in scopes:
            has_permission = validator.check_scope_permission(
                required_scope=scope,
                available_scopes=api_key.scopes
            )
            if not has_permission:
                missing_scopes.append(scope)
        
        if missing_scopes:
            logger.warning(
                f"API key {api_key.key_prefix}... lacks required scopes: {missing_scopes}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required scopes: {', '.join(missing_scopes)}"
            )
        
        # Store used scopes for logging
        request.state.api_key_scopes_used = scopes
        
        return api_key
    
    return verify_all_scopes


class APIKeyPermissionChecker:
    """Check API key permissions for specific resources."""
    
    @staticmethod
    async def can_access_model(
        api_key: PlatformAPIKey,
        model_id: str
    ) -> bool:
        """Check if API key can access a specific model."""
        return api_key.can_access_model(model_id)
    
    @staticmethod
    async def can_access_conversation(
        api_key: PlatformAPIKey,
        conversation_id: str
    ) -> bool:
        """Check if API key can access a specific conversation."""
        return api_key.can_access_conversation(conversation_id)
    
    @staticmethod
    async def can_access_agency(
        api_key: PlatformAPIKey,
        agency_id: str
    ) -> bool:
        """Check if API key can access a specific agency."""
        # API keys are agency-scoped
        return str(api_key.agency_id) == str(agency_id)
    
    @staticmethod
    async def can_perform_action(
        api_key: PlatformAPIKey,
        action: str,
        resource: str
    ) -> bool:
        """
        Check if API key can perform a specific action on a resource.
        
        Args:
            api_key: The API key
            action: The action (read, write, admin)
            resource: The resource type
            
        Returns:
            True if allowed
        """
        required_scope = f"{action}:{resource}"
        
        from core.security.api_keys.key_generator import APIKeyScopeValidator
        validator = APIKeyScopeValidator()
        
        return validator.check_scope_permission(
            required_scope=required_scope,
            available_scopes=api_key.scopes
        )


# Middleware for automatic API key usage logging
async def log_api_key_usage(request: Request, call_next):
    """
    Middleware to log API key usage.
    
    This should be added to FastAPI app middleware stack.
    """
    start_time = datetime.utcnow()
    
    # Process request
    response = await call_next(request)
    
    # Calculate response time
    response_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    # Log if API key was used
    if hasattr(request.state, "api_key"):
        api_key = request.state.api_key
        
        # Get additional info
        scope_used = getattr(request.state, "api_key_scope_used", None)
        scopes_used = getattr(request.state, "api_key_scopes_used", None)
        
        if scopes_used:
            scope_used = ",".join(scopes_used)
        
        # Log usage asynchronously
        try:
            # Get database session
            async for db in get_db():
                await api_key_manager.log_usage(
                    db=db,
                    api_key=api_key,
                    endpoint=str(request.url.path),
                    method=request.method,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    request_size=request.headers.get("Content-Length"),
                    response_size=response.headers.get("Content-Length"),
                    scope_used=scope_used,
                    error_message=None if response.status_code < 400 else "Request failed",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    origin=request.headers.get("Origin")
                )
                break
        except Exception as e:
            logger.error(f"Failed to log API key usage: {e}")
    
    # Add rate limit headers if available
    if hasattr(request.state, "rate_limit_remaining"):
        remaining = request.state.rate_limit_remaining
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["minute"])
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["hour"])
        response.headers["X-RateLimit-Remaining-Day"] = str(remaining["day"])
    
    return response


# Convenience function for WebSocket authentication
async def validate_websocket_api_key(
    api_key: str,
    db: AsyncSession,
    client_ip: Optional[str] = None
) -> Optional[Tuple[PlatformAPIKey, User]]:
    """
    Validate API key for WebSocket connections.
    
    Args:
        api_key: The API key string
        db: Database session
        client_ip: Client IP address
        
    Returns:
        Tuple of (api_key, user) if valid, None otherwise
    """
    # Validate key
    validated_key = await api_key_manager.validate_api_key(
        db=db,
        api_key_string=api_key,
        required_scope="websocket:access",
        ip_address=client_ip
    )
    
    if not validated_key:
        return None
    
    # Check rate limits
    is_allowed, _ = await api_key_manager.check_rate_limit(
        api_key=validated_key,
        db=db
    )
    
    if not is_allowed:
        logger.warning(f"WebSocket rate limit exceeded for key {validated_key.key_prefix}...")
        return None
    
    # Load user
    await db.refresh(validated_key, ["user"])
    
    if not validated_key.user:
        return None
    
    return validated_key, validated_key.user