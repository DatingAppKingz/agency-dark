"""
OAuth to JWT compatibility layer for seamless migration.
Provides adapters and utilities to run both authentication systems in parallel.
"""
from typing import Optional, Union, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
from jwt import PyJWTError

from .models import OAuthToken, OAuthClient
from .provider import get_current_oauth_token, get_current_oauth_user
from models.user import User
from core.database import get_db
from core.config import settings
from core.security_v2.authentication.jwt_handler import JWTHandler

logger = logging.getLogger(__name__)


class DualAuthBearer(HTTPBearer):
    """
    Custom Bearer authentication that supports both OAuth tokens and JWTs.
    Tries OAuth first, then falls back to JWT for backward compatibility.
    """
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.jwt_handler = JWTHandler()
    
    async def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = None
    ) -> Optional[str]:
        """Extract and validate bearer token."""
        credentials = await super().__call__(request)
        if not credentials:
            return None
        
        if credentials.scheme != "Bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid authentication scheme"
                )
            else:
                return None
        
        return credentials.credentials


dual_auth_bearer = DualAuthBearer()


class OAuthToJWTAdapter:
    """
    Adapter to convert OAuth tokens to JWT-like format.
    Maintains backward compatibility with existing JWT-based code.
    """
    
    @staticmethod
    def oauth_token_to_jwt_claims(token: OAuthToken, user: User) -> Dict[str, Any]:
        """
        Convert an OAuth token to JWT-compatible claims.
        
        Args:
            token: OAuth token object
            user: User associated with the token
            
        Returns:
            JWT-compatible claims dictionary
        """
        claims = {
            "sub": str(user.id),
            "email": user.email,
            "agency_id": str(token.agency_id),
            "scopes": token.scope.split() if token.scope else [],
            "token_type": "oauth",  # Marker to identify OAuth-derived tokens
            "client_id": token.client_id,
            "iat": int(token.created_at.timestamp()),
        }
        
        if token.expires_at:
            claims["exp"] = int(token.expires_at.timestamp())
        
        # Add user roles and permissions
        if hasattr(user, 'role'):
            claims["role"] = user.role
        
        if hasattr(user, 'permissions'):
            claims["permissions"] = user.permissions
        
        # Add extra data from token
        if token.extra_data:
            claims.update(token.extra_data)
        
        return claims
    
    @staticmethod
    def jwt_to_oauth_token(jwt_payload: Dict[str, Any], db: AsyncSession) -> OAuthToken:
        """
        Create a temporary OAuth token object from JWT claims.
        Used for backward compatibility when JWT is still in use.
        
        Args:
            jwt_payload: Decoded JWT payload
            db: Database session
            
        Returns:
            Temporary OAuth token object (not persisted)
        """
        # Create a non-persisted OAuth token for compatibility
        token = OAuthToken(
            user_id=jwt_payload.get("sub"),
            agency_id=jwt_payload.get("agency_id"),
            client_id="jwt-compatibility",  # Special marker
            token_type="Bearer",
            access_token=f"jwt-compat-{jwt_payload.get('jti', 'unknown')}",
            scope=" ".join(jwt_payload.get("scopes", [])),
            expires_at=datetime.fromtimestamp(jwt_payload["exp"], tz=timezone.utc) if "exp" in jwt_payload else None,
            extra_data={
                "jwt_original": True,
                "role": jwt_payload.get("role"),
                "permissions": jwt_payload.get("permissions", [])
            }
        )
        
        # Don't add to session - this is temporary
        return token


class UnifiedAuthDependency:
    """
    Unified authentication dependency that supports both OAuth and JWT.
    Provides a single interface for authentication across the application.
    """
    
    def __init__(self, required_scopes: Optional[list] = None):
        self.required_scopes = required_scopes or []
        self.jwt_handler = JWTHandler()
        self.adapter = OAuthToJWTAdapter()
    
    async def __call__(
        self,
        request: Request,
        token: str = Depends(dual_auth_bearer),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """
        Authenticate user using either OAuth or JWT.
        
        Args:
            request: FastAPI request
            token: Bearer token string
            db: Database session
            
        Returns:
            Authenticated User object
            
        Raises:
            HTTPException: If authentication fails
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Try OAuth first
        oauth_user = await self._try_oauth_auth(token, request, db)
        if oauth_user:
            return oauth_user
        
        # Fall back to JWT
        jwt_user = await self._try_jwt_auth(token, db)
        if jwt_user:
            return jwt_user
        
        # Neither worked
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    async def _try_oauth_auth(
        self,
        token: str,
        request: Request,
        db: AsyncSession
    ) -> Optional[User]:
        """Try to authenticate using OAuth token."""
        try:
            # Query OAuth token
            result = await db.execute(
                select(OAuthToken).where(
                    OAuthToken.access_token == token
                )
            )
            oauth_token = result.scalar_one_or_none()
            
            if not oauth_token or oauth_token.is_expired:
                return None
            
            # Check required scopes
            if self.required_scopes:
                token_scopes = set(oauth_token.scope.split())
                required = set(self.required_scopes)
                if not required.issubset(token_scopes):
                    logger.warning(f"Insufficient scopes: required {required}, got {token_scopes}")
                    return None
            
            # Load user
            result = await db.execute(
                select(User).where(User.id == oauth_token.user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Store token in request state for later use
                request.state.oauth_token = oauth_token
                request.state.auth_method = "oauth"
                logger.debug(f"OAuth authentication successful for user {user.id}")
            
            return user
            
        except Exception as e:
            logger.error(f"OAuth authentication error: {e}")
            return None
    
    async def _try_jwt_auth(self, token: str, db: AsyncSession) -> Optional[User]:
        """Try to authenticate using JWT."""
        try:
            # Decode JWT
            payload = self.jwt_handler.decode_token(token)
            if not payload:
                return None
            
            # Check token type (if present)
            if payload.get("token_type") == "refresh":
                logger.warning("Refresh token used for authentication")
                return None
            
            # Check required scopes
            if self.required_scopes:
                token_scopes = set(payload.get("scopes", []))
                required = set(self.required_scopes)
                if not required.issubset(token_scopes):
                    logger.warning(f"Insufficient JWT scopes: required {required}, got {token_scopes}")
                    return None
            
            # Load user
            user_id = payload.get("sub")
            if not user_id:
                return None
            
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Create compatibility OAuth token and store in request
                compat_token = self.adapter.jwt_to_oauth_token(payload, db)
                request.state.oauth_token = compat_token
                request.state.auth_method = "jwt"
                logger.debug(f"JWT authentication successful for user {user.id}")
            
            return user
            
        except PyJWTError as e:
            logger.error(f"JWT authentication error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected JWT authentication error: {e}")
            return None


# Convenience functions for dependency injection

def get_current_user(
    required_scopes: Optional[list] = None
) -> UnifiedAuthDependency:
    """
    Get current authenticated user with optional scope requirements.
    
    Args:
        required_scopes: List of required OAuth scopes
        
    Returns:
        Dependency that provides the current User
    """
    return UnifiedAuthDependency(required_scopes=required_scopes)


async def get_optional_user(
    request: Request,
    token: Optional[str] = Depends(dual_auth_bearer),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    Does not raise exceptions for missing authentication.
    """
    if not token:
        return None
    
    auth = UnifiedAuthDependency()
    try:
        return await auth(request, token, db)
    except HTTPException:
        return None


class MigrationUtilities:
    """
    Utilities to help migrate existing sessions and tokens.
    """
    
    @staticmethod
    async def convert_jwt_session_to_oauth(
        jwt_token: str,
        db: AsyncSession,
        jwt_handler: JWTHandler
    ) -> Optional[OAuthToken]:
        """
        Convert an existing JWT session to OAuth token.
        
        Args:
            jwt_token: JWT token string
            db: Database session
            jwt_handler: JWT handler for decoding
            
        Returns:
            Created OAuth token or None if conversion fails
        """
        try:
            # Decode JWT
            payload = jwt_handler.decode_token(jwt_token)
            if not payload:
                return None
            
            # Check if already converted
            existing = await db.execute(
                select(OAuthToken).where(
                    OAuthToken.extra_data["jwt_jti"].astext == payload.get("jti")
                )
            )
            if existing.scalar_one_or_none():
                logger.info(f"JWT session already converted: {payload.get('jti')}")
                return existing.scalar_one_or_none()
            
            # Create OAuth token
            import secrets
            oauth_token = OAuthToken(
                user_id=payload.get("sub"),
                agency_id=payload.get("agency_id"),
                client_id="jwt-migration",  # Special migration client
                token_type="Bearer",
                access_token=secrets.token_urlsafe(32),
                refresh_token=secrets.token_urlsafe(32) if payload.get("token_type") != "refresh" else None,
                scope=" ".join(payload.get("scopes", [])),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc) if "exp" in payload else None,
                extra_data={
                    "migrated_from_jwt": True,
                    "jwt_jti": payload.get("jti"),
                    "migration_date": datetime.now(timezone.utc).isoformat(),
                    "original_role": payload.get("role"),
                    "original_permissions": payload.get("permissions", [])
                }
            )
            
            db.add(oauth_token)
            await db.commit()
            
            logger.info(f"Successfully migrated JWT session to OAuth: {oauth_token.access_token}")
            return oauth_token
            
        except Exception as e:
            logger.error(f"Failed to convert JWT to OAuth: {e}")
            await db.rollback()
            return None
    
    @staticmethod
    async def bulk_migrate_active_sessions(
        db: AsyncSession,
        jwt_handler: JWTHandler,
        redis_client=None
    ) -> Dict[str, int]:
        """
        Migrate all active JWT sessions to OAuth tokens.
        
        Args:
            db: Database session
            jwt_handler: JWT handler
            redis_client: Optional Redis client for session lookup
            
        Returns:
            Statistics of migration
        """
        stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "already_migrated": 0
        }
        
        # This would typically scan Redis or another session store
        # For now, this is a placeholder implementation
        logger.info("Starting bulk session migration")
        
        # TODO: Implement actual session scanning from Redis/session store
        # This would involve:
        # 1. Scanning all active JWT sessions
        # 2. Converting each to OAuth token
        # 3. Updating session store with new token
        
        logger.info(f"Bulk migration complete: {stats}")
        return stats
    
    @staticmethod
    async def create_migration_client(
        agency_id: str,
        db: AsyncSession
    ) -> OAuthClient:
        """
        Create a special OAuth client for migration purposes.
        
        Args:
            agency_id: Agency ID
            db: Database session
            
        Returns:
            Created OAuth client
        """
        import secrets
        
        # Check if migration client already exists
        result = await db.execute(
            select(OAuthClient).where(
                OAuthClient.agency_id == agency_id,
                OAuthClient.client_id.like("migration-%")
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        
        # Create new migration client
        client = OAuthClient(
            agency_id=agency_id,
            client_id=f"migration-{secrets.token_urlsafe(16)}",
            client_secret=secrets.token_urlsafe(32),
            client_name="JWT Migration Client",
            redirect_uris=["http://localhost:3000/auth/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="read write admin",
            is_active=True
        )
        
        db.add(client)
        await db.commit()
        
        logger.info(f"Created migration client for agency {agency_id}: {client.client_id}")
        return client


# Update CurrentUser dependency to use unified auth
CurrentUser = get_current_user()
OptionalUser = get_optional_user