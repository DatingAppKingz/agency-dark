"""
API Key authentication middleware.
"""
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any

from core.application.api_key_service import APIKeyService
from core.database import AsyncSessionLocal


class APIKeyAuth(HTTPBearer):
    """API Key authentication using Bearer token or custom headers."""
    
    def __init__(self, required_scopes: Optional[list] = None, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.required_scopes = required_scopes or []
    
    async def __call__(self, request: Request) -> Optional[Dict[str, Any]]:
        # Try to get API key from different sources
        api_key = None
        api_secret = None
        
        # 1. Check Authorization header (Bearer token)
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
            if ":" in token:
                api_key, api_secret = token.split(":", 1)
        
        # 2. Check custom headers
        if not api_key:
            api_key = request.headers.get("X-API-Key")
            api_secret = request.headers.get("X-API-Secret")
        
        # 3. Check query parameters (for webhooks/callbacks)
        if not api_key and request.query_params:
            api_key = request.query_params.get("api_key")
            api_secret = request.query_params.get("api_secret")
        
        if not api_key or not api_secret:
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Missing API credentials",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return None
        
        # Get client IP
        client_ip = None
        if request.client:
            client_ip = request.client.host
        
        # Validate the API key
        async with AsyncSessionLocal() as db:
            api_key_record = await APIKeyService.validate_api_key(
                db=db,
                api_key=api_key,
                api_secret=api_secret,
                required_scopes=self.required_scopes,
                ip_address=client_ip
            )
        
        if not api_key_record:
            if self.auto_error:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API credentials",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return None
        
        # Log the API request in audit log
        from core.domain.api_key_models import APIKeyAuditLog
        async with AsyncSessionLocal() as db:
            audit_log = APIKeyAuditLog(
                api_key_id=api_key_record.id,
                action="api_request",
                ip_address=client_ip,
                user_agent=request.headers.get("User-Agent"),
                request_path=str(request.url.path),
                request_method=request.method,
                metadata={
                    "query_params": dict(request.query_params),
                    "scopes_used": self.required_scopes
                }
            )
            db.add(audit_log)
            await db.commit()
        
        # Return API key info
        return {
            "api_key_id": str(api_key_record.id),
            "agency_id": str(api_key_record.agency_id),
            "user_id": str(api_key_record.user_id),
            "scopes": api_key_record.scopes,
            "api_key_name": api_key_record.name
        }


def require_api_key(scopes: Optional[list] = None):
    """
    Dependency to require API key authentication with optional scopes.
    
    Usage:
        @router.get("/protected")
        async def protected_endpoint(
            api_key_info: dict = Depends(require_api_key(["read:analytics"]))
        ):
            return {"agency_id": api_key_info["agency_id"]}
    """
    return APIKeyAuth(required_scopes=scopes)


class APIKeyOrJWTAuth:
    """
    Allow either API key or JWT authentication.
    
    Tries API key first, falls back to JWT if not provided.
    """
    
    def __init__(self, required_scopes: Optional[list] = None):
        self.api_key_auth = APIKeyAuth(required_scopes=required_scopes, auto_error=False)
        self.required_scopes = required_scopes or []
    
    async def __call__(self, request: Request) -> Dict[str, Any]:
        # Try API key authentication first
        api_key_info = await self.api_key_auth(request)
        if api_key_info:
            return {
                "auth_type": "api_key",
                **api_key_info
            }
        
        # Fall back to JWT authentication
        from core.dependencies import get_current_user_optional
        user = await get_current_user_optional(request)
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Check scopes for JWT auth (if needed)
        # For now, we'll assume JWT users have all scopes for their role
        
        return {
            "auth_type": "jwt",
            "user_id": str(user.id),
            "agency_id": str(user.agency_id),
            "user_role": user.role,
            "scopes": []  # Could map user roles to scopes
        }


def require_api_key_or_jwt(scopes: Optional[list] = None):
    """
    Dependency to allow either API key or JWT authentication.
    
    Usage:
        @router.get("/data")
        async def get_data(
            auth_info: dict = Depends(require_api_key_or_jwt(["read:data"]))
        ):
            if auth_info["auth_type"] == "api_key":
                # Handle API key access
            else:
                # Handle JWT access
    """
    return APIKeyOrJWTAuth(required_scopes=scopes)