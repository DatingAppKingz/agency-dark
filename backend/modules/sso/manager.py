"""
SSO Manager - Central orchestration for SSO operations
"""
import logging
import secrets
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import SSOProvider, SSOProviderType, SSOSession, SCIMUser
from .saml import SAMLProvider
from .oauth import OAuthProvider
from .scim import SCIMService
from core.domain.models import User, Agency
from core.security import create_access_token

logger = logging.getLogger(__name__)


class SSOManager:
    """Manages SSO providers and authentication flows"""
    
    def __init__(self):
        self._providers = {}
        self._scim_services = {}
    
    async def get_provider(
        self,
        db: AsyncSession,
        provider_id: UUID
    ) -> Optional[SSOProvider]:
        """Get SSO provider by ID"""
        result = await db.execute(
            select(SSOProvider).where(
                and_(
                    SSOProvider.id == provider_id,
                    SSOProvider.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_agency_providers(
        self,
        db: AsyncSession,
        agency_id: UUID
    ) -> List[SSOProvider]:
        """Get all active SSO providers for an agency"""
        result = await db.execute(
            select(SSOProvider).where(
                and_(
                    SSOProvider.agency_id == agency_id,
                    SSOProvider.is_active == True
                )
            ).order_by(SSOProvider.name)
        )
        return result.scalars().all()
    
    async def create_provider(
        self,
        db: AsyncSession,
        agency_id: UUID,
        provider_data: Dict[str, Any]
    ) -> SSOProvider:
        """Create new SSO provider"""
        provider = SSOProvider(
            agency_id=agency_id,
            **provider_data
        )
        
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
        
        return provider
    
    async def update_provider(
        self,
        db: AsyncSession,
        provider_id: UUID,
        update_data: Dict[str, Any]
    ) -> SSOProvider:
        """Update SSO provider configuration"""
        provider = await self.get_provider(db, provider_id)
        if not provider:
            raise ValueError("Provider not found")
        
        for key, value in update_data.items():
            if hasattr(provider, key):
                setattr(provider, key, value)
        
        provider.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(provider)
        
        # Clear cached provider instances
        if str(provider_id) in self._providers:
            del self._providers[str(provider_id)]
        
        return provider
    
    def get_auth_handler(self, provider: SSOProvider):
        """Get appropriate authentication handler for provider"""
        provider_key = str(provider.id)
        
        if provider_key not in self._providers:
            if provider.provider_type == SSOProviderType.SAML:
                self._providers[provider_key] = SAMLProvider(provider)
            elif provider.provider_type in [SSOProviderType.OAUTH2, SSOProviderType.OIDC]:
                self._providers[provider_key] = OAuthProvider(provider)
            else:
                raise ValueError(f"Unsupported provider type: {provider.provider_type}")
        
        return self._providers[provider_key]
    
    def get_scim_service(self, provider: SSOProvider) -> SCIMService:
        """Get SCIM service for provider"""
        provider_key = str(provider.id)
        
        if provider_key not in self._scim_services:
            self._scim_services[provider_key] = SCIMService(provider)
        
        return self._scim_services[provider_key]
    
    async def authenticate_user(
        self,
        db: AsyncSession,
        provider: SSOProvider,
        auth_response: Dict[str, Any],
        request_info: Dict[str, Any]
    ) -> Tuple[User, str]:
        """Authenticate user via SSO and create/update user record"""
        handler = self.get_auth_handler(provider)
        
        # Extract user data based on provider type
        if provider.provider_type == SSOProviderType.SAML:
            user_data = auth_response  # Already processed by SAML handler
        else:
            # OAuth/OIDC - map user info
            user_data = handler.map_user_info(
                auth_response.get('user_info', {}),
                auth_response.get('id_token_claims')
            )
        
        # Find or create user
        user = await self._find_or_create_user(db, provider, user_data)
        
        # Create SSO session
        if provider.provider_type == SSOProviderType.SAML:
            session = await handler.create_session(
                db, str(user.id), user_data, request_info
            )
        else:
            session = await handler.create_session(
                db, str(user.id), auth_response, request_info
            )
        
        # Generate access token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "sso_session": str(session.id),
                "provider": str(provider.id)
            }
        )
        
        return user, access_token
    
    async def _find_or_create_user(
        self,
        db: AsyncSession,
        provider: SSOProvider,
        user_data: Dict[str, Any]
    ) -> User:
        """Find existing user or create new one"""
        email = user_data.get('email')
        if not email:
            raise ValueError("Email is required for SSO authentication")
        
        # Check if user exists
        result = await db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.agency_id == provider.agency_id
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update user info if changed
            if user_data.get('first_name') and user_data['first_name'] != user.first_name:
                user.first_name = user_data['first_name']
            if user_data.get('last_name') and user_data['last_name'] != user.last_name:
                user.last_name = user_data['last_name']
            
            user.updated_at = datetime.utcnow()
            await db.commit()
            
        elif provider.auto_provision_users:
            # Create new user
            user = User(
                id=uuid4(),
                email=email,
                username=email.split('@')[0],  # Default username
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                is_active=True,
                agency_id=provider.agency_id,
                role=provider.default_role or 'fan',
                hashed_password='',  # SSO users don't need passwords
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            # Create SCIM record if external ID provided
            if user_data.get('external_id'):
                scim_user = SCIMUser(
                    user_id=user.id,
                    provider_id=provider.id,
                    external_id=user_data['external_id'],
                    scim_id=str(user.id),
                    schemas=[SCIMService.SCIM_SCHEMAS['user']],
                    last_synced=datetime.utcnow(),
                    sync_status='active'
                )
                db.add(scim_user)
                await db.commit()
        else:
            raise ValueError(f"User {email} not found and auto-provisioning is disabled")
        
        return user
    
    async def logout_user(
        self,
        db: AsyncSession,
        session_id: UUID,
        request_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Logout user and return logout URL if applicable"""
        # Get session
        result = await db.execute(
            select(SSOSession).options(
                selectinload(SSOSession.provider)
            ).where(SSOSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        provider = session.provider
        handler = self.get_auth_handler(provider)
        
        logout_url = None
        
        # Handle provider-specific logout
        if provider.provider_type == SSOProviderType.SAML and request_data:
            # SAML SLO
            logout_url = handler.init_logout_request(
                request_data,
                session.name_id,
                session.session_index
            )
        elif provider.provider_type in [SSOProviderType.OAUTH2, SSOProviderType.OIDC]:
            # Revoke tokens if supported
            if session.access_token:
                await handler.revoke_token(session.access_token, 'access_token')
            if session.refresh_token:
                await handler.revoke_token(session.refresh_token, 'refresh_token')
        
        # Delete session
        await db.delete(session)
        await db.commit()
        
        return logout_url
    
    async def validate_sso_session(
        self,
        db: AsyncSession,
        session_id: UUID
    ) -> Tuple[bool, Optional[SSOSession]]:
        """Validate SSO session"""
        result = await db.execute(
            select(SSOSession).options(
                selectinload(SSOSession.provider)
            ).where(SSOSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return False, None
        
        provider = session.provider
        handler = self.get_auth_handler(provider)
        
        # Provider-specific validation
        if provider.provider_type == SSOProviderType.SAML:
            valid = await handler.validate_session(db, str(session_id))
            return valid, session if valid else None
        else:
            # OAuth/OIDC
            return await handler.validate_session(db, str(session_id))
    
    async def cleanup_expired_sessions(
        self,
        db: AsyncSession,
        older_than_hours: int = 24
    ) -> int:
        """Clean up expired SSO sessions"""
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        result = await db.execute(
            select(SSOSession).where(
                or_(
                    SSOSession.expires_at < datetime.utcnow(),
                    SSOSession.last_activity < cutoff
                )
            )
        )
        sessions = result.scalars().all()
        
        count = len(sessions)
        for session in sessions:
            await db.delete(session)
        
        await db.commit()
        
        return count
    
    async def get_user_sessions(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> List[SSOSession]:
        """Get all active SSO sessions for a user"""
        result = await db.execute(
            select(SSOSession).options(
                selectinload(SSOSession.provider)
            ).where(
                and_(
                    SSOSession.user_id == user_id,
                    SSOSession.expires_at > datetime.utcnow()
                )
            ).order_by(SSOSession.created_at.desc())
        )
        return result.scalars().all()
    
    async def revoke_user_sessions(
        self,
        db: AsyncSession,
        user_id: UUID,
        except_session_id: Optional[UUID] = None
    ) -> int:
        """Revoke all SSO sessions for a user"""
        query = select(SSOSession).where(SSOSession.user_id == user_id)
        
        if except_session_id:
            query = query.where(SSOSession.id != except_session_id)
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        count = 0
        for session in sessions:
            provider = session.provider
            handler = self.get_auth_handler(provider)
            
            # Revoke OAuth tokens if applicable
            if provider.provider_type in [SSOProviderType.OAUTH2, SSOProviderType.OIDC]:
                if session.access_token:
                    await handler.revoke_token(session.access_token)
                if session.refresh_token:
                    await handler.revoke_token(session.refresh_token)
            
            await db.delete(session)
            count += 1
        
        await db.commit()
        
        return count


# Global SSO manager instance
sso_manager = SSOManager()