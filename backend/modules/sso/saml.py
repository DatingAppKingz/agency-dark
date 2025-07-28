"""
SAML 2.0 Provider Implementation
"""
import base64
import logging
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.response import OneLogin_Saml2_Response

from .models import SSOProvider, SSOSession, SSOProviderType
from core.database import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class SAMLProvider:
    """SAML 2.0 Authentication Provider"""
    
    def __init__(self, provider: SSOProvider):
        self.provider = provider
        self._settings = None
    
    def get_settings(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SAML settings for OneLogin toolkit"""
        if self._settings:
            return self._settings
            
        settings = {
            "sp": {
                "entityId": f"{request_data['https']}://{request_data['http_host']}/api/v1/sso/saml/metadata/{self.provider.id}",
                "assertionConsumerService": {
                    "url": f"{request_data['https']}://{request_data['http_host']}/api/v1/sso/saml/acs",
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                },
                "singleLogoutService": {
                    "url": f"{request_data['https']}://{request_data['http_host']}/api/v1/sso/saml/sls",
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
                "x509cert": "",
                "privateKey": ""
            },
            "idp": {
                "entityId": self.provider.entity_id,
                "singleSignOnService": {
                    "url": self.provider.sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "singleLogoutService": {
                    "url": self.provider.slo_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "x509cert": self.provider.x509_cert
            },
            "security": {
                "nameIdEncrypted": False,
                "authnRequestsSigned": False,
                "logoutRequestSigned": False,
                "logoutResponseSigned": False,
                "signMetadata": False,
                "wantMessagesSigned": False,
                "wantAssertionsSigned": True,
                "wantAssertionsEncrypted": False,
                "wantNameId": True,
                "wantNameIdEncrypted": False,
                "wantAttributeStatement": True,
                "requestedAuthnContext": True,
                "requestedAuthnContextComparison": "exact",
                "signatureAlgorithm": "http://www.w3.org/2000/09/xmldsig#rsa-sha256",
                "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256"
            }
        }
        
        self._settings = settings
        return settings
    
    def init_auth_request(self, request_data: Dict[str, Any]) -> str:
        """Initialize SAML authentication request"""
        settings = self.get_settings(request_data)
        auth = OneLogin_Saml2_Auth(request_data, settings)
        return auth.login(return_to=request_data.get('return_to'))
    
    def process_response(
        self, 
        request_data: Dict[str, Any], 
        saml_response: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Process SAML response"""
        try:
            settings = self.get_settings(request_data)
            auth = OneLogin_Saml2_Auth(request_data, settings)
            auth.process_response()
            
            if not auth.is_authenticated():
                errors = auth.get_errors()
                return False, None, f"Authentication failed: {', '.join(errors)}"
            
            # Extract user attributes
            attributes = auth.get_attributes()
            name_id = auth.get_nameid()
            session_index = auth.get_session_index()
            
            # Map attributes based on provider configuration
            user_data = self._map_attributes(attributes, name_id)
            user_data['session_index'] = session_index
            user_data['name_id'] = name_id
            
            return True, user_data, None
            
        except Exception as e:
            logger.error(f"SAML response processing error: {str(e)}")
            return False, None, str(e)
    
    def _map_attributes(self, attributes: Dict[str, list], name_id: str) -> Dict[str, Any]:
        """Map SAML attributes to user data"""
        mapping = self.provider.attribute_mapping or {}
        user_data = {'email': name_id}
        
        # Default attribute mappings
        default_mappings = {
            'email': ['email', 'mail', 'emailAddress'],
            'first_name': ['firstName', 'givenName', 'first_name'],
            'last_name': ['lastName', 'surname', 'sn', 'last_name'],
            'full_name': ['displayName', 'cn', 'fullName']
        }
        
        for key, possible_attrs in default_mappings.items():
            if key in mapping:
                # Use custom mapping
                attr_name = mapping[key]
                if attr_name in attributes:
                    user_data[key] = attributes[attr_name][0] if attributes[attr_name] else None
            else:
                # Try default mappings
                for attr in possible_attrs:
                    if attr in attributes and attributes[attr]:
                        user_data[key] = attributes[attr][0]
                        break
        
        # Handle full name if first/last not available
        if 'full_name' in user_data and not user_data.get('first_name'):
            parts = user_data['full_name'].split(' ', 1)
            user_data['first_name'] = parts[0]
            user_data['last_name'] = parts[1] if len(parts) > 1 else ''
        
        return user_data
    
    def init_logout_request(
        self, 
        request_data: Dict[str, Any], 
        name_id: str,
        session_index: Optional[str] = None
    ) -> str:
        """Initialize SAML logout request"""
        settings = self.get_settings(request_data)
        auth = OneLogin_Saml2_Auth(request_data, settings)
        return auth.logout(
            return_to=request_data.get('return_to'),
            name_id=name_id,
            session_index=session_index
        )
    
    def process_logout_response(self, request_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Process SAML logout response"""
        try:
            settings = self.get_settings(request_data)
            auth = OneLogin_Saml2_Auth(request_data, settings)
            url = auth.process_slo(delete_session_cb=lambda: None)
            
            errors = auth.get_errors()
            if errors:
                return False, f"Logout failed: {', '.join(errors)}"
            
            return True, url
            
        except Exception as e:
            logger.error(f"SAML logout response error: {str(e)}")
            return False, str(e)
    
    def get_metadata(self, request_data: Dict[str, Any]) -> str:
        """Generate SP metadata"""
        settings = self.get_settings(request_data)
        saml_settings = OneLogin_Saml2_Settings(settings)
        metadata = saml_settings.get_sp_metadata()
        return metadata
    
    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        session_data: Dict[str, Any],
        request_info: Dict[str, Any]
    ) -> SSOSession:
        """Create SSO session"""
        session = SSOSession(
            user_id=user_id,
            provider_id=self.provider.id,
            session_index=session_data.get('session_index'),
            name_id=session_data.get('name_id'),
            expires_at=datetime.utcnow() + timedelta(hours=8),
            ip_address=request_info.get('ip_address'),
            user_agent=request_info.get('user_agent')
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return session
    
    async def validate_session(self, db: AsyncSession, session_id: str) -> bool:
        """Validate SSO session"""
        result = await db.execute(
            select(SSOSession).where(
                SSOSession.id == session_id,
                SSOSession.provider_id == self.provider.id,
                SSOSession.expires_at > datetime.utcnow()
            )
        )
        session = result.scalar_one_or_none()
        
        if session:
            # Update last activity
            session.last_activity = datetime.utcnow()
            await db.commit()
            return True
            
        return False