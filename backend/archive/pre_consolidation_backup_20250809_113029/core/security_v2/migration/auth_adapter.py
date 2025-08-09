"""
Authentication adapter for migrating from old to new security system.
Provides compatibility layer for existing code.
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging

from ..authentication import (
    hash_password,
    verify_password,
    create_token_pair,
    verify_token as verify_token_v2,
    jwt_handler
)
from ..authorization import Role

logger = logging.getLogger(__name__)

class AuthAdapter:
    """
    Adapter to bridge old authentication system with new security_v2.
    Provides backward compatibility during migration.
    """
    
    def __init__(self):
        """Initialize authentication adapter."""
        self.jwt_handler = jwt_handler
        self._use_new_system = True  # Flag to control which system to use
    
    def authenticate_user(
        self,
        email: str,
        password: str,
        user_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate user using new system with old interface.
        
        Args:
            email: User email
            password: Plain text password
            user_data: User data from database (includes hashed_password, role, etc.)
            
        Returns:
            Authentication result with tokens
        """
        if not user_data:
            return None
        
        # Get hashed password from user data
        hashed_password = user_data.get('hashed_password')
        if not hashed_password:
            # Fallback to 'password' field for legacy data
            hashed_password = user_data.get('password')
        
        if not hashed_password:
            logger.error(f"No password found for user {email}")
            return None
        
        # Verify password using new system
        if not verify_password(password, hashed_password):
            logger.warning(f"Invalid password for user {email}")
            return None
        
        # Map old role to new role if needed
        user_role = self._map_role(user_data.get('role', 'viewer'))
        
        # Create tokens using new system
        access_token, refresh_token = create_token_pair(
            user_id=user_data.get('id'),
            email=email,
            role=user_role,
            additional_claims={
                'agency_id': user_data.get('agency_id'),
                'first_name': user_data.get('first_name'),
                'last_name': user_data.get('last_name')
            }
        )
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'bearer',
            'user': {
                'id': user_data.get('id'),
                'email': email,
                'role': user_role,
                'agency_id': user_data.get('agency_id'),
                'first_name': user_data.get('first_name'),
                'last_name': user_data.get('last_name')
            }
        }
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify token with backward compatibility.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Token payload or None if invalid
        """
        # Try new system first
        payload = verify_token_v2(token, "access")
        
        if payload:
            return payload
        
        # If that fails, try as refresh token
        payload = verify_token_v2(token, "refresh")
        
        return payload
    
    def create_compatible_token(
        self,
        user_id: int,
        email: str,
        role: str,
        **kwargs
    ) -> str:
        """
        Create a token that works with both old and new systems.
        
        Args:
            user_id: User ID
            email: User email
            role: User role
            **kwargs: Additional claims
            
        Returns:
            JWT access token
        """
        # Map role if needed
        mapped_role = self._map_role(role)
        
        # Create token with new system
        access_token, _ = create_token_pair(
            user_id=user_id,
            email=email,
            role=mapped_role,
            additional_claims=kwargs
        )
        
        return access_token
    
    def hash_password_compatible(self, password: str) -> str:
        """
        Hash password using new system.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return hash_password(password)
    
    def verify_password_compatible(
        self,
        plain_password: str,
        hashed_password: str
    ) -> bool:
        """
        Verify password with fallback for plain text (migration).
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed (or plain) password from database
            
        Returns:
            True if password matches
        """
        # First try as hashed password
        if hashed_password and hashed_password.startswith('$2b$'):
            return verify_password(plain_password, hashed_password)
        
        # Fallback: Check if it's plain text (for migration)
        # This should only be temporary during migration
        if plain_password == hashed_password:
            logger.warning("Plain text password detected - needs hashing!")
            return True
        
        return False
    
    def _map_role(self, old_role: str) -> str:
        """
        Map old role names to new Role enum values.
        
        Args:
            old_role: Old role name
            
        Returns:
            New role enum value
        """
        role_mapping = {
            # Direct mappings
            'super_admin': Role.SUPER_ADMIN,
            'agency_owner': Role.AGENCY_OWNER,
            'agency_admin': Role.AGENCY_ADMIN,
            'agency_user': Role.AGENCY_USER,
            'model': Role.MODEL,
            'client': Role.CLIENT,
            'viewer': Role.VIEWER,
            
            # Alternative names (legacy)
            'admin': Role.AGENCY_ADMIN,
            'user': Role.AGENCY_USER,
            'owner': Role.AGENCY_OWNER,
            'superadmin': Role.SUPER_ADMIN,
            'super-admin': Role.SUPER_ADMIN,
            
            # Default
            'default': Role.VIEWER
        }
        
        return role_mapping.get(old_role.lower(), Role.VIEWER)
    
    def migrate_session_data(self, old_session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate old session format to new format.
        
        Args:
            old_session: Old session data
            
        Returns:
            New session format
        """
        return {
            'user_id': old_session.get('user_id'),
            'created_at': old_session.get('created_at', datetime.utcnow().isoformat()),
            'last_activity': datetime.utcnow().isoformat(),
            'data': {
                'email': old_session.get('email'),
                'role': self._map_role(old_session.get('role', 'viewer')),
                'agency_id': old_session.get('agency_id')
            },
            'device_info': old_session.get('device_info', {})
        }

# Singleton instance
auth_adapter = AuthAdapter()

# Export convenience functions
def get_auth_adapter() -> AuthAdapter:
    """Get the auth adapter instance."""
    return auth_adapter

def migrate_user_authentication(
    email: str,
    password: str,
    user_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Convenience function for authenticating users during migration.
    
    Args:
        email: User email
        password: Plain text password
        user_data: User data from database
        
    Returns:
        Authentication result with tokens
    """
    return auth_adapter.authenticate_user(email, password, user_data)

def create_compatible_token(
    user_id: int,
    email: str,
    role: str,
    **kwargs
) -> str:
    """
    Create a backward-compatible token.
    
    Args:
        user_id: User ID
        email: User email
        role: User role
        **kwargs: Additional claims
        
    Returns:
        JWT access token
    """
    return auth_adapter.create_compatible_token(user_id, email, role, **kwargs)