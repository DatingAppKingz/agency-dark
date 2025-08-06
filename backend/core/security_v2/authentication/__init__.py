"""
Authentication module.
Handles password hashing, JWT tokens, and session management.
"""

from .password_handler import (
    hash_password,
    verify_password,
    validate_password,
    generate_secure_password,
    password_handler
)

from .jwt_handler import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_token,
    get_current_user_id,
    refresh_access_token,
    jwt_handler
)

from .session_manager import (
    session_manager,
    init_session_manager
)

__all__ = [
    # Password handling
    'hash_password',
    'verify_password',
    'validate_password',
    'generate_secure_password',
    'password_handler',
    
    # JWT handling
    'create_access_token',
    'create_refresh_token',
    'create_token_pair',
    'decode_token',
    'verify_token',
    'get_current_user_id',
    'refresh_access_token',
    'jwt_handler',
    
    # Session management
    'session_manager',
    'init_session_manager'
]