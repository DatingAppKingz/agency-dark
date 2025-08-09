"""
Secure API key generation and management.
"""
import secrets
import hashlib
import base64
from typing import Tuple, Optional
from datetime import datetime, timedelta
import re

from core.logger import get_logger

logger = get_logger(__name__)


class APIKeyGenerator:
    """Generate and validate secure API keys."""
    
    # Key format: prefix_randomdata
    KEY_PREFIX_LENGTH = 8
    KEY_RANDOM_LENGTH = 32
    KEY_PATTERN = re.compile(r'^[a-zA-Z0-9]{8}_[a-zA-Z0-9]{32}$')
    
    # Prefixes for different key types
    PREFIXES = {
        "live": "pk_live_",  # Production keys
        "test": "pk_test_",  # Test keys
        "webhook": "whk_sec_",  # Webhook secrets
        "restricted": "rk_res_",  # Restricted keys
    }
    
    @classmethod
    def generate_key(cls, key_type: str = "live") -> Tuple[str, str, str]:
        """
        Generate a new API key.
        
        Args:
            key_type: Type of key to generate (live, test, webhook, restricted)
            
        Returns:
            Tuple of (full_key, key_prefix, key_hash)
        """
        # Get prefix
        prefix = cls.PREFIXES.get(key_type, "pk_live_")
        
        # Generate random part
        random_bytes = secrets.token_bytes(cls.KEY_RANDOM_LENGTH)
        random_part = base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')
        
        # Ensure proper length
        random_part = random_part[:cls.KEY_RANDOM_LENGTH]
        
        # Combine
        full_key = f"{prefix}{random_part}"
        
        # Extract prefix for storage
        key_prefix = full_key[:cls.KEY_PREFIX_LENGTH]
        
        # Hash the key for storage
        key_hash = cls.hash_key(full_key)
        
        logger.info(f"Generated new {key_type} API key with prefix: {key_prefix}")
        
        return full_key, key_prefix, key_hash
    
    @classmethod
    def hash_key(cls, key: str) -> str:
        """
        Hash an API key for secure storage.
        
        Args:
            key: The API key to hash
            
        Returns:
            Hashed key
        """
        # Use SHA-256 with salt
        salt = "agency_dark_api_key_salt_v1"  # In production, use environment variable
        salted_key = f"{salt}{key}"
        
        return hashlib.sha256(salted_key.encode()).hexdigest()
    
    @classmethod
    def validate_format(cls, key: str) -> bool:
        """
        Validate API key format.
        
        Args:
            key: The API key to validate
            
        Returns:
            True if format is valid
        """
        if not key:
            return False
        
        # Check if it starts with a known prefix
        valid_prefix = any(key.startswith(prefix) for prefix in cls.PREFIXES.values())
        if not valid_prefix:
            return False
        
        # Check length
        if len(key) < cls.KEY_PREFIX_LENGTH + cls.KEY_RANDOM_LENGTH:
            return False
        
        # Check characters (alphanumeric, underscore, hyphen)
        if not re.match(r'^[a-zA-Z0-9_-]+$', key):
            return False
        
        return True
    
    @classmethod
    def extract_prefix(cls, key: str) -> str:
        """Extract the prefix from an API key."""
        return key[:cls.KEY_PREFIX_LENGTH] if len(key) >= cls.KEY_PREFIX_LENGTH else ""
    
    @classmethod
    def generate_webhook_secret(cls) -> str:
        """Generate a webhook signing secret."""
        full_key, _, _ = cls.generate_key("webhook")
        return full_key
    
    @classmethod
    def rotate_key(cls, old_key_type: str = "live") -> Tuple[str, str, str]:
        """
        Generate a new key for rotation.
        
        Args:
            old_key_type: Type of the key being rotated
            
        Returns:
            New key tuple
        """
        new_key, prefix, hash = cls.generate_key(old_key_type)
        logger.info(f"Generated rotation key with prefix: {prefix}")
        return new_key, prefix, hash


class APIKeyValidator:
    """Validate API keys and check permissions."""
    
    @staticmethod
    def validate_scope_combination(scopes: list) -> Tuple[bool, Optional[str]]:
        """
        Validate that scope combination is allowed.
        
        Args:
            scopes: List of scopes to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for conflicting scopes
        read_scopes = [s for s in scopes if s.startswith("read:")]
        write_scopes = [s for s in scopes if s.startswith("write:")]
        admin_scopes = [s for s in scopes if s.startswith("admin:")]
        
        # Admin scopes should not be mixed with limited scopes
        if admin_scopes and (read_scopes or write_scopes):
            if "admin:system" in admin_scopes:
                return False, "System admin scope cannot be combined with other scopes"
        
        # Check for duplicate resources
        resources = set()
        for scope in scopes:
            if ":" in scope:
                _, resource = scope.split(":", 1)
                if resource in resources:
                    return False, f"Duplicate resource scope: {resource}"
                resources.add(resource)
        
        return True, None
    
    @staticmethod
    def validate_ip_restrictions(allowed_ips: list) -> Tuple[bool, Optional[str]]:
        """
        Validate IP address restrictions.
        
        Args:
            allowed_ips: List of IP addresses or CIDR ranges
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        import ipaddress
        
        for ip in allowed_ips:
            try:
                # Try to parse as IP address or network
                if '/' in ip:
                    ipaddress.ip_network(ip)
                else:
                    ipaddress.ip_address(ip)
            except ValueError:
                return False, f"Invalid IP address or CIDR: {ip}"
        
        return True, None
    
    @staticmethod
    def validate_rate_limits(
        per_minute: int, 
        per_hour: int, 
        per_day: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate rate limit configuration.
        
        Args:
            per_minute: Requests per minute
            per_hour: Requests per hour
            per_day: Requests per day
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check reasonable limits
        if per_minute <= 0 or per_hour <= 0 or per_day <= 0:
            return False, "Rate limits must be positive"
        
        # Check consistency
        if per_minute * 60 < per_hour:
            return False, "Hourly limit exceeds minute limit * 60"
        
        if per_hour * 24 < per_day:
            return False, "Daily limit exceeds hourly limit * 24"
        
        # Check maximum limits
        if per_minute > 1000:
            return False, "Per-minute limit too high (max: 1000)"
        
        if per_day > 1000000:
            return False, "Per-day limit too high (max: 1,000,000)"
        
        return True, None
    
    @staticmethod
    def calculate_expiration(validity_days: Optional[int] = None) -> Optional[datetime]:
        """
        Calculate expiration date for an API key.
        
        Args:
            validity_days: Number of days the key is valid (None for no expiration)
            
        Returns:
            Expiration datetime or None
        """
        if validity_days is None:
            return None
        
        if validity_days <= 0:
            raise ValueError("Validity days must be positive")
        
        if validity_days > 365:
            logger.warning(f"API key validity set to {validity_days} days (>1 year)")
        
        return datetime.utcnow() + timedelta(days=validity_days)


class APIKeyScopeValidator:
    """Validate scope-based permissions for API keys."""
    
    # Define scope hierarchy
    SCOPE_HIERARCHY = {
        "admin:system": ["admin:agency", "admin:users", "write:*", "read:*"],
        "admin:agency": ["write:models", "write:users", "read:*"],
        "admin:users": ["write:users", "read:users"],
        "write:conversations": ["read:conversations"],
        "write:models": ["read:models"],
        "write:users": ["read:users"],
        "write:financial": ["read:financial"],
    }
    
    @classmethod
    def expand_scopes(cls, scopes: list) -> set:
        """
        Expand scopes to include implied permissions.
        
        Args:
            scopes: List of explicit scopes
            
        Returns:
            Set of all scopes including implied ones
        """
        expanded = set(scopes)
        
        for scope in scopes:
            # Add implied scopes
            if scope in cls.SCOPE_HIERARCHY:
                for implied in cls.SCOPE_HIERARCHY[scope]:
                    if implied.endswith(":*"):
                        # Expand wildcard
                        prefix = implied[:-2]
                        expanded.update([
                            f"{prefix}:conversations",
                            f"{prefix}:models",
                            f"{prefix}:users",
                            f"{prefix}:analytics",
                            f"{prefix}:financial",
                        ])
                    else:
                        expanded.add(implied)
        
        return expanded
    
    @classmethod
    def check_scope_permission(cls, required_scope: str, available_scopes: list) -> bool:
        """
        Check if required scope is satisfied by available scopes.
        
        Args:
            required_scope: The scope required for an operation
            available_scopes: List of scopes the key has
            
        Returns:
            True if permission is granted
        """
        # Expand available scopes
        expanded = cls.expand_scopes(available_scopes)
        
        # Check direct match
        if required_scope in expanded:
            return True
        
        # Check wildcard matches
        if "admin:system" in expanded:
            return True  # System admin has all permissions
        
        # Check resource wildcards
        if ":" in required_scope:
            action, resource = required_scope.split(":", 1)
            if f"{action}:*" in expanded:
                return True
        
        return False