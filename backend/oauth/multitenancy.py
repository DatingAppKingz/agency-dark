"""
Multi-tenant support for OAuth2 implementation.
Provides agency-level isolation and cross-agency access control.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
from fastapi import Request, HTTPException, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from oauth.models import OAuthClient, OAuthToken
from oauth.config import oauth_config
from models.user import User
from models.agency import Agency
from core.database import get_db

logger = logging.getLogger(__name__)


class AgencyContext:
    """
    Manages agency context for multi-tenant operations.
    """
    
    def __init__(self, agency_id: str, agency_name: Optional[str] = None):
        self.agency_id = agency_id
        self.agency_name = agency_name
        self.subdomain = None
        self.custom_domain = None
        self.settings = {}
    
    @classmethod
    async def from_request(cls, request: Request, db: AsyncSession) -> Optional['AgencyContext']:
        """
        Extract agency context from request.
        Tries multiple methods: subdomain, header, token claim.
        """
        agency_id = None
        
        # Method 1: Extract from subdomain
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain and subdomain != "www":
                # Look up agency by subdomain
                result = await db.execute(
                    select(Agency).where(Agency.subdomain == subdomain)
                )
                agency = result.scalar_one_or_none()
                if agency:
                    context = cls(str(agency.id), agency.name)
                    context.subdomain = subdomain
                    return context
        
        # Method 2: Extract from custom header
        agency_header = request.headers.get("X-Agency-ID")
        if agency_header:
            result = await db.execute(
                select(Agency).where(Agency.id == agency_header)
            )
            agency = result.scalar_one_or_none()
            if agency:
                return cls(str(agency.id), agency.name)
        
        # Method 3: Extract from OAuth token
        if hasattr(request.state, "oauth_token"):
            token = request.state.oauth_token
            if token and hasattr(token, "agency_id"):
                result = await db.execute(
                    select(Agency).where(Agency.id == token.agency_id)
                )
                agency = result.scalar_one_or_none()
                if agency:
                    return cls(str(agency.id), agency.name)
        
        # Method 4: Extract from JWT claim (compatibility)
        if hasattr(request.state, "user"):
            user = request.state.user
            if hasattr(user, "agency_id"):
                result = await db.execute(
                    select(Agency).where(Agency.id == user.agency_id)
                )
                agency = result.scalar_one_or_none()
                if agency:
                    return cls(str(agency.id), agency.name)
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agency context to dictionary."""
        return {
            "agency_id": self.agency_id,
            "agency_name": self.agency_name,
            "subdomain": self.subdomain,
            "custom_domain": self.custom_domain,
            "settings": self.settings
        }


class AgencyIsolation:
    """
    Enforces agency-level isolation for OAuth operations.
    """
    
    @staticmethod
    async def validate_client_agency_access(
        client: OAuthClient,
        agency_id: str,
        operation: str = "access"
    ) -> bool:
        """
        Validate if a client has access to an agency.
        
        Args:
            client: OAuth client
            agency_id: Target agency ID
            operation: Type of operation (access, read, write, admin)
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Check if client belongs to the agency
        if str(client.agency_id) == str(agency_id):
            return True
        
        # Check cross-agency access if enabled
        if not oauth_config.ENABLE_CROSS_AGENCY_ACCESS:
            logger.warning(
                f"Cross-agency access denied: client {client.client_id} "
                f"from agency {client.agency_id} trying to access agency {agency_id}"
            )
            return False
        
        # Check if client has explicit access to the agency
        if client.allowed_agencies:
            if agency_id in [str(a) for a in client.allowed_agencies]:
                logger.info(
                    f"Cross-agency access allowed: client {client.client_id} "
                    f"has explicit access to agency {agency_id}"
                )
                return True
        
        return False
    
    @staticmethod
    async def validate_user_agency_access(
        user: User,
        agency_id: str,
        db: AsyncSession
    ) -> bool:
        """
        Validate if a user has access to an agency.
        
        Args:
            user: User object
            agency_id: Target agency ID
            db: Database session
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Check if user belongs to the agency
        if hasattr(user, "agency_id") and str(user.agency_id) == str(agency_id):
            return True
        
        # Check if user has multi-agency access (e.g., super admin)
        if hasattr(user, "is_superadmin") and user.is_superadmin:
            return True
        
        # Check if user has explicit access through agency memberships
        # This would involve checking a user_agency_memberships table
        # For now, we'll keep it simple
        
        return False
    
    @staticmethod
    async def filter_by_agency(
        query,
        agency_id: str,
        strict: bool = None
    ):
        """
        Add agency filtering to a SQLAlchemy query.
        
        Args:
            query: SQLAlchemy query
            agency_id: Agency ID to filter by
            strict: Whether to enforce strict isolation (overrides config)
            
        Returns:
            Filtered query
        """
        if strict is None:
            strict = oauth_config.AGENCY_ISOLATION_STRICT
        
        if strict:
            # Strict mode: only return records for this agency
            return query.where(query.c.agency_id == agency_id)
        else:
            # Relaxed mode: return records for this agency or with cross-agency access
            return query.where(
                or_(
                    query.c.agency_id == agency_id,
                    query.c.allowed_agencies.contains([agency_id])
                )
            )
    
    @staticmethod
    async def validate_token_agency_access(
        token: OAuthToken,
        agency_id: str
    ) -> bool:
        """
        Validate if a token has access to an agency.
        
        Args:
            token: OAuth token
            agency_id: Target agency ID
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Check if token belongs to the agency
        if str(token.agency_id) == str(agency_id):
            return True
        
        # Check if token has cross-agency scope
        if token.scope:
            scopes = token.scope.split()
            if "admin:agencies" in scopes or "cross_agency" in scopes:
                logger.info(
                    f"Cross-agency token access allowed: "
                    f"token has admin:agencies scope"
                )
                return True
        
        return False


class AgencyMiddleware:
    """
    Middleware to inject agency context into requests.
    """
    
    def __init__(self, enforce_agency: bool = True):
        self.enforce_agency = enforce_agency
    
    async def __call__(
        self,
        request: Request,
        call_next,
        db: AsyncSession = Depends(get_db)
    ):
        """
        Process request with agency context.
        """
        # Extract agency context
        agency_context = await AgencyContext.from_request(request, db)
        
        if self.enforce_agency and not agency_context:
            # No agency context found and enforcement is enabled
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_agency_context",
                    "error_description": "Could not determine agency context"
                }
            )
        
        # Store agency context in request state
        if agency_context:
            request.state.agency = agency_context
            logger.debug(f"Agency context set: {agency_context.agency_id}")
        
        # Process request
        response = await call_next(request)
        
        # Add agency header to response
        if agency_context:
            response.headers["X-Agency-ID"] = agency_context.agency_id
        
        return response


# Dependency injection helpers

async def get_current_agency(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_agency_id: Optional[str] = Header(None)
) -> AgencyContext:
    """
    Get current agency context from request.
    
    Args:
        request: FastAPI request
        db: Database session
        x_agency_id: Optional agency ID header
        
    Returns:
        Agency context
        
    Raises:
        HTTPException: If agency context cannot be determined
    """
    # Try to get from request state first (set by middleware)
    if hasattr(request.state, "agency"):
        return request.state.agency
    
    # Otherwise, extract from request
    agency_context = await AgencyContext.from_request(request, db)
    
    if not agency_context:
        raise HTTPException(
            status_code=400,
            detail="Could not determine agency context"
        )
    
    return agency_context


async def get_optional_agency(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[AgencyContext]:
    """
    Get optional agency context from request.
    
    Args:
        request: FastAPI request
        db: Database session
        
    Returns:
        Agency context or None
    """
    # Try to get from request state first
    if hasattr(request.state, "agency"):
        return request.state.agency
    
    # Otherwise, extract from request
    return await AgencyContext.from_request(request, db)


def require_agency_access(
    operation: str = "access",
    allow_cross_agency: bool = False
):
    """
    Decorator/dependency to require agency access for an endpoint.
    
    Args:
        operation: Type of operation (access, read, write, admin)
        allow_cross_agency: Whether to allow cross-agency access
        
    Returns:
        Dependency function
    """
    async def agency_access_checker(
        request: Request,
        agency: AgencyContext = Depends(get_current_agency),
        db: AsyncSession = Depends(get_db)
    ):
        """Check agency access."""
        # Get current user
        if not hasattr(request.state, "user"):
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        user = request.state.user
        
        # Validate user has access to the agency
        has_access = await AgencyIsolation.validate_user_agency_access(
            user, agency.agency_id, db
        )
        
        if not has_access and not allow_cross_agency:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to agency {agency.agency_id}"
            )
        
        return agency
    
    return agency_access_checker


class AgencyScopedQuery:
    """
    Helper for creating agency-scoped database queries.
    """
    
    def __init__(self, agency_id: str, strict: bool = None):
        self.agency_id = agency_id
        self.strict = strict if strict is not None else oauth_config.AGENCY_ISOLATION_STRICT
    
    def filter_clients(self, query):
        """Filter OAuth clients by agency."""
        if self.strict:
            return query.where(OAuthClient.agency_id == self.agency_id)
        else:
            return query.where(
                or_(
                    OAuthClient.agency_id == self.agency_id,
                    OAuthClient.allowed_agencies.contains([self.agency_id])
                )
            )
    
    def filter_tokens(self, query):
        """Filter OAuth tokens by agency."""
        return query.where(OAuthToken.agency_id == self.agency_id)
    
    def filter_users(self, query):
        """Filter users by agency."""
        return query.where(User.agency_id == self.agency_id)
    
    def apply(self, query, model):
        """Apply agency filtering based on model type."""
        if model == OAuthClient:
            return self.filter_clients(query)
        elif model == OAuthToken:
            return self.filter_tokens(query)
        elif model == User:
            return self.filter_users(query)
        else:
            # Generic filtering for models with agency_id
            return query.where(model.agency_id == self.agency_id)