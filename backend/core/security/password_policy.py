"""
Enhanced password policies and 2FA implementation
"""
import re
import secrets
import string
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64
from passlib.context import CryptContext
from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text

from core.database import Base
from core.config import settings
from core.logging import logger
from core.redis import redis_client


# Password hashing context
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    default="argon2",
    argon2__rounds=4,
    argon2__memory_cost=65536,
    argon2__parallelism=2,
    bcrypt__rounds=12,
    deprecated="bcrypt"
)


class PasswordPolicy:
    """Enhanced password policy enforcement"""
    
    def __init__(
        self,
        min_length: int = 12,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_numbers: bool = True,
        require_special: bool = True,
        min_unique_chars: int = 8,
        prevent_common_passwords: bool = True,
        prevent_user_info: bool = True,
        password_history: int = 5,
        max_age_days: int = 90,
        min_age_hours: int = 24
    ):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_numbers = require_numbers
        self.require_special = require_special
        self.min_unique_chars = min_unique_chars
        self.prevent_common_passwords = prevent_common_passwords
        self.prevent_user_info = prevent_user_info
        self.password_history = password_history
        self.max_age_days = max_age_days
        self.min_age_hours = min_age_hours
        
        # Load common passwords list
        self.common_passwords = self._load_common_passwords()
    
    def validate_password(
        self,
        password: str,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        old_passwords: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate password against policy
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Length check
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        
        # Character requirements
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.require_numbers and not re.search(r"\d", password):
            errors.append("Password must contain at least one number")
        
        if self.require_special and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("Password must contain at least one special character")
        
        # Unique characters check
        unique_chars = len(set(password))
        if unique_chars < self.min_unique_chars:
            errors.append(f"Password must contain at least {self.min_unique_chars} unique characters")
        
        # Common passwords check
        if self.prevent_common_passwords and password.lower() in self.common_passwords:
            errors.append("Password is too common. Please choose a more unique password")
        
        # User info check
        if self.prevent_user_info:
            if user_email and user_email.split('@')[0].lower() in password.lower():
                errors.append("Password cannot contain your email username")
            
            if user_name and user_name.lower() in password.lower():
                errors.append("Password cannot contain your name")
        
        # Password history check
        if old_passwords and self.password_history > 0:
            for old_pwd in old_passwords[-self.password_history:]:
                if pwd_context.verify(password, old_pwd):
                    errors.append(f"Password cannot be the same as your last {self.password_history} passwords")
                    break
        
        # Pattern checks
        if self._has_sequential_chars(password):
            errors.append("Password cannot contain sequential characters (e.g., abc, 123)")
        
        if self._has_repeated_chars(password):
            errors.append("Password cannot contain repeated characters (e.g., aaa, 111)")
        
        return len(errors) == 0, errors
    
    def generate_strong_password(self, length: int = 16) -> str:
        """Generate a strong password that meets policy requirements"""
        # Ensure we have all required character types
        password_chars = []
        
        if self.require_uppercase:
            password_chars.append(secrets.choice(string.ascii_uppercase))
        if self.require_lowercase:
            password_chars.append(secrets.choice(string.ascii_lowercase))
        if self.require_numbers:
            password_chars.append(secrets.choice(string.digits))
        if self.require_special:
            password_chars.append(secrets.choice("!@#$%^&*(),.?\":{}|<>"))
        
        # Fill the rest with random characters
        all_chars = string.ascii_letters + string.digits + "!@#$%^&*(),.?\":{}|<>"
        remaining_length = max(length - len(password_chars), self.min_length - len(password_chars))
        
        for _ in range(remaining_length):
            password_chars.append(secrets.choice(all_chars))
        
        # Shuffle the password
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    def _load_common_passwords(self) -> set:
        """Load list of common passwords"""
        # In production, load from a file or database
        # This is a simplified example
        return {
            "password", "123456", "password123", "admin", "letmein",
            "qwerty", "123456789", "12345678", "12345", "1234567",
            "welcome", "monkey", "dragon", "baseball", "football",
            "abc123", "password1", "123123", "admin123", "root"
        }
    
    def _has_sequential_chars(self, password: str) -> bool:
        """Check for sequential characters"""
        sequences = [
            "abcdefghijklmnopqrstuvwxyz",
            "0123456789",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm"
        ]
        
        password_lower = password.lower()
        for seq in sequences:
            for i in range(len(seq) - 2):
                if seq[i:i+3] in password_lower or seq[i:i+3][::-1] in password_lower:
                    return True
        
        return False
    
    def _has_repeated_chars(self, password: str) -> bool:
        """Check for repeated characters"""
        return bool(re.search(r"(.)\1{2,}", password))


class PasswordHistory(Base):
    """Password history tracking"""
    __tablename__ = "password_history"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(PG_UUID(as_uuid=True), nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TwoFactorAuth(Base):
    """Two-factor authentication settings"""
    __tablename__ = "two_factor_auth"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    
    # TOTP settings
    totp_secret = Column(String)
    totp_enabled = Column(Boolean, default=False)
    totp_verified = Column(Boolean, default=False)
    
    # Backup codes
    backup_codes = Column(JSON, default=[])
    backup_codes_generated_at = Column(DateTime)
    
    # SMS settings
    sms_enabled = Column(Boolean, default=False)
    sms_phone_number = Column(String)
    sms_verified = Column(Boolean, default=False)
    
    # Email settings
    email_enabled = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    
    # Recovery settings
    recovery_email = Column(String)
    recovery_questions = Column(JSON, default={})
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime)
    failed_attempts = Column(Integer, default=0)


class TwoFactorService:
    """Service for managing two-factor authentication"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.issuer_name = getattr(settings, 'APP_NAME', 'MyApp')
    
    async def setup_totp(self, user_id: str, user_email: str) -> Dict[str, Any]:
        """Setup TOTP for a user"""
        # Generate secret
        secret = pyotp.random_base32()
        
        # Get or create 2FA settings
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa:
            two_fa = TwoFactorAuth(user_id=user_id)
            self.db.add(two_fa)
        
        two_fa.totp_secret = secret
        two_fa.totp_enabled = True
        two_fa.totp_verified = False
        
        await self.db.commit()
        
        # Generate provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=self.issuer_name
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        qr_code_base64 = base64.b64encode(buf.getvalue()).decode()
        
        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code": f"data:image/png;base64,{qr_code_base64}"
        }
    
    async def verify_totp_setup(self, user_id: str, token: str) -> bool:
        """Verify TOTP setup with initial token"""
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa or not two_fa.totp_secret:
            return False
        
        totp = pyotp.TOTP(two_fa.totp_secret)
        if totp.verify(token, valid_window=1):
            two_fa.totp_verified = True
            two_fa.updated_at = datetime.utcnow()
            
            # Generate backup codes
            backup_codes = await self.generate_backup_codes(user_id)
            
            await self.db.commit()
            return True
        
        return False
    
    async def verify_totp(self, user_id: str, token: str) -> bool:
        """Verify TOTP token"""
        # Check rate limiting
        rate_limit_key = f"2fa_attempts:{user_id}"
        attempts = await redis_client.incr(rate_limit_key)
        if attempts == 1:
            await redis_client.expire(rate_limit_key, 300)  # 5 minutes
        
        if attempts > 5:
            logger.warning(f"Too many 2FA attempts for user {user_id}")
            return False
        
        # Get 2FA settings
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa or not two_fa.totp_enabled or not two_fa.totp_secret:
            return False
        
        # Verify token
        totp = pyotp.TOTP(two_fa.totp_secret)
        if totp.verify(token, valid_window=1):
            # Update last used
            two_fa.last_used_at = datetime.utcnow()
            two_fa.failed_attempts = 0
            await self.db.commit()
            
            # Clear rate limiting
            await redis_client.delete(rate_limit_key)
            
            return True
        
        # Increment failed attempts
        two_fa.failed_attempts += 1
        await self.db.commit()
        
        return False
    
    async def generate_backup_codes(self, user_id: str, count: int = 10) -> List[str]:
        """Generate backup codes"""
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa:
            two_fa = TwoFactorAuth(user_id=user_id)
            self.db.add(two_fa)
        
        # Generate codes
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.digits) for _ in range(8))
            codes.append(code)
        
        # Hash and store codes
        hashed_codes = [pwd_context.hash(code) for code in codes]
        two_fa.backup_codes = hashed_codes
        two_fa.backup_codes_generated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return codes
    
    async def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify and consume a backup code"""
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa or not two_fa.backup_codes:
            return False
        
        # Check each code
        for i, hashed_code in enumerate(two_fa.backup_codes):
            if pwd_context.verify(code, hashed_code):
                # Remove used code
                two_fa.backup_codes.pop(i)
                two_fa.last_used_at = datetime.utcnow()
                await self.db.commit()
                
                logger.info(f"Backup code used for user {user_id}")
                return True
        
        return False
    
    async def disable_2fa(self, user_id: str) -> bool:
        """Disable all 2FA methods"""
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if two_fa:
            two_fa.totp_enabled = False
            two_fa.totp_secret = None
            two_fa.sms_enabled = False
            two_fa.email_enabled = False
            two_fa.backup_codes = []
            two_fa.updated_at = datetime.utcnow()
            
            await self.db.commit()
            return True
        
        return False
    
    async def is_2fa_enabled(self, user_id: str) -> bool:
        """Check if any 2FA method is enabled"""
        result = await self.db.execute(
            select(TwoFactorAuth).where(TwoFactorAuth.user_id == user_id)
        )
        two_fa = result.scalar_one_or_none()
        
        if not two_fa:
            return False
        
        return any([
            two_fa.totp_enabled and two_fa.totp_verified,
            two_fa.sms_enabled and two_fa.sms_verified,
            two_fa.email_enabled and two_fa.email_verified
        ])


# Password utility functions
def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """Check if password hash needs to be updated"""
    return pwd_context.needs_update(hashed_password)