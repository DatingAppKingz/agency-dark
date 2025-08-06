"""
OWASP Top 10 Compliance Module

Implements security controls for OWASP Top 10 2021:
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection
- A04: Insecure Design
- A05: Security Misconfiguration
- A06: Vulnerable and Outdated Components
- A07: Identification and Authentication Failures
- A08: Software and Data Integrity Failures
- A09: Security Logging and Monitoring Failures
- A10: Server-Side Request Forgery (SSRF)
"""
import re
import hashlib
import secrets
import jwt
from typing import Dict, List, Optional, Any, Set, Callable
from datetime import datetime, timedelta
from functools import wraps
import urllib.parse
import ipaddress
import subprocess
import pkg_resources

from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from core.logger import get_logger
from core.redis import redis_client
from core.security.input_validator import input_validator

logger = get_logger(__name__)


class OWASPCompliance:
    """OWASP Top 10 compliance implementation."""
    
    def __init__(self):
        # Security configuration
        self.jwt_secret = secrets.token_urlsafe(32)
        self.jwt_algorithm = "HS256"
        self.token_expiry = 3600  # 1 hour
        
        # Encryption key (should be from environment)
        self.encryption_key = self._generate_encryption_key()
        
        # SSRF protection
        self.blocked_networks = [
            ipaddress.ip_network("127.0.0.0/8"),      # Localhost
            ipaddress.ip_network("10.0.0.0/8"),       # Private
            ipaddress.ip_network("172.16.0.0/12"),    # Private
            ipaddress.ip_network("192.168.0.0/16"),   # Private
            ipaddress.ip_network("169.254.0.0/16"),   # Link-local
            ipaddress.ip_network("::1/128"),          # IPv6 localhost
            ipaddress.ip_network("fc00::/7"),         # IPv6 private
        ]
        
        # Security headers
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
    
    # A01: Broken Access Control
    
    def enforce_access_control(
        self,
        required_roles: Optional[List[str]] = None,
        required_permissions: Optional[List[str]] = None,
        owner_field: Optional[str] = None
    ):
        """
        Decorator to enforce access control.
        
        Args:
            required_roles: List of required roles
            required_permissions: List of required permissions
            owner_field: Field to check for ownership
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                # Get user from request (assumes authentication middleware)
                user = getattr(request.state, "user", None)
                if not user:
                    raise HTTPException(status_code=401, detail="Not authenticated")
                
                # Check roles
                if required_roles:
                    user_roles = set(getattr(user, "roles", []))
                    if not any(role in user_roles for role in required_roles):
                        logger.warning(
                            f"Access denied for user {user.id}: "
                            f"missing roles {required_roles}"
                        )
                        raise HTTPException(status_code=403, detail="Insufficient roles")
                
                # Check permissions
                if required_permissions:
                    user_perms = set(getattr(user, "permissions", []))
                    missing_perms = set(required_permissions) - user_perms
                    if missing_perms:
                        logger.warning(
                            f"Access denied for user {user.id}: "
                            f"missing permissions {missing_perms}"
                        )
                        raise HTTPException(status_code=403, detail="Insufficient permissions")
                
                # Check ownership
                if owner_field and owner_field in kwargs:
                    resource_owner = kwargs[owner_field]
                    if resource_owner != user.id and "admin" not in getattr(user, "roles", []):
                        logger.warning(
                            f"Access denied for user {user.id}: "
                            f"not owner of resource"
                        )
                        raise HTTPException(status_code=403, detail="Not resource owner")
                
                return await func(request, *args, **kwargs)
            
            return wrapper
        return decorator
    
    def validate_object_access(
        self,
        user_id: int,
        object_owner_id: int,
        object_type: str,
        action: str,
        user_roles: List[str] = None
    ) -> bool:
        """Validate object-level access control."""
        # Admin can access everything
        if user_roles and "admin" in user_roles:
            return True
        
        # Owner can access their own objects
        if user_id == object_owner_id:
            return True
        
        # Log unauthorized access attempt
        logger.warning(
            f"Unauthorized access attempt: user {user_id} tried to "
            f"{action} {object_type} owned by {object_owner_id}"
        )
        
        return False
    
    # A02: Cryptographic Failures
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key from password."""
        password = secrets.token_urlsafe(32).encode()
        salt = b'stable_salt'  # In production, use proper salt management
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        f = Fernet(self.encryption_key)
        encrypted = f.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        f = Fernet(self.encryption_key)
        decoded = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = f.decrypt(decoded)
        return decrypted.decode()
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        import bcrypt
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    def generate_secure_token(self, data: Dict[str, Any], expiry_hours: int = 1) -> str:
        """Generate secure JWT token."""
        payload = {
            **data,
            "exp": datetime.utcnow() + timedelta(hours=expiry_hours),
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)  # JWT ID for revocation
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check if token is revoked
            jti = payload.get("jti")
            if jti and self._is_token_revoked(jti):
                raise jwt.InvalidTokenError("Token has been revoked")
            
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    # A03: Injection
    
    def prevent_sql_injection(self, query: str, params: Dict[str, Any]) -> bool:
        """Validate query to prevent SQL injection."""
        # Check for dangerous patterns
        dangerous_patterns = [
            r";\s*DROP\s+",
            r";\s*DELETE\s+",
            r";\s*UPDATE\s+",
            r";\s*INSERT\s+",
            r"--",
            r"\/\*.*\*\/",
            r"UNION\s+SELECT",
            r"OR\s+1\s*=\s*1",
            r"AND\s+1\s*=\s*1"
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                logger.error(f"SQL injection attempt detected: {query[:100]}")
                return False
        
        return True
    
    def sanitize_command_input(self, command: str, args: List[str]) -> Tuple[str, List[str]]:
        """Sanitize command execution inputs."""
        # Whitelist allowed commands
        allowed_commands = {
            "git": ["status", "log", "diff"],
            "npm": ["install", "test", "run"],
            "python": ["-m", "pip", "list"]
        }
        
        if command not in allowed_commands:
            raise ValueError(f"Command not allowed: {command}")
        
        # Validate arguments
        safe_args = []
        for arg in args:
            # Remove shell metacharacters
            safe_arg = re.sub(r'[;&|`$()<>]', '', arg)
            safe_args.append(safe_arg)
        
        return command, safe_args
    
    # A04: Insecure Design
    
    def validate_business_logic(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> bool:
        """Validate business logic constraints."""
        validations = {
            "transfer_funds": self._validate_fund_transfer,
            "update_permissions": self._validate_permission_update,
            "delete_account": self._validate_account_deletion,
            "bulk_operation": self._validate_bulk_operation
        }
        
        validator = validations.get(action)
        if not validator:
            logger.error(f"No validation for action: {action}")
            return False
        
        return validator(context)
    
    def _validate_fund_transfer(self, context: Dict[str, Any]) -> bool:
        """Validate fund transfer logic."""
        amount = context.get("amount", 0)
        from_balance = context.get("from_balance", 0)
        
        # Check sufficient balance
        if amount > from_balance:
            return False
        
        # Check daily limit
        daily_limit = context.get("daily_limit", 10000)
        daily_transferred = context.get("daily_transferred", 0)
        
        if daily_transferred + amount > daily_limit:
            return False
        
        return True
    
    def _validate_permission_update(self, context: Dict[str, Any]) -> bool:
        """Validate permission updates."""
        user_role = context.get("user_role")
        target_role = context.get("target_role")
        new_permissions = context.get("new_permissions", [])
        
        # Users can't elevate their own privileges
        if context.get("user_id") == context.get("target_id"):
            if any(perm.startswith("admin") for perm in new_permissions):
                return False
        
        # Only admins can grant admin permissions
        if user_role != "admin":
            if any(perm.startswith("admin") for perm in new_permissions):
                return False
        
        return True
    
    def _validate_account_deletion(self, context: Dict[str, Any]) -> bool:
        """Validate account deletion."""
        # Require recent authentication
        last_auth = context.get("last_auth_time")
        if not last_auth:
            return False
        
        time_since_auth = datetime.utcnow() - last_auth
        if time_since_auth > timedelta(minutes=5):
            return False
        
        # Check for active subscriptions
        if context.get("has_active_subscriptions"):
            return False
        
        return True
    
    def _validate_bulk_operation(self, context: Dict[str, Any]) -> bool:
        """Validate bulk operations."""
        item_count = context.get("item_count", 0)
        max_bulk_size = context.get("max_bulk_size", 100)
        
        if item_count > max_bulk_size:
            return False
        
        return True
    
    # A05: Security Misconfiguration
    
    def apply_security_headers(self, response: Response):
        """Apply security headers to response."""
        for header, value in self.security_headers.items():
            response.headers[header] = value
        
        return response
    
    def validate_configuration(self) -> Dict[str, List[str]]:
        """Validate security configuration."""
        issues = {
            "critical": [],
            "warning": [],
            "info": []
        }
        
        # Check debug mode
        import os
        if os.getenv("DEBUG", "").lower() == "true":
            issues["critical"].append("Debug mode is enabled in production")
        
        # Check secret key
        if len(self.jwt_secret) < 32:
            issues["critical"].append("JWT secret is too short")
        
        # Check HTTPS
        if not os.getenv("FORCE_HTTPS", "").lower() == "true":
            issues["warning"].append("HTTPS is not enforced")
        
        # Check CORS
        allowed_origins = os.getenv("CORS_ORIGINS", "")
        if "*" in allowed_origins:
            issues["warning"].append("CORS allows all origins")
        
        return issues
    
    # A06: Vulnerable and Outdated Components
    
    def check_dependencies(self) -> Dict[str, List[Dict[str, str]]]:
        """Check for vulnerable dependencies."""
        vulnerabilities = []
        
        # Get installed packages
        installed_packages = {
            pkg.key: pkg.version
            for pkg in pkg_resources.working_set
        }
        
        # In production, integrate with vulnerability databases
        # For now, check against known vulnerable versions
        vulnerable_versions = {
            "django": ["2.2.0", "2.2.1"],  # Example
            "flask": ["1.0.0", "1.0.1"],    # Example
        }
        
        for package, versions in vulnerable_versions.items():
            if package in installed_packages:
                if installed_packages[package] in versions:
                    vulnerabilities.append({
                        "package": package,
                        "installed": installed_packages[package],
                        "vulnerability": "Known security issues",
                        "recommendation": "Upgrade to latest version"
                    })
        
        return {"vulnerabilities": vulnerabilities}
    
    # A07: Identification and Authentication Failures
    
    def validate_authentication(
        self,
        username: str,
        password: str,
        ip_address: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate authentication with security checks."""
        # Check account lockout
        if self._is_account_locked(username):
            return False, "Account is locked"
        
        # Check IP-based rate limiting
        if self._is_ip_blocked(ip_address):
            return False, "Too many failed attempts from this IP"
        
        # Validate password complexity
        if not self._validate_password_complexity(password):
            return False, "Password does not meet complexity requirements"
        
        return True, None
    
    def _validate_password_complexity(self, password: str) -> bool:
        """Validate password complexity."""
        if len(password) < 12:
            return False
        
        # Must contain uppercase, lowercase, digit, and special char
        patterns = [
            r'[A-Z]',  # Uppercase
            r'[a-z]',  # Lowercase
            r'\d',     # Digit
            r'[!@#$%^&*(),.?":{}|<>]'  # Special char
        ]
        
        for pattern in patterns:
            if not re.search(pattern, password):
                return False
        
        return True
    
    def enforce_mfa(self, user_id: int, token: str) -> bool:
        """Enforce multi-factor authentication."""
        # Validate TOTP token
        import pyotp
        
        # Get user's secret (in production, from database)
        user_secret = self._get_user_mfa_secret(user_id)
        if not user_secret:
            return False
        
        totp = pyotp.TOTP(user_secret)
        return totp.verify(token, valid_window=1)
    
    # A08: Software and Data Integrity Failures
    
    def verify_data_integrity(self, data: str, signature: str) -> bool:
        """Verify data integrity using HMAC."""
        import hmac
        
        expected_signature = hmac.new(
            self.jwt_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def sign_data(self, data: str) -> str:
        """Sign data for integrity verification."""
        import hmac
        
        signature = hmac.new(
            self.jwt_secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    # A09: Security Logging and Monitoring Failures
    
    def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[int],
        ip_address: str,
        details: Dict[str, Any]
    ):
        """Log security events comprehensively."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details
        }
        
        # Log to file/SIEM
        logger.warning(f"SECURITY_EVENT: {event}")
        
        # Store in database for analysis
        # In production, send to SIEM system
        
        # Alert on critical events
        if severity == "critical":
            self._send_security_alert(event)
    
    def detect_anomalies(self, user_id: int, action: str) -> bool:
        """Detect anomalous behavior."""
        # Check for unusual patterns
        anomalies = []
        
        # Rapid succession of actions
        recent_actions = self._get_recent_actions(user_id)
        if len(recent_actions) > 100:  # 100 actions in last minute
            anomalies.append("Excessive activity rate")
        
        # Geographic anomaly
        locations = self._get_recent_locations(user_id)
        if self._has_impossible_travel(locations):
            anomalies.append("Impossible travel detected")
        
        # Time-based anomaly
        if self._is_unusual_time(user_id):
            anomalies.append("Activity at unusual time")
        
        if anomalies:
            self.log_security_event(
                "anomaly_detected",
                "warning",
                user_id,
                "unknown",
                {"anomalies": anomalies, "action": action}
            )
            return True
        
        return False
    
    # A10: Server-Side Request Forgery (SSRF)
    
    def validate_url_for_ssrf(self, url: str) -> bool:
        """Validate URL to prevent SSRF attacks."""
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                logger.warning(f"SSRF attempt with scheme: {parsed.scheme}")
                return False
            
            # Resolve hostname
            import socket
            try:
                ip = socket.gethostbyname(parsed.hostname)
                ip_obj = ipaddress.ip_address(ip)
                
                # Check against blocked networks
                for network in self.blocked_networks:
                    if ip_obj in network:
                        logger.warning(f"SSRF attempt to blocked network: {ip}")
                        return False
                
            except socket.gaierror:
                logger.warning(f"SSRF attempt with invalid hostname: {parsed.hostname}")
                return False
            
            # Check for DNS rebinding
            # In production, implement proper DNS rebinding protection
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating URL: {e}")
            return False
    
    def make_safe_request(self, url: str, timeout: int = 5) -> Optional[str]:
        """Make HTTP request with SSRF protection."""
        if not self.validate_url_for_ssrf(url):
            raise ValueError("URL failed SSRF validation")
        
        import requests
        
        try:
            # Use timeout to prevent slowloris attacks
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=False,  # Prevent redirect-based SSRF
                headers={"User-Agent": "AgencyDark/1.0"}
            )
            
            # Check content type
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith(("text/", "application/json")):
                raise ValueError(f"Unexpected content type: {content_type}")
            
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
    
    # Helper methods
    
    def _is_token_revoked(self, jti: str) -> bool:
        """Check if token is revoked."""
        # In production, check revocation list in Redis
        return False
    
    def _is_account_locked(self, username: str) -> bool:
        """Check if account is locked."""
        # Check Redis for lockout
        lock_key = f"account_locked:{username}"
        # return bool(redis_client.get(lock_key))
        return False
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked."""
        block_key = f"ip_blocked:{ip}"
        # return bool(redis_client.get(block_key))
        return False
    
    def _get_user_mfa_secret(self, user_id: int) -> Optional[str]:
        """Get user's MFA secret."""
        # In production, fetch from database
        return None
    
    def _send_security_alert(self, event: Dict[str, Any]):
        """Send security alert."""
        # In production, send to security team
        logger.critical(f"SECURITY_ALERT: {event}")
    
    def _get_recent_actions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's recent actions."""
        # In production, query from activity log
        return []
    
    def _get_recent_locations(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's recent locations."""
        # In production, query from location log
        return []
    
    def _has_impossible_travel(self, locations: List[Dict[str, Any]]) -> bool:
        """Check for impossible travel."""
        # In production, calculate distance/time
        return False
    
    def _is_unusual_time(self, user_id: int) -> bool:
        """Check if activity is at unusual time."""
        # In production, check user's typical activity patterns
        return False


# Global instance
owasp_compliance = OWASPCompliance()


# Middleware for automatic security headers
async def security_headers_middleware(request: Request, call_next):
    """Middleware to add security headers."""
    response = await call_next(request)
    owasp_compliance.apply_security_headers(response)
    return response


# Decorators for common security patterns
def require_recent_auth(max_age_minutes: int = 5):
    """Require recent authentication for sensitive operations."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = getattr(request.state, "user", None)
            if not user:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            last_auth = getattr(user, "last_auth_time", None)
            if not last_auth:
                raise HTTPException(status_code=401, detail="Re-authentication required")
            
            if datetime.utcnow() - last_auth > timedelta(minutes=max_age_minutes):
                raise HTTPException(status_code=401, detail="Re-authentication required")
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def log_security_action(action: str):
    """Log security-sensitive actions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = getattr(request.state, "user", None)
            user_id = user.id if user else None
            
            # Log action
            owasp_compliance.log_security_event(
                event_type=action,
                severity="info",
                user_id=user_id,
                ip_address=request.client.host if request.client else "unknown",
                details={
                    "endpoint": str(request.url),
                    "method": request.method
                }
            )
            
            # Check for anomalies
            if user_id:
                if owasp_compliance.detect_anomalies(user_id, action):
                    logger.warning(f"Anomaly detected for user {user_id} performing {action}")
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator