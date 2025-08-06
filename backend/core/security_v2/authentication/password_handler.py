"""
Password handling with bcrypt hashing.
Ensures all passwords are properly hashed before storage.
"""
from passlib.context import CryptContext
from typing import Optional, Tuple
import secrets
import string
import re

from ..config import security_config

class PasswordHandler:
    """Handles password hashing, verification, and validation."""
    
    def __init__(self):
        """Initialize password handler with bcrypt."""
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=security_config.PASSWORD_BCRYPT_ROUNDS
        )
        
        # Password policy from config
        self.min_length = security_config.PASSWORD_MIN_LENGTH
        self.require_uppercase = security_config.PASSWORD_REQUIRE_UPPERCASE
        self.require_lowercase = security_config.PASSWORD_REQUIRE_LOWERCASE
        self.require_numbers = security_config.PASSWORD_REQUIRE_NUMBERS
        self.require_special = security_config.PASSWORD_REQUIRE_SPECIAL
    
    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches, False otherwise
        """
        if not plain_password or not hashed_password:
            return False
        
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # Handle cases where hashed_password is not a valid hash
            return False
    
    def validate_password_strength(self, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validate password meets security requirements.
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not password:
            return False, "Password cannot be empty"
        
        if len(password) < self.min_length:
            return False, f"Password must be at least {self.min_length} characters long"
        
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if self.require_lowercase and not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if self.require_numbers and not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        # Check for common weak passwords
        weak_passwords = ['password', '12345678', 'qwerty', 'admin', 'letmein']
        if password.lower() in weak_passwords:
            return False, "Password is too common. Please choose a stronger password"
        
        return True, None
    
    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate a cryptographically secure random password.
        
        Args:
            length: Length of password to generate
            
        Returns:
            Secure random password
        """
        if length < self.min_length:
            length = self.min_length
        
        # Character sets
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        special = "!@#$%^&*(),.?\":{}|<>"
        
        # Ensure at least one of each required type
        password_chars = []
        
        if self.require_lowercase:
            password_chars.append(secrets.choice(lowercase))
        if self.require_uppercase:
            password_chars.append(secrets.choice(uppercase))
        if self.require_numbers:
            password_chars.append(secrets.choice(digits))
        if self.require_special:
            password_chars.append(secrets.choice(special))
        
        # Fill remaining length with random characters from all sets
        all_chars = lowercase + uppercase + digits + special
        for _ in range(length - len(password_chars)):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle to avoid predictable patterns
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    def needs_rehash(self, hashed_password: str) -> bool:
        """
        Check if a password hash needs to be updated.
        Useful when changing hashing algorithms or parameters.
        
        Args:
            hashed_password: Current password hash
            
        Returns:
            True if rehashing is recommended
        """
        return self.pwd_context.needs_update(hashed_password)
    
    def generate_reset_token(self) -> str:
        """Generate a secure password reset token."""
        return secrets.token_urlsafe(32)

# Create singleton instance
password_handler = PasswordHandler()

# Export convenience functions
hash_password = password_handler.hash_password
verify_password = password_handler.verify_password
validate_password = password_handler.validate_password_strength
generate_secure_password = password_handler.generate_secure_password