"""
Compatibility layer for seamless transition from old to new security.
Provides drop-in replacements for old security functions.
"""
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

# Import new security components
from ..authentication import (
    hash_password as hash_password_v2,
    verify_password as verify_password_v2,
    create_token_pair,
    verify_token as verify_token_v2,
    jwt_handler
)
from ..authorization import (
    has_permission as has_permission_v2,
    Role,
    Permission,
    get_current_user as get_current_user_v2
)
from .auth_adapter import auth_adapter
from .permission_mapper import permission_mapper

logger = logging.getLogger(__name__)

# Environment variable to control which system to use
USE_NEW_SECURITY = os.getenv("USE_NEW_SECURITY", "true").lower() == "true"

def log_compatibility_usage(func_name: str):
    """Log when compatibility layer is used."""
    logger.debug(f"Compatibility layer: {func_name} called (using {'new' if USE_NEW_SECURITY else 'old'} system)")


# Authentication compatibility functions

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Drop-in replacement for old create_access_token.
    Compatible with both old and new token formats.
    """
    log_compatibility_usage("create_access_token")
    
    if USE_NEW_SECURITY:
        # Extract user info from data
        user_id = data.get("sub") or data.get("user_id")
        email = data.get("email")
        role = data.get("role", "viewer")
        
        # Map old role to new if needed
        mapped_role = permission_mapper.map_role(role)
        
        # Create token with new system
        access_token, _ = create_token_pair(
            user_id=int(user_id) if user_id else 0,
            email=email or "",
            role=mapped_role,
            additional_claims={k: v for k, v in data.items() 
                             if k not in ["sub", "user_id", "email", "role"]}
        )
        return access_token
    else:
        # Fallback to old system (if it exists)
        # This is a placeholder - implement based on your old system
        raise NotImplementedError("Old security system not available")


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Drop-in replacement for old verify_token.
    Works with both old and new token formats.
    """
    log_compatibility_usage("verify_token")
    
    if USE_NEW_SECURITY:
        return auth_adapter.verify_token(token)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def get_password_hash(password: str) -> str:
    """
    Drop-in replacement for old get_password_hash.
    """
    log_compatibility_usage("get_password_hash")
    
    if USE_NEW_SECURITY:
        return hash_password_v2(password)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Drop-in replacement for old verify_password.
    Handles both old plain text and new hashed passwords.
    """
    log_compatibility_usage("verify_password")
    
    if USE_NEW_SECURITY:
        return auth_adapter.verify_password_compatible(plain_password, hashed_password)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def authenticate_user(email: str, password: str, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Drop-in replacement for old authenticate_user.
    """
    log_compatibility_usage("authenticate_user")
    
    if USE_NEW_SECURITY:
        return auth_adapter.authenticate_user(email, password, user_data)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


# Authorization compatibility functions

def check_permission(user_role: str, permission: str, **kwargs) -> bool:
    """
    Drop-in replacement for old check_permission.
    Works with both old permission strings and new Permission enum.
    """
    log_compatibility_usage("check_permission")
    
    if USE_NEW_SECURITY:
        return permission_mapper.check_legacy_permission(user_role, permission, **kwargs)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def has_permission(user_role: str, permission: str, **kwargs) -> bool:
    """
    Alias for check_permission for compatibility.
    """
    return check_permission(user_role, permission, **kwargs)


def get_current_user(token: str) -> Optional[Dict[str, Any]]:
    """
    Drop-in replacement for old get_current_user.
    """
    log_compatibility_usage("get_current_user")
    
    if USE_NEW_SECURITY:
        payload = verify_token(token)
        if not payload:
            return None
        
        return {
            "id": int(payload.get("sub")) if payload.get("sub") else None,
            "email": payload.get("email"),
            "role": payload.get("role"),
            "agency_id": payload.get("agency_id"),
            "permissions": permission_mapper.get_role_permissions_legacy(
                payload.get("role", "viewer")
            )
        }
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def get_user_permissions(user_role: str) -> List[str]:
    """
    Drop-in replacement for old get_user_permissions.
    Returns permissions in old string format.
    """
    log_compatibility_usage("get_user_permissions")
    
    if USE_NEW_SECURITY:
        return permission_mapper.get_role_permissions_legacy(user_role)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


# Role checking compatibility functions

def is_admin(user_role: str) -> bool:
    """Check if user has admin privileges."""
    log_compatibility_usage("is_admin")
    
    if USE_NEW_SECURITY:
        mapped_role = permission_mapper.map_role(user_role)
        return mapped_role in [Role.SUPER_ADMIN, Role.AGENCY_OWNER, Role.AGENCY_ADMIN]
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def is_owner(user_role: str) -> bool:
    """Check if user is an agency owner."""
    log_compatibility_usage("is_owner")
    
    if USE_NEW_SECURITY:
        mapped_role = permission_mapper.map_role(user_role)
        return mapped_role in [Role.SUPER_ADMIN, Role.AGENCY_OWNER]
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def is_super_admin(user_role: str) -> bool:
    """Check if user is a super admin."""
    log_compatibility_usage("is_super_admin")
    
    if USE_NEW_SECURITY:
        mapped_role = permission_mapper.map_role(user_role)
        return mapped_role == Role.SUPER_ADMIN
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


# Session compatibility functions

def create_session(user_id: int, **kwargs) -> str:
    """
    Drop-in replacement for old create_session.
    """
    log_compatibility_usage("create_session")
    
    if USE_NEW_SECURITY:
        # Note: This requires session_manager to be initialized with Redis
        # For now, return a placeholder
        import secrets
        return secrets.token_urlsafe(32)
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Drop-in replacement for old get_session.
    """
    log_compatibility_usage("get_session")
    
    if USE_NEW_SECURITY:
        # Note: This requires session_manager to be initialized with Redis
        # For now, return None
        return None
    else:
        # Fallback to old system
        raise NotImplementedError("Old security system not available")


# Export all compatibility functions
__all__ = [
    # Authentication
    'create_access_token',
    'verify_token',
    'get_password_hash',
    'verify_password',
    'authenticate_user',
    
    # Authorization
    'check_permission',
    'has_permission',
    'get_current_user',
    'get_user_permissions',
    
    # Role checking
    'is_admin',
    'is_owner',
    'is_super_admin',
    
    # Sessions
    'create_session',
    'get_session',
    
    # Control flag
    'USE_NEW_SECURITY'
]