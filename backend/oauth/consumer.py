"""
OAuth2 Consumer for external provider integration.
Handles authentication with Google, Instagram, OnlyFans, and other providers.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import secrets
import logging
from abc import ABC, abstractmethod
import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from oauth.models import ExternalOAuthToken
from oauth.config import oauth_config
from models.user import User
from core.config import settings

logger = logging.getLogger(__name__)


class OAuthProvider(ABC):
    """
    Abstract base class for OAuth providers.
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: Optional[str] = None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope or ""
        self.state_prefix = f"{self.provider_name}_"
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name identifier."""
        pass
    
    @property
    @abstractmethod
    def authorization_url(self) -> str:
        """OAuth authorization endpoint."""
        pass
    
    @property
    @abstractmethod
    def token_url(self) -> str:
        """OAuth token endpoint."""
        pass
    
    @property
    @abstractmethod
    def userinfo_url(self) -> str:
        """User information endpoint."""
        pass
    
    async def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate authorization URL.
        
        Returns:
            Tuple of (authorization_url, state)
        """
        if not state:
            state = self.state_prefix + secrets.token_urlsafe(32)
        
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scope
        )
        
        auth_url, _ = client.create_authorization_url(
            self.authorization_url,
            state=state
        )
        
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from provider.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    @abstractmethod
    async def parse_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse provider-specific user info into standard format.
        """
        pass


class GoogleOAuthProvider(OAuthProvider):
    """
    Google OAuth2 provider implementation.
    """
    
    provider_name = "google"
    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="openid email profile"
        )
    
    async def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generate Google authorization URL with additional parameters.
        """
        auth_url, state = await super().get_authorization_url(state)
        
        # Add Google-specific parameters
        auth_url += "&access_type=offline&prompt=consent"
        
        return auth_url, state
    
    async def parse_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Google user info.
        """
        return {
            "provider": self.provider_name,
            "provider_user_id": user_info.get("sub"),
            "email": user_info.get("email"),
            "email_verified": user_info.get("email_verified", False),
            "name": user_info.get("name"),
            "given_name": user_info.get("given_name"),
            "family_name": user_info.get("family_name"),
            "picture": user_info.get("picture"),
            "locale": user_info.get("locale")
        }


class InstagramOAuthProvider(OAuthProvider):
    """
    Instagram OAuth2 provider implementation.
    """
    
    provider_name = "instagram"
    authorization_url = "https://api.instagram.com/oauth/authorize"
    token_url = "https://api.instagram.com/oauth/access_token"
    userinfo_url = "https://graph.instagram.com/me"
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user_profile,user_media"
        )
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get Instagram user information.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.userinfo_url}?fields=id,username,account_type,media_count&access_token={access_token}"
            )
            response.raise_for_status()
            return response.json()
    
    async def parse_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Instagram user info.
        """
        return {
            "provider": self.provider_name,
            "provider_user_id": user_info.get("id"),
            "username": user_info.get("username"),
            "account_type": user_info.get("account_type"),
            "media_count": user_info.get("media_count")
        }


class OnlyFansOAuthProvider(OAuthProvider):
    """
    OnlyFans OAuth2 provider implementation (placeholder).
    Note: OnlyFans doesn't have a public OAuth API yet.
    This is a preparatory implementation for future use.
    """
    
    provider_name = "onlyfans"
    authorization_url = "https://onlyfans.com/oauth/authorize"  # Placeholder
    token_url = "https://onlyfans.com/oauth/token"  # Placeholder
    userinfo_url = "https://onlyfans.com/api/v2/users/me"  # Placeholder
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="read write"
        )
        logger.warning("OnlyFans OAuth provider is a placeholder implementation")
    
    async def parse_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse OnlyFans user info (placeholder).
        """
        return {
            "provider": self.provider_name,
            "provider_user_id": user_info.get("id"),
            "username": user_info.get("username"),
            "display_name": user_info.get("name"),
            "avatar": user_info.get("avatar"),
            "is_performer": user_info.get("isPerformer", False)
        }


class MicrosoftOAuthProvider(OAuthProvider):
    """
    Microsoft Azure AD OAuth2 provider implementation.
    """
    
    provider_name = "microsoft"
    authorization_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    userinfo_url = "https://graph.microsoft.com/v1.0/me"
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="openid profile email User.Read"
        )
    
    async def parse_user_info(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Microsoft user info.
        """
        return {
            "provider": self.provider_name,
            "provider_user_id": user_info.get("id"),
            "email": user_info.get("mail") or user_info.get("userPrincipalName"),
            "name": user_info.get("displayName"),
            "given_name": user_info.get("givenName"),
            "family_name": user_info.get("surname"),
            "job_title": user_info.get("jobTitle"),
            "office_location": user_info.get("officeLocation")
        }


class OAuthProviderRegistry:
    """
    Registry for managing OAuth providers.
    """
    
    def __init__(self):
        self._providers: Dict[str, OAuthProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """
        Initialize configured OAuth providers.
        """
        # Google
        if hasattr(settings, "GOOGLE_CLIENT_ID") and settings.GOOGLE_CLIENT_ID:
            self.register_provider(
                "google",
                GoogleOAuthProvider(
                    client_id=settings.GOOGLE_CLIENT_ID,
                    client_secret=settings.GOOGLE_CLIENT_SECRET,
                    redirect_uri=f"{settings.OAUTH_ISSUER}/oauth/callback/google"
                )
            )
        
        # Instagram
        if hasattr(settings, "INSTAGRAM_CLIENT_ID") and settings.INSTAGRAM_CLIENT_ID:
            self.register_provider(
                "instagram",
                InstagramOAuthProvider(
                    client_id=settings.INSTAGRAM_CLIENT_ID,
                    client_secret=settings.INSTAGRAM_CLIENT_SECRET,
                    redirect_uri=f"{settings.OAUTH_ISSUER}/oauth/callback/instagram"
                )
            )
        
        # OnlyFans (placeholder)
        if hasattr(settings, "ONLYFANS_CLIENT_ID") and settings.ONLYFANS_CLIENT_ID:
            self.register_provider(
                "onlyfans",
                OnlyFansOAuthProvider(
                    client_id=settings.ONLYFANS_CLIENT_ID,
                    client_secret=settings.ONLYFANS_CLIENT_SECRET,
                    redirect_uri=f"{settings.OAUTH_ISSUER}/oauth/callback/onlyfans"
                )
            )
        
        # Microsoft
        if hasattr(settings, "MICROSOFT_CLIENT_ID") and settings.MICROSOFT_CLIENT_ID:
            self.register_provider(
                "microsoft",
                MicrosoftOAuthProvider(
                    client_id=settings.MICROSOFT_CLIENT_ID,
                    client_secret=settings.MICROSOFT_CLIENT_SECRET,
                    redirect_uri=f"{settings.OAUTH_ISSUER}/oauth/callback/microsoft"
                )
            )
    
    def register_provider(self, name: str, provider: OAuthProvider):
        """
        Register an OAuth provider.
        """
        self._providers[name] = provider
        logger.info(f"Registered OAuth provider: {name}")
    
    def get_provider(self, name: str) -> Optional[OAuthProvider]:
        """
        Get an OAuth provider by name.
        """
        return self._providers.get(name)
    
    def list_providers(self) -> List[str]:
        """
        List all registered provider names.
        """
        return list(self._providers.keys())
    
    def is_provider_enabled(self, name: str) -> bool:
        """
        Check if a provider is enabled.
        """
        return name in self._providers


class ExternalOAuthManager:
    """
    Manages external OAuth tokens and user linking.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = OAuthProviderRegistry()
    
    async def link_external_account(
        self,
        user_id: str,
        agency_id: str,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        scope: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None
    ) -> ExternalOAuthToken:
        """
        Link an external OAuth account to a user.
        """
        # Check for existing token
        result = await self.db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.user_id == user_id,
                ExternalOAuthToken.provider == provider
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing token
            existing.access_token = access_token  # Should be encrypted
            existing.refresh_token = refresh_token
            existing.expires_at = expires_at
            existing.scope = scope
            existing.raw_data = str(raw_data) if raw_data else None
            existing.updated_at = datetime.now(timezone.utc)
            
            await self.db.commit()
            logger.info(f"Updated {provider} token for user {user_id}")
            return existing
        
        # Create new token
        token = ExternalOAuthToken(
            agency_id=agency_id,
            user_id=user_id,
            provider=provider,
            access_token=access_token,  # Should be encrypted
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=scope,
            raw_data=str(raw_data) if raw_data else None
        )
        
        self.db.add(token)
        await self.db.commit()
        
        logger.info(f"Linked {provider} account for user {user_id}")
        return token
    
    async def unlink_external_account(
        self,
        user_id: str,
        provider: str
    ) -> bool:
        """
        Unlink an external OAuth account from a user.
        """
        result = await self.db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.user_id == user_id,
                ExternalOAuthToken.provider == provider
            )
        )
        token = result.scalar_one_or_none()
        
        if not token:
            return False
        
        await self.db.delete(token)
        await self.db.commit()
        
        logger.info(f"Unlinked {provider} account for user {user_id}")
        return True
    
    async def get_external_token(
        self,
        user_id: str,
        provider: str
    ) -> Optional[ExternalOAuthToken]:
        """
        Get external OAuth token for a user and provider.
        """
        result = await self.db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.user_id == user_id,
                ExternalOAuthToken.provider == provider
            )
        )
        return result.scalar_one_or_none()
    
    async def refresh_external_token(
        self,
        user_id: str,
        provider: str
    ) -> Optional[ExternalOAuthToken]:
        """
        Refresh an external OAuth token if needed.
        """
        token = await self.get_external_token(user_id, provider)
        
        if not token:
            return None
        
        # Check if token needs refresh
        if not token.needs_refresh():
            return token
        
        if not token.refresh_token:
            logger.warning(f"No refresh token available for {provider} token")
            return token
        
        # Get provider
        oauth_provider = self.registry.get_provider(provider)
        if not oauth_provider:
            logger.error(f"Provider {provider} not registered")
            return token
        
        try:
            # Refresh the token
            token_data = await oauth_provider.refresh_token(token.refresh_token)
            
            # Update token
            token.access_token = token_data["access_token"]
            if "refresh_token" in token_data:
                token.refresh_token = token_data["refresh_token"]
            
            if "expires_in" in token_data:
                token.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=token_data["expires_in"]
                )
            
            await self.db.commit()
            logger.info(f"Refreshed {provider} token for user {user_id}")
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to refresh {provider} token: {e}")
            return None
    
    async def get_user_external_accounts(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all external accounts linked to a user.
        """
        result = await self.db.execute(
            select(ExternalOAuthToken).where(
                ExternalOAuthToken.user_id == user_id
            ).order_by(ExternalOAuthToken.created_at.desc())
        )
        tokens = result.scalars().all()
        
        accounts = []
        for token in tokens:
            accounts.append({
                "provider": token.provider,
                "connected_at": token.created_at.isoformat(),
                "updated_at": token.updated_at.isoformat() if token.updated_at else None,
                "is_expired": token.is_expired,
                "needs_refresh": token.needs_refresh(),
                "scope": token.scope
            })
        
        return accounts


# Global registry instance
oauth_provider_registry = OAuthProviderRegistry()