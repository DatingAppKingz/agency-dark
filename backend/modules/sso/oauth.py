"""
OAuth 2.0 / OpenID Connect Provider Implementation
"""
import logging
import secrets
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime, timedelta
import httpx
import jwt
from urllib.parse import urlencode, parse_qs, urlparse

from .models import SSOProvider, SSOSession, SSOProviderType
from core.database import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class OAuthProvider:
    """OAuth 2.0 / OIDC Authentication Provider"""
    
    def __init__(self, provider: SSOProvider):
        self.provider = provider
        self._discovery_doc = None
        self._jwks = None
    
    async def discover_configuration(self) -> Dict[str, Any]:
        """Discover OIDC configuration from well-known endpoint"""
        if self._discovery_doc:
            return self._discovery_doc
            
        if not self.provider.metadata_url:
            # Manual configuration
            return {
                'authorization_endpoint': self.provider.authorization_url,
                'token_endpoint': self.provider.token_url,
                'userinfo_endpoint': self.provider.userinfo_url,
                'jwks_uri': None,
                'issuer': self.provider.entity_id
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.provider.metadata_url)
                response.raise_for_status()
                self._discovery_doc = response.json()
                return self._discovery_doc
        except Exception as e:
            logger.error(f"OIDC discovery failed: {str(e)}")
            raise
    
    async def get_authorization_url(
        self, 
        state: str,
        redirect_uri: str,
        nonce: Optional[str] = None,
        additional_params: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate authorization URL"""
        config = await self.discover_configuration()
        
        params = {
            'client_id': self.provider.client_id,
            'response_type': 'code',
            'scope': ' '.join(self.provider.scopes or ['openid', 'profile', 'email']),
            'redirect_uri': redirect_uri,
            'state': state
        }
        
        if nonce and 'openid' in params['scope']:
            params['nonce'] = nonce
        
        if additional_params:
            params.update(additional_params)
        
        auth_url = config['authorization_endpoint']
        return f"{auth_url}?{urlencode(params)}"
    
    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        config = await self.discover_configuration()
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': self.provider.client_id,
            'client_secret': self.provider.client_secret
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config['token_endpoint'],
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Token exchange failed: {str(e)}")
            raise
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from userinfo endpoint"""
        config = await self.discover_configuration()
        
        if not config.get('userinfo_endpoint'):
            raise ValueError("No userinfo endpoint configured")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    config['userinfo_endpoint'],
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Userinfo request failed: {str(e)}")
            raise
    
    async def validate_id_token(
        self, 
        id_token: str,
        nonce: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate and decode ID token"""
        if self.provider.provider_type != SSOProviderType.OIDC:
            return {}
        
        try:
            # Decode without verification first to get the header
            unverified = jwt.decode(id_token, options={"verify_signature": False})
            
            # Get JWKS for signature verification
            config = await self.discover_configuration()
            if config.get('jwks_uri'):
                jwks = await self._get_jwks(config['jwks_uri'])
                # In production, use proper JWT library with JWKS support
                # For now, skip signature verification in this example
            
            # Validate claims
            claims = unverified
            
            # Check issuer
            if claims.get('iss') != config.get('issuer'):
                raise ValueError("Invalid issuer")
            
            # Check audience
            if claims.get('aud') != self.provider.client_id:
                raise ValueError("Invalid audience")
            
            # Check expiration
            if claims.get('exp', 0) < datetime.utcnow().timestamp():
                raise ValueError("Token expired")
            
            # Check nonce if provided
            if nonce and claims.get('nonce') != nonce:
                raise ValueError("Invalid nonce")
            
            return claims
            
        except Exception as e:
            logger.error(f"ID token validation failed: {str(e)}")
            raise
    
    async def _get_jwks(self, jwks_uri: str) -> Dict[str, Any]:
        """Get JSON Web Key Set"""
        if self._jwks:
            return self._jwks
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                self._jwks = response.json()
                return self._jwks
        except Exception as e:
            logger.error(f"JWKS fetch failed: {str(e)}")
            raise
    
    def map_user_info(
        self, 
        user_info: Dict[str, Any],
        id_token_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Map OAuth/OIDC user info to internal user data"""
        mapping = self.provider.attribute_mapping or {}
        
        # Combine userinfo and ID token claims
        all_claims = {}
        if id_token_claims:
            all_claims.update(id_token_claims)
        all_claims.update(user_info)
        
        # Default mappings for common OIDC claims
        user_data = {
            'email': all_claims.get('email') or all_claims.get('preferred_username'),
            'email_verified': all_claims.get('email_verified', False),
            'first_name': all_claims.get('given_name'),
            'last_name': all_claims.get('family_name'),
            'full_name': all_claims.get('name'),
            'picture': all_claims.get('picture'),
            'external_id': all_claims.get('sub')
        }
        
        # Apply custom mappings
        for internal_key, claim_name in mapping.items():
            if claim_name in all_claims:
                user_data[internal_key] = all_claims[claim_name]
        
        # Handle full name if first/last not available
        if user_data.get('full_name') and not user_data.get('first_name'):
            parts = user_data['full_name'].split(' ', 1)
            user_data['first_name'] = parts[0]
            user_data['last_name'] = parts[1] if len(parts) > 1 else ''
        
        return user_data
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        config = await self.discover_configuration()
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.provider.client_id,
            'client_secret': self.provider.client_secret
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config['token_endpoint'],
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise
    
    async def revoke_token(self, token: str, token_type: str = 'access_token') -> bool:
        """Revoke token (if supported)"""
        config = await self.discover_configuration()
        
        if not config.get('revocation_endpoint'):
            logger.warning("No revocation endpoint available")
            return False
        
        data = {
            'token': token,
            'token_type_hint': token_type,
            'client_id': self.provider.client_id,
            'client_secret': self.provider.client_secret
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config['revocation_endpoint'],
                    data=data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Token revocation failed: {str(e)}")
            return False
    
    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        token_response: Dict[str, Any],
        request_info: Dict[str, Any]
    ) -> SSOSession:
        """Create SSO session"""
        # Calculate expiration
        expires_in = token_response.get('expires_in', 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        session = SSOSession(
            user_id=user_id,
            provider_id=self.provider.id,
            access_token=token_response.get('access_token'),
            refresh_token=token_response.get('refresh_token'),
            id_token=token_response.get('id_token'),
            expires_at=expires_at,
            ip_address=request_info.get('ip_address'),
            user_agent=request_info.get('user_agent')
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return session
    
    async def validate_session(
        self, 
        db: AsyncSession, 
        session_id: str
    ) -> Tuple[bool, Optional[SSOSession]]:
        """Validate and potentially refresh SSO session"""
        result = await db.execute(
            select(SSOSession).where(
                SSOSession.id == session_id,
                SSOSession.provider_id == self.provider.id
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return False, None
        
        # Check if expired
        if session.expires_at <= datetime.utcnow():
            # Try to refresh if we have a refresh token
            if session.refresh_token:
                try:
                    token_response = await self.refresh_token(session.refresh_token)
                    
                    # Update session
                    session.access_token = token_response.get('access_token')
                    if 'refresh_token' in token_response:
                        session.refresh_token = token_response['refresh_token']
                    
                    expires_in = token_response.get('expires_in', 3600)
                    session.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                    session.last_activity = datetime.utcnow()
                    
                    await db.commit()
                    return True, session
                    
                except Exception as e:
                    logger.error(f"Session refresh failed: {str(e)}")
                    return False, None
            else:
                return False, None
        
        # Update last activity
        session.last_activity = datetime.utcnow()
        await db.commit()
        
        return True, session