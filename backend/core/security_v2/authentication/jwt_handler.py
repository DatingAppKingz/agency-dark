"""
JWT token handling with refresh token support.
Manages access and refresh tokens for authentication.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
import secrets
from jose import JWTError, jwt

from ..config import security_config

class JWTHandler:
    """Handles JWT token generation, validation, and refresh."""
    
    def __init__(self):
        """Initialize JWT handler with configuration."""
        self.secret_key = security_config.JWT_SECRET_KEY
        self.algorithm = security_config.JWT_ALGORITHM
        self.access_token_expire_minutes = security_config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = security_config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.
        
        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=self.access_token_expire_minutes
            )
        
        to_encode.update({
            "exp": expire,
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "jti": secrets.token_hex(16)  # JWT ID for tracking
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT refresh token.
        
        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=self.refresh_token_expire_days
            )
        
        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "iat": datetime.now(timezone.utc),
            "jti": secrets.token_hex(16)
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def create_token_pair(
        self, 
        user_id: int, 
        email: str,
        role: Optional[str] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Create both access and refresh tokens.
        
        Args:
            user_id: User ID to encode
            email: User email
            role: User role
            additional_claims: Additional data to include
            
        Returns:
            Tuple of (access_token, refresh_token)
        """
        token_data = {
            "sub": str(user_id),  # Subject (user ID)
            "email": email,
        }
        
        if role:
            token_data["role"] = role
        
        if additional_claims:
            token_data.update(additional_claims)
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token({"sub": str(user_id)})
        
        return access_token, refresh_token
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            return payload
        except JWTError:
            return None
    
    def verify_token(self, token: str, expected_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify a token and check its type.
        
        Args:
            token: JWT token to verify
            expected_type: Expected token type (access or refresh)
            
        Returns:
            Token payload if valid, None otherwise
        """
        payload = self.decode_token(token)
        
        if not payload:
            return None
        
        # Check token type
        if payload.get("type") != expected_type:
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp:
            if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                return None
        
        return payload
    
    def get_current_user_id(self, token: str) -> Optional[int]:
        """
        Extract user ID from access token.
        
        Args:
            token: JWT access token
            
        Returns:
            User ID or None if invalid
        """
        payload = self.verify_token(token, "access")
        if payload:
            try:
                return int(payload.get("sub"))
            except (TypeError, ValueError):
                return None
        return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Generate new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token or None if refresh token invalid
        """
        payload = self.verify_token(refresh_token, "refresh")
        if not payload:
            return None
        
        # Create new access token with user ID
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        new_token_data = {"sub": user_id}
        return self.create_access_token(new_token_data)
    
    def revoke_token(self, token: str, token_id: str) -> bool:
        """
        Mark a token as revoked (requires external storage).
        This is a placeholder for token revocation logic.
        
        Args:
            token: Token to revoke
            token_id: JWT ID (jti) from token
            
        Returns:
            True if successfully revoked
        """
        # TODO: Implement token revocation with Redis
        # Store token_id in a blacklist with expiration
        return True
    
    def is_token_revoked(self, token_id: str) -> bool:
        """
        Check if a token has been revoked.
        
        Args:
            token_id: JWT ID (jti) to check
            
        Returns:
            True if token is revoked
        """
        # TODO: Check Redis blacklist
        return False

# Create singleton instance
jwt_handler = JWTHandler()

# Export convenience functions
create_access_token = jwt_handler.create_access_token
create_refresh_token = jwt_handler.create_refresh_token
create_token_pair = jwt_handler.create_token_pair
decode_token = jwt_handler.decode_token
verify_token = jwt_handler.verify_token
get_current_user_id = jwt_handler.get_current_user_id
refresh_access_token = jwt_handler.refresh_access_token