from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from core.config import settings
import secrets
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Initialize Fernet cipher for sensitive data encryption
def _get_fernet_key() -> bytes:
    """Generate a Fernet key from the secret key."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'stable_salt',  # In production, use a proper salt
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))
    return key

fernet = Fernet(_get_fernet_key())


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Add additional security claims
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow(),  # Issued at
        "nbf": datetime.utcnow(),  # Not before
        "jti": secrets.token_urlsafe(16),  # JWT ID for revocation
        "iss": "agencydark",  # Issuer
    })
    
    # Sign the token
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Add additional security claims
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow(),
        "nbf": datetime.utcnow(),
        "jti": secrets.token_urlsafe(16),
        "iss": "agencydark",
        "family": secrets.token_urlsafe(16),  # Token family for rotation
    })
    
    # Sign the token with a different key for refresh tokens
    refresh_key = hashlib.sha256((settings.SECRET_KEY + "_refresh").encode()).hexdigest()
    encoded_jwt = jwt.encode(to_encode, refresh_key, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def decode_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    try:
        # Use different keys for different token types
        if token_type == "refresh":
            key = hashlib.sha256((settings.SECRET_KEY + "_refresh").encode()).hexdigest()
        else:
            key = settings.SECRET_KEY
            
        payload = jwt.decode(
            token, 
            key, 
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": True, "verify_nbf": True}
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            return None
            
        # Verify issuer
        if payload.get("iss") != "agencydark":
            return None
            
        return payload
    except JWTError:
        return None


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def encrypt_sensitive_data(data: str) -> str:
    """Encrypt sensitive data like API keys."""
    return fernet.encrypt(data.encode()).decode()


def decrypt_sensitive_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    return fernet.decrypt(encrypted_data.encode()).decode()


def generate_token_fingerprint() -> Tuple[str, str]:
    """Generate a token fingerprint for additional security."""
    raw_fingerprint = secrets.token_bytes(32)
    fingerprint_hash = hashlib.sha256(raw_fingerprint).hexdigest()
    return base64.urlsafe_b64encode(raw_fingerprint).decode(), fingerprint_hash


def verify_token_fingerprint(raw_fingerprint: str, fingerprint_hash: str) -> bool:
    """Verify a token fingerprint."""
    try:
        decoded = base64.urlsafe_b64decode(raw_fingerprint.encode())
        return hashlib.sha256(decoded).hexdigest() == fingerprint_hash
    except:
        return False


def hash_token(token: str) -> str:
    """Hash a token for storage (e.g., for token revocation)."""
    return hashlib.sha256(token.encode()).hexdigest()