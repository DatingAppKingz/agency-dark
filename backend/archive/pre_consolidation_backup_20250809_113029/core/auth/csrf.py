"""
CSRF (Cross-Site Request Forgery) protection implementation.

This module provides CSRF protection using the double-submit cookie pattern
combined with custom headers for maximum security.
"""

import secrets
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from fastapi import Request, Response, HTTPException, status
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# CSRF token configuration
CSRF_TOKEN_LENGTH = 32  # Length of the random token
CSRF_COOKIE_NAME = "__Secure-CSRF-Token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_FORM_FIELD_NAME = "csrf_token"
CSRF_TOKEN_EXPIRY_HOURS = 24  # Token expires after 24 hours

# Safe HTTP methods that don't require CSRF protection
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFProtection:
    """CSRF protection manager using double-submit cookie pattern."""
    
    def __init__(self):
        """Initialize CSRF protection with secret key."""
        self.secret_key = settings.SECRET_KEY.encode()
    
    def generate_csrf_token(self) -> Tuple[str, str]:
        """
        Generate a new CSRF token pair.
        
        Returns:
            Tuple of (token_for_cookie, token_for_form)
        """
        # Generate random token
        random_token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
        
        # Create timestamp
        timestamp = int(datetime.utcnow().timestamp())
        
        # Create token with timestamp
        token_data = f"{random_token}:{timestamp}"
        
        # Sign the token
        signature = self._sign_token(token_data)
        
        # Combine token and signature
        csrf_token = f"{token_data}:{signature}"
        
        return csrf_token, csrf_token
    
    def _sign_token(self, token_data: str) -> str:
        """Sign token data with HMAC."""
        return hmac.new(
            self.secret_key,
            token_data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def validate_csrf_token(self, token: str) -> bool:
        """
        Validate a CSRF token.
        
        Args:
            token: The CSRF token to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Split token into parts
            parts = token.split(":")
            if len(parts) != 3:
                return False
            
            random_token, timestamp_str, signature = parts
            
            # Verify signature
            token_data = f"{random_token}:{timestamp_str}"
            expected_signature = self._sign_token(token_data)
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("CSRF token signature mismatch")
                return False
            
            # Check timestamp
            timestamp = int(timestamp_str)
            current_time = int(datetime.utcnow().timestamp())
            
            # Check if token has expired
            if current_time - timestamp > (CSRF_TOKEN_EXPIRY_HOURS * 3600):
                logger.warning("CSRF token expired")
                return False
            
            return True
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"CSRF token validation error: {e}")
            return False
    
    def set_csrf_cookie(self, response: Response, token: str) -> None:
        """
        Set CSRF token in cookie.
        
        Args:
            response: FastAPI response object
            token: CSRF token to set
        """
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            max_age=CSRF_TOKEN_EXPIRY_HOURS * 3600,
            secure=settings.ENVIRONMENT == "production",
            httponly=False,  # Must be readable by JavaScript
            samesite="strict" if settings.ENVIRONMENT == "production" else "lax",
            path="/"
        )
    
    def get_csrf_token_from_request(self, request: Request) -> Optional[str]:
        """
        Extract CSRF token from request (header or form).
        
        Args:
            request: FastAPI request object
            
        Returns:
            CSRF token if found, None otherwise
        """
        # First check header
        token = request.headers.get(CSRF_HEADER_NAME)
        if token:
            return token
        
        # Then check form data if content type is form
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            # This would need to be extracted from form data
            # For now, we'll only support header-based CSRF tokens
            pass
        
        return None
    
    def get_csrf_cookie(self, request: Request) -> Optional[str]:
        """
        Get CSRF token from cookie.
        
        Args:
            request: FastAPI request object
            
        Returns:
            CSRF token if found, None otherwise
        """
        return request.cookies.get(CSRF_COOKIE_NAME)
    
    async def verify_csrf_token(self, request: Request) -> bool:
        """
        Verify CSRF token in request matches cookie.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if CSRF token is valid
            
        Raises:
            HTTPException: If CSRF validation fails
        """
        # Skip CSRF check for safe methods
        if request.method in SAFE_METHODS:
            return True
        
        # Skip CSRF check for API endpoints that use API keys
        if request.url.path.startswith("/api/v1/external"):
            return True
        
        # Get token from cookie
        cookie_token = self.get_csrf_cookie(request)
        if not cookie_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF cookie not found"
            )
        
        # Get token from request
        request_token = self.get_csrf_token_from_request(request)
        if not request_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token not provided in request"
            )
        
        # Validate token format and signature
        if not self.validate_csrf_token(cookie_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF cookie"
            )
        
        # Compare tokens
        if not hmac.compare_digest(cookie_token, request_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token mismatch"
            )
        
        return True


# Global CSRF protection instance
csrf_protection = CSRFProtection()


async def verify_csrf_token(request: Request) -> None:
    """
    Dependency to verify CSRF token.
    
    Use this in your route dependencies:
    ```python
    @router.post("/sensitive-action", dependencies=[Depends(verify_csrf_token)])
    async def sensitive_action():
        ...
    ```
    """
    await csrf_protection.verify_csrf_token(request)


def generate_csrf_token(response: Response) -> str:
    """
    Generate and set a new CSRF token.
    
    Args:
        response: FastAPI response object
        
    Returns:
        The generated CSRF token
    """
    token, _ = csrf_protection.generate_csrf_token()
    csrf_protection.set_csrf_cookie(response, token)
    return token