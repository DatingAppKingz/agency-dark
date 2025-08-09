"""
Authentication and Authorization Module

This module provides enhanced security features for the AgencyDark platform.
"""
from .token_blacklist import token_blacklist_service, TokenBlacklist
from .session_manager import session_manager

# Import get_current_user from the main auth endpoint
# TODO: Fix circular import - get_current_user should be defined in core/auth or core/dependencies
# from api.v1.endpoints.auth import get_current_user  # This would cause circular import

__all__ = [
    "token_blacklist_service",
    "TokenBlacklist", 
    "session_manager"
    # "get_current_user"  # Removed until circular import is resolved
]