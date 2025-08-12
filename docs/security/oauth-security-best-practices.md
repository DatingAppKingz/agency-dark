# OAuth 2.0 Security Best Practices

## Overview
This document outlines comprehensive security best practices for implementing and maintaining OAuth 2.0 in the Agency Dark platform. These practices align with industry standards including OWASP, RFC 6819, and OAuth 2.0 Security BCP.

## Table of Contents
- [Security Principles](#security-principles)
- [Client Security](#client-security)
- [Authorization Server Security](#authorization-server-security)
- [Token Security](#token-security)
- [Transport Security](#transport-security)
- [Session Security](#session-security)
- [Multi-Tenant Security](#multi-tenant-security)
- [Threat Mitigation](#threat-mitigation)
- [Security Monitoring](#security-monitoring)
- [Incident Response](#incident-response)
- [Compliance](#compliance)

---

## Security Principles

### Defense in Depth
Implement multiple layers of security controls:

```python
# backend/core/security/defense_layers.py
class DefenseInDepth:
    """
    Multiple security layers for OAuth implementation
    """
    
    LAYERS = [
        "network_security",      # Firewall, DDoS protection
        "transport_security",     # TLS/HTTPS
        "application_security",   # Input validation, output encoding
        "authentication",         # Strong authentication mechanisms
        "authorization",          # Fine-grained access control
        "data_security",         # Encryption at rest and in transit
        "monitoring",            # Security event monitoring
        "incident_response"      # Rapid response procedures
    ]
    
    @classmethod
    def validate_all_layers(cls) -> Dict[str, bool]:
        """Validate all security layers are active"""
        results = {}
        for layer in cls.LAYERS:
            validator = getattr(cls, f"validate_{layer}", None)
            if validator:
                results[layer] = validator()
        return results
```

### Least Privilege
Grant minimum necessary permissions:

```python
# backend/core/security/least_privilege.py
class LeastPrivilegeEnforcer:
    """
    Enforce least privilege principle for OAuth scopes
    """
    
    # Define minimal scope sets for common operations
    MINIMAL_SCOPES = {
        "read_profile": ["openid", "profile"],
        "read_campaigns": ["openid", "campaigns:read"],
        "manage_campaigns": ["openid", "campaigns:read", "campaigns:write"],
        "admin_campaigns": ["openid", "campaigns:read", "campaigns:write", "campaigns:delete"]
    }
    
    @classmethod
    def validate_scope_request(
        cls,
        requested_scopes: List[str],
        user_role: str,
        operation: str
    ) -> List[str]:
        """
        Validate and minimize requested scopes
        """
        # Get maximum allowed scopes for user role
        max_allowed = cls.get_max_scopes_for_role(user_role)
        
        # Get minimum required for operation
        min_required = cls.MINIMAL_SCOPES.get(operation, [])
        
        # Return intersection of requested, allowed, and required
        validated = []
        for scope in requested_scopes:
            if scope in max_allowed and (scope in min_required or operation == "custom"):
                validated.append(scope)
        
        return validated if validated else min_required
```

---

## Client Security

### Client Registration

```python
# backend/oauth/client_security.py
from typing import Dict, List, Optional
import secrets
import hashlib
from datetime import datetime, timedelta

class SecureClientRegistration:
    """
    Secure OAuth client registration and management
    """
    
    @staticmethod
    def register_client(client_data: Dict) -> Dict:
        """
        Securely register a new OAuth client
        """
        # Validate client data
        validated = SecureClientRegistration.validate_client_data(client_data)
        
        # Generate secure credentials
        client_id = SecureClientRegistration.generate_client_id()
        client_secret = SecureClientRegistration.generate_client_secret()
        
        # Hash secret for storage
        secret_hash = SecureClientRegistration.hash_secret(client_secret)
        
        # Set security policies
        client = {
            "client_id": client_id,
            "client_secret_hash": secret_hash,
            "client_name": validated["name"],
            "client_type": validated["type"],  # public or confidential
            "redirect_uris": validated["redirect_uris"],
            "allowed_scopes": validated["scopes"],
            "allowed_grant_types": validated["grant_types"],
            "token_endpoint_auth_method": validated["auth_method"],
            "require_pkce": validated["type"] == "public",
            "require_consent": True,
            "max_token_lifetime": 3600,  # 1 hour
            "max_refresh_lifetime": 2592000,  # 30 days
            "rate_limit": 1000,  # requests per hour
            "created_at": datetime.utcnow(),
            "rotated_at": datetime.utcnow(),
            "rotation_required_by": datetime.utcnow() + timedelta(days=90)
        }
        
        return {
            "client": client,
            "credentials": {
                "client_id": client_id,
                "client_secret": client_secret  # Return once for client to store
            }
        }
    
    @staticmethod
    def validate_client_data(data: Dict) -> Dict:
        """
        Validate client registration data
        """
        # Validate redirect URIs
        for uri in data.get("redirect_uris", []):
            if not SecureClientRegistration.validate_redirect_uri(uri):
                raise ValueError(f"Invalid redirect URI: {uri}")
        
        # Validate client type
        if data.get("type") not in ["public", "confidential"]:
            raise ValueError("Invalid client type")
        
        # Public clients cannot use client_credentials grant
        if data.get("type") == "public":
            if "client_credentials" in data.get("grant_types", []):
                raise ValueError("Public clients cannot use client_credentials grant")
        
        return data
    
    @staticmethod
    def validate_redirect_uri(uri: str) -> bool:
        """
        Validate redirect URI security
        """
        from urllib.parse import urlparse
        
        parsed = urlparse(uri)
        
        # No fragments allowed
        if parsed.fragment:
            return False
        
        # HTTPS required (except localhost for development)
        if parsed.hostname not in ["localhost", "127.0.0.1"]:
            if parsed.scheme != "https":
                return False
        
        # No wildcards in production
        if "*" in uri and not is_development():
            return False
        
        # No open redirects
        if not parsed.hostname:
            return False
        
        return True
    
    @staticmethod
    def generate_client_id() -> str:
        """Generate cryptographically secure client ID"""
        return f"client_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def generate_client_secret() -> str:
        """Generate cryptographically secure client secret"""
        return secrets.token_urlsafe(64)
    
    @staticmethod
    def hash_secret(secret: str) -> str:
        """Hash client secret for storage"""
        salt = secrets.token_bytes(32)
        key = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt, 100000)
        return f"{salt.hex()}:{key.hex()}"
```

### Client Authentication

```python
# backend/oauth/client_authentication.py
class ClientAuthenticator:
    """
    Secure client authentication methods
    """
    
    async def authenticate_client(
        self,
        request: Request,
        require_confidential: bool = False
    ) -> Optional[Dict]:
        """
        Authenticate OAuth client using multiple methods
        """
        # Try authentication methods in order of preference
        methods = [
            self.authenticate_private_key_jwt,
            self.authenticate_client_secret_jwt,
            self.authenticate_client_secret_basic,
            self.authenticate_client_secret_post
        ]
        
        for method in methods:
            client = await method(request)
            if client:
                # Validate client status
                if not await self.validate_client_status(client):
                    raise HTTPException(401, "Client suspended or revoked")
                
                # Check if confidential client required
                if require_confidential and client["type"] == "public":
                    raise HTTPException(401, "Confidential client required")
                
                # Log successful authentication
                await self.log_client_auth(client, method.__name__)
                
                return client
        
        return None
    
    async def authenticate_private_key_jwt(self, request: Request) -> Optional[Dict]:
        """
        Authenticate using private key JWT (most secure)
        """
        assertion = request.form.get("client_assertion")
        if not assertion:
            return None
        
        assertion_type = request.form.get("client_assertion_type")
        if assertion_type != "urn:ietf:params:oauth:client-assertion-type:jwt-bearer":
            return None
        
        try:
            # Decode JWT header to get key ID
            header = jwt.get_unverified_header(assertion)
            kid = header.get("kid")
            
            # Get client's public key
            client_id = jwt.decode(assertion, options={"verify_signature": False})["sub"]
            public_key = await self.get_client_public_key(client_id, kid)
            
            # Verify JWT
            payload = jwt.decode(
                assertion,
                public_key,
                algorithms=["RS256"],
                audience=self.token_endpoint,
                issuer=client_id
            )
            
            # Additional validations
            if payload.get("sub") != payload.get("iss"):
                return None
            
            # Check JWT is not reused
            jti = payload.get("jti")
            if await self.is_jti_used(jti):
                raise HTTPException(401, "JWT already used")
            
            await self.mark_jti_used(jti, ttl=300)  # 5 minutes
            
            return await self.get_client(client_id)
            
        except jwt.PyJWTError:
            return None
```

---

## Authorization Server Security

### Authorization Request Validation

```python
# backend/oauth/authorization_security.py
class AuthorizationSecurity:
    """
    Secure authorization endpoint implementation
    """
    
    async def validate_authorization_request(
        self,
        request: AuthorizationRequest
    ) -> None:
        """
        Comprehensive validation of authorization requests
        """
        # Validate client
        client = await self.get_client(request.client_id)
        if not client:
            raise OAuth2Error("invalid_client", "Client not found")
        
        # Validate redirect URI
        if request.redirect_uri not in client["redirect_uris"]:
            # Don't redirect on redirect_uri mismatch (security)
            raise HTTPException(400, "Invalid redirect URI")
        
        # Validate response type
        if request.response_type not in client["allowed_response_types"]:
            raise OAuth2Error("unsupported_response_type")
        
        # Validate scope
        for scope in request.scopes:
            if scope not in client["allowed_scopes"]:
                raise OAuth2Error("invalid_scope", f"Scope not allowed: {scope}")
        
        # Validate PKCE for public clients
        if client["type"] == "public" or client.get("require_pkce"):
            if not request.code_challenge:
                raise OAuth2Error("invalid_request", "PKCE required")
            
            if request.code_challenge_method != "S256":
                raise OAuth2Error("invalid_request", "Only S256 supported")
        
        # Validate state parameter (recommended)
        if not request.state and not is_development():
            logger.warning(f"Missing state parameter for client {client['client_id']}")
        
        # Check for authorization replay
        if await self.is_duplicate_authorization(request):
            raise OAuth2Error("invalid_request", "Duplicate authorization")
        
        # Rate limiting
        if not await self.check_rate_limit(client["client_id"]):
            raise OAuth2Error("temporarily_unavailable", "Rate limit exceeded")
```

### Consent Management

```python
# backend/oauth/consent_security.py
class ConsentSecurity:
    """
    Secure consent management
    """
    
    async def process_consent(
        self,
        user_id: str,
        client_id: str,
        requested_scopes: List[str]
    ) -> Dict:
        """
        Process user consent securely
        """
        # Check for existing consent
        existing = await self.get_existing_consent(user_id, client_id)
        
        if existing:
            # Validate existing consent is still valid
            if existing["expires_at"] > datetime.utcnow():
                # Check if new scopes requested
                new_scopes = set(requested_scopes) - set(existing["scopes"])
                if not new_scopes:
                    return {"consent": "reused", "scopes": existing["scopes"]}
        
        # Generate consent challenge
        consent_challenge = {
            "challenge_id": secrets.token_urlsafe(32),
            "user_id": user_id,
            "client_id": client_id,
            "requested_scopes": requested_scopes,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=5)
        }
        
        # Store challenge
        await self.store_consent_challenge(consent_challenge)
        
        return {
            "consent": "required",
            "challenge_id": consent_challenge["challenge_id"],
            "client_info": await self.get_client_info(client_id),
            "requested_scopes": requested_scopes
        }
    
    async def validate_consent_response(
        self,
        challenge_id: str,
        user_response: str,
        granted_scopes: List[str]
    ) -> bool:
        """
        Validate consent response
        """
        # Get challenge
        challenge = await self.get_consent_challenge(challenge_id)
        if not challenge:
            raise ValueError("Invalid consent challenge")
        
        # Check expiration
        if challenge["expires_at"] < datetime.utcnow():
            raise ValueError("Consent challenge expired")
        
        # Validate granted scopes are subset of requested
        if not set(granted_scopes).issubset(set(challenge["requested_scopes"])):
            raise ValueError("Invalid scopes granted")
        
        # Store consent decision
        await self.store_consent_decision(
            user_id=challenge["user_id"],
            client_id=challenge["client_id"],
            granted_scopes=granted_scopes,
            decision=user_response
        )
        
        # Delete challenge (one-time use)
        await self.delete_consent_challenge(challenge_id)
        
        return user_response == "approve"
```

---

## Token Security

### Token Generation

```python
# backend/oauth/token_security.py
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

class SecureTokenGenerator:
    """
    Cryptographically secure token generation
    """
    
    def __init__(self):
        self.min_entropy = 128  # bits
    
    def generate_access_token(self) -> str:
        """
        Generate secure access token
        """
        # Use OS random for cryptographic security
        token_bytes = os.urandom(32)  # 256 bits
        
        # Add timestamp component
        timestamp = int(time.time()).to_bytes(8, 'big')
        
        # Combine and encode
        token = base64.urlsafe_b64encode(token_bytes + timestamp).decode().rstrip('=')
        
        # Validate entropy
        if self.calculate_entropy(token) < self.min_entropy:
            raise ValueError("Insufficient token entropy")
        
        return token
    
    def generate_refresh_token(self) -> str:
        """
        Generate secure refresh token with higher entropy
        """
        # Refresh tokens need more entropy (longer lifetime)
        token_bytes = os.urandom(48)  # 384 bits
        
        # Add version byte for future migration
        version = b'\x01'
        
        # Add random salt
        salt = os.urandom(16)
        
        # Derive key for additional security
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(token_bytes)
        
        # Combine all components
        token = base64.urlsafe_b64encode(
            version + salt + key + token_bytes[:16]
        ).decode().rstrip('=')
        
        return token
    
    def generate_authorization_code(self) -> str:
        """
        Generate short-lived authorization code
        """
        # Shorter but still secure (will expire quickly)
        code_bytes = os.urandom(24)  # 192 bits
        
        # Add timestamp for automatic expiration
        timestamp = int(time.time()).to_bytes(8, 'big')
        
        # Add HMAC for integrity
        hmac_key = os.urandom(32)
        h = hmac.new(hmac_key, code_bytes + timestamp, hashlib.sha256)
        
        code = base64.urlsafe_b64encode(
            code_bytes + timestamp + h.digest()[:8]
        ).decode().rstrip('=')
        
        return code
    
    @staticmethod
    def calculate_entropy(token: str) -> float:
        """
        Calculate token entropy in bits
        """
        import math
        from collections import Counter
        
        if not token:
            return 0.0
        
        # Calculate character frequency
        freq = Counter(token)
        probs = [float(f) / len(token) for f in freq.values()]
        
        # Calculate Shannon entropy
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        
        # Return total entropy in bits
        return entropy * len(token)
```

### Token Storage

```python
# backend/oauth/token_storage_security.py
from cryptography.fernet import Fernet
import redis
import json

class SecureTokenStorage:
    """
    Secure token storage with encryption
    """
    
    def __init__(self, redis_client: redis.Redis, encryption_key: bytes):
        self.redis = redis_client
        self.cipher = Fernet(encryption_key)
    
    async def store_token(
        self,
        token_id: str,
        token_data: Dict,
        ttl: int
    ) -> None:
        """
        Store token securely
        """
        # Separate sensitive and non-sensitive data
        sensitive = {
            "access_token": token_data.pop("access_token", None),
            "refresh_token": token_data.pop("refresh_token", None),
            "client_secret": token_data.pop("client_secret", None)
        }
        
        # Encrypt sensitive data
        if any(sensitive.values()):
            encrypted = self.cipher.encrypt(
                json.dumps(sensitive).encode()
            )
            token_data["encrypted_data"] = encrypted.decode()
        
        # Add security metadata
        token_data["created_at"] = int(time.time())
        token_data["expires_at"] = int(time.time()) + ttl
        token_data["access_count"] = 0
        token_data["last_accessed"] = None
        
        # Store with automatic expiration
        key = f"token:{token_id}"
        self.redis.setex(
            key,
            ttl,
            json.dumps(token_data)
        )
        
        # Add to user's token set
        if "user_id" in token_data:
            self.redis.sadd(
                f"user:tokens:{token_data['user_id']}",
                token_id
            )
            # Expire the set member
            self.redis.expire(
                f"user:tokens:{token_data['user_id']}",
                ttl
            )
    
    async def retrieve_token(
        self,
        token_id: str,
        increment_access: bool = True
    ) -> Optional[Dict]:
        """
        Retrieve and decrypt token
        """
        key = f"token:{token_id}"
        
        # Get token data
        data = self.redis.get(key)
        if not data:
            return None
        
        token_data = json.loads(data)
        
        # Check expiration
        if token_data.get("expires_at", 0) < time.time():
            await self.revoke_token(token_id)
            return None
        
        # Decrypt sensitive data
        if "encrypted_data" in token_data:
            decrypted = json.loads(
                self.cipher.decrypt(
                    token_data.pop("encrypted_data").encode()
                )
            )
            token_data.update(decrypted)
        
        # Update access metadata
        if increment_access:
            token_data["access_count"] += 1
            token_data["last_accessed"] = int(time.time())
            
            # Update in storage
            self.redis.set(key, json.dumps({
                k: v for k, v in token_data.items()
                if k not in ["access_token", "refresh_token", "client_secret"]
            }))
        
        return token_data
    
    async def revoke_token(self, token_id: str) -> None:
        """
        Securely revoke token
        """
        key = f"token:{token_id}"
        
        # Get token for logging
        token_data = await self.retrieve_token(token_id, increment_access=False)
        
        if token_data:
            # Log revocation
            logger.info(f"Revoking token {token_id} for user {token_data.get('user_id')}")
            
            # Remove from user's token set
            if "user_id" in token_data:
                self.redis.srem(
                    f"user:tokens:{token_data['user_id']}",
                    token_id
                )
            
            # Add to revocation list (for JWT validation)
            self.redis.setex(
                f"revoked:{token_id}",
                token_data.get("expires_at", 0) - int(time.time()),
                "1"
            )
        
        # Delete token
        self.redis.delete(key)
```

---

## Transport Security

### TLS Configuration

```python
# backend/core/security/tls_config.py
class TLSConfiguration:
    """
    TLS/HTTPS security configuration
    """
    
    # Minimum TLS version
    MIN_TLS_VERSION = "TLSv1.2"
    
    # Recommended cipher suites (in order of preference)
    CIPHER_SUITES = [
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305"
    ]
    
    @classmethod
    def configure_ssl_context(cls) -> ssl.SSLContext:
        """
        Configure secure SSL context
        """
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Set minimum TLS version
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        # Set cipher suites
        context.set_ciphers(':'.join(cls.CIPHER_SUITES))
        
        # Disable weak protocols
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1
        
        # Enable security features
        context.options |= ssl.OP_SINGLE_DH_USE
        context.options |= ssl.OP_SINGLE_ECDH_USE
        
        return context
    
    @classmethod
    def validate_https_redirect(cls, request: Request) -> Optional[str]:
        """
        Validate and generate HTTPS redirect if needed
        """
        if request.url.scheme != "https":
            if not is_localhost(request.url.hostname):
                # Build HTTPS URL
                https_url = request.url.replace(scheme="https")
                return str(https_url)
        return None
```

### HSTS Implementation

```python
# backend/middleware/security_headers.py
from fastapi import Request
from fastapi.responses import Response

class SecurityHeadersMiddleware:
    """
    Security headers middleware
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        # HSTS - Strict Transport Security
        response.headers["Strict-Transport-Security"] = \
            "max-age=31536000; includeSubDomains; preload"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS Protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = \
            "default-src 'self'; " \
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " \
            "style-src 'self' 'unsafe-inline'; " \
            "img-src 'self' data: https:; " \
            "font-src 'self' data:; " \
            "connect-src 'self'; " \
            "frame-ancestors 'none';"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy
        response.headers["Permissions-Policy"] = \
            "accelerometer=(), camera=(), geolocation=(), " \
            "gyroscope=(), magnetometer=(), microphone=(), " \
            "payment=(), usb=()"
        
        # OAuth-specific headers
        if "/oauth" in str(request.url):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        
        return response
```

---

## Session Security

### Session Management

```python
# backend/core/security/session_security.py
class SecureSessionManager:
    """
    Secure session management for OAuth
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.session_timeout = 3600  # 1 hour
        self.absolute_timeout = 43200  # 12 hours
    
    async def create_session(
        self,
        user_id: str,
        client_id: str,
        scopes: List[str],
        metadata: Dict
    ) -> str:
        """
        Create secure session
        """
        # Generate session ID
        session_id = secrets.token_urlsafe(32)
        
        # Create session data
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "client_id": client_id,
            "scopes": scopes,
            "created_at": int(time.time()),
            "last_activity": int(time.time()),
            "expires_at": int(time.time()) + self.absolute_timeout,
            "ip_address": metadata.get("ip_address"),
            "user_agent": metadata.get("user_agent"),
            "fingerprint": self.generate_fingerprint(metadata)
        }
        
        # Store session
        key = f"session:{session_id}"
        self.redis.setex(
            key,
            self.session_timeout,
            json.dumps(session_data)
        )
        
        # Add to user's sessions
        self.redis.sadd(f"user:sessions:{user_id}", session_id)
        
        return session_id
    
    async def validate_session(
        self,
        session_id: str,
        metadata: Dict
    ) -> Optional[Dict]:
        """
        Validate and update session
        """
        key = f"session:{session_id}"
        
        # Get session
        data = self.redis.get(key)
        if not data:
            return None
        
        session = json.loads(data)
        
        # Check absolute timeout
        if session["expires_at"] < time.time():
            await self.terminate_session(session_id)
            return None
        
        # Validate fingerprint
        if session.get("fingerprint"):
            current_fingerprint = self.generate_fingerprint(metadata)
            if session["fingerprint"] != current_fingerprint:
                logger.warning(f"Session fingerprint mismatch for {session_id}")
                # Could be legitimate (browser update, etc.)
                # Log for monitoring but don't immediately terminate
        
        # Check for session fixation
        if await self.detect_session_fixation(session, metadata):
            await self.terminate_session(session_id)
            raise SecurityException("Session fixation detected")
        
        # Update last activity
        session["last_activity"] = int(time.time())
        
        # Extend session timeout
        self.redis.setex(
            key,
            self.session_timeout,
            json.dumps(session)
        )
        
        return session
    
    def generate_fingerprint(self, metadata: Dict) -> str:
        """
        Generate browser/device fingerprint
        """
        components = [
            metadata.get("user_agent", ""),
            metadata.get("accept_language", ""),
            metadata.get("accept_encoding", ""),
            metadata.get("dnt", ""),
            # Don't use IP as it can legitimately change
        ]
        
        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    async def detect_session_fixation(
        self,
        session: Dict,
        metadata: Dict
    ) -> bool:
        """
        Detect potential session fixation attacks
        """
        # Check for rapid IP changes
        if session.get("ip_address") != metadata.get("ip_address"):
            time_since_creation = time.time() - session["created_at"]
            if time_since_creation < 60:  # IP changed within 1 minute
                return True
        
        # Check for impossible travel
        if session.get("ip_address") and metadata.get("ip_address"):
            distance = await self.calculate_geo_distance(
                session["ip_address"],
                metadata["ip_address"]
            )
            time_diff = time.time() - session["last_activity"]
            
            # If distance/time implies > 500mph travel
            if distance > 0 and (distance / time_diff) > 500 * 1.609:  # mph to km/h
                return True
        
        return False
```

---

## Multi-Tenant Security

### Tenant Isolation

```python
# backend/core/security/tenant_isolation.py
class TenantIsolation:
    """
    Multi-tenant security and isolation
    """
    
    @staticmethod
    async def validate_tenant_access(
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """
        Validate tenant access boundaries
        """
        # Get user's tenant
        user_tenant = await get_user_tenant(user_id)
        
        # Check tenant match
        if user_tenant != tenant_id:
            # Check for cross-tenant permissions
            cross_tenant_allowed = await check_cross_tenant_permission(
                user_id,
                tenant_id,
                resource_type
            )
            
            if not cross_tenant_allowed:
                logger.warning(
                    f"Cross-tenant access denied: user {user_id} "
                    f"(tenant {user_tenant}) accessing tenant {tenant_id}"
                )
                return False
        
        # Validate resource belongs to tenant
        resource_tenant = await get_resource_tenant(resource_type, resource_id)
        if resource_tenant != tenant_id:
            logger.error(
                f"Resource tenant mismatch: resource {resource_id} "
                f"belongs to {resource_tenant}, not {tenant_id}"
            )
            return False
        
        return True
    
    @staticmethod
    def apply_tenant_filter(query: str, tenant_id: str) -> str:
        """
        Apply tenant filtering to database queries
        """
        # Add tenant condition to WHERE clause
        if "WHERE" in query.upper():
            return query.replace(
                "WHERE",
                f"WHERE tenant_id = '{tenant_id}' AND",
                1
            )
        else:
            return f"{query} WHERE tenant_id = '{tenant_id}'"
```

---

## Threat Mitigation

### Common OAuth Attacks and Defenses

```python
# backend/core/security/threat_mitigation.py
class OAuthThreatMitigation:
    """
    Mitigation strategies for common OAuth threats
    """
    
    async def prevent_code_injection(self, auth_code: str) -> bool:
        """
        Prevent authorization code injection attacks
        """
        # Bind code to client
        code_data = await self.get_auth_code(auth_code)
        if not code_data:
            return False
        
        # Validate code hasn't been used
        if code_data.get("used"):
            # Code replay attack - revoke all tokens
            await self.revoke_all_tokens_for_code(auth_code)
            logger.critical(f"Authorization code replay detected: {auth_code}")
            return False
        
        # Mark code as used immediately
        await self.mark_code_used(auth_code)
        
        # Validate PKCE if present
        if code_data.get("code_challenge"):
            if not self.validate_pkce(
                code_data["code_challenge"],
                request.code_verifier
            ):
                logger.warning(f"PKCE validation failed for code {auth_code}")
                return False
        
        return True
    
    async def prevent_token_leakage(self, response: Dict) -> Dict:
        """
        Prevent token leakage in responses
        """
        # Never include tokens in URL parameters
        if "access_token" in response:
            # Ensure using fragment, not query
            response["token_location"] = "fragment"
        
        # Add security headers
        response["headers"] = {
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY"
        }
        
        # Limit token scope in implicit flow
        if response.get("response_type") == "token":
            response["scope"] = self.limit_implicit_scope(
                response.get("scope", "")
            )
        
        return response
    
    async def detect_token_scanning(
        self,
        client_id: str,
        request_pattern: List[str]
    ) -> bool:
        """
        Detect token scanning attempts
        """
        # Track introspection patterns
        key = f"introspection:pattern:{client_id}"
        
        # Get recent patterns
        recent = self.redis.lrange(key, 0, 99)
        
        # Detect scanning patterns
        if self.is_scanning_pattern(recent + request_pattern):
            logger.warning(f"Token scanning detected from client {client_id}")
            
            # Temporary block
            self.redis.setex(
                f"blocked:client:{client_id}",
                300,  # 5 minutes
                "token_scanning"
            )
            
            return True
        
        # Store pattern
        for pattern in request_pattern:
            self.redis.lpush(key, pattern)
            self.redis.ltrim(key, 0, 99)
            self.redis.expire(key, 3600)
        
        return False
    
    def is_scanning_pattern(self, patterns: List[str]) -> bool:
        """
        Detect scanning patterns in requests
        """
        if len(patterns) < 10:
            return False
        
        # Sequential token IDs
        if self.is_sequential(patterns):
            return True
        
        # High frequency of invalid tokens
        invalid_rate = sum(1 for p in patterns if p == "invalid") / len(patterns)
        if invalid_rate > 0.8:
            return True
        
        # Predictable patterns
        if self.has_predictable_pattern(patterns):
            return True
        
        return False
```

---

## Security Monitoring

### Security Events

```python
# backend/monitoring/security_events.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class SecurityEventType(Enum):
    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_SUSPICIOUS = "auth.suspicious"
    
    # Token events
    TOKEN_ISSUED = "token.issued"
    TOKEN_REVOKED = "token.revoked"
    TOKEN_EXPIRED = "token.expired"
    TOKEN_LEAKED = "token.leaked"
    
    # Attack events
    ATTACK_DETECTED = "attack.detected"
    ATTACK_BLOCKED = "attack.blocked"
    
    # Compliance events
    CONSENT_GRANTED = "consent.granted"
    CONSENT_DENIED = "consent.denied"
    DATA_ACCESSED = "data.accessed"
    DATA_EXPORTED = "data.exported"

@dataclass
class SecurityEvent:
    event_type: SecurityEventType
    user_id: Optional[str]
    client_id: Optional[str]
    ip_address: str
    user_agent: str
    details: Dict
    risk_score: float
    timestamp: datetime

class SecurityEventMonitor:
    """
    Monitor and analyze security events
    """
    
    def __init__(self):
        self.high_risk_threshold = 0.7
        self.event_handlers = {
            SecurityEventType.AUTH_FAILURE: self.handle_auth_failure,
            SecurityEventType.TOKEN_LEAKED: self.handle_token_leak,
            SecurityEventType.ATTACK_DETECTED: self.handle_attack
        }
    
    async def log_event(self, event: SecurityEvent) -> None:
        """
        Log and process security event
        """
        # Store event
        await self.store_event(event)
        
        # Calculate risk score if not provided
        if event.risk_score == 0:
            event.risk_score = await self.calculate_risk_score(event)
        
        # Handle high-risk events
        if event.risk_score >= self.high_risk_threshold:
            await self.handle_high_risk_event(event)
        
        # Execute specific handlers
        handler = self.event_handlers.get(event.event_type)
        if handler:
            await handler(event)
        
        # Send to SIEM
        await self.send_to_siem(event)
    
    async def calculate_risk_score(self, event: SecurityEvent) -> float:
        """
        Calculate risk score for event
        """
        score = 0.0
        
        # Base score by event type
        base_scores = {
            SecurityEventType.AUTH_FAILURE: 0.3,
            SecurityEventType.TOKEN_LEAKED: 0.9,
            SecurityEventType.ATTACK_DETECTED: 0.8
        }
        score = base_scores.get(event.event_type, 0.1)
        
        # Adjust for user history
        if event.user_id:
            history = await self.get_user_security_history(event.user_id)
            if history["recent_failures"] > 5:
                score += 0.2
            if history["account_age_days"] < 7:
                score += 0.1
        
        # Adjust for IP reputation
        ip_reputation = await self.check_ip_reputation(event.ip_address)
        if ip_reputation == "malicious":
            score += 0.3
        elif ip_reputation == "suspicious":
            score += 0.1
        
        # Adjust for anomaly detection
        if await self.is_anomalous_behavior(event):
            score += 0.2
        
        return min(score, 1.0)
```

### Real-time Alerts

```python
# backend/monitoring/security_alerts.py
class SecurityAlertSystem:
    """
    Real-time security alerting
    """
    
    def __init__(self):
        self.alert_channels = {
            "email": EmailAlertChannel(),
            "slack": SlackAlertChannel(),
            "pagerduty": PagerDutyAlertChannel(),
            "webhook": WebhookAlertChannel()
        }
    
    async def send_alert(
        self,
        severity: str,
        title: str,
        description: str,
        event: SecurityEvent
    ) -> None:
        """
        Send security alert through configured channels
        """
        alert = {
            "severity": severity,
            "title": title,
            "description": description,
            "event": event,
            "timestamp": datetime.utcnow(),
            "environment": os.getenv("ENVIRONMENT", "production")
        }
        
        # Determine channels based on severity
        channels = self.get_channels_for_severity(severity)
        
        # Send through each channel
        tasks = []
        for channel_name in channels:
            channel = self.alert_channels.get(channel_name)
            if channel:
                tasks.append(channel.send(alert))
        
        await asyncio.gather(*tasks)
        
        # Log alert
        logger.info(f"Security alert sent: {title} (severity: {severity})")
    
    def get_channels_for_severity(self, severity: str) -> List[str]:
        """
        Determine alert channels based on severity
        """
        if severity == "critical":
            return ["email", "slack", "pagerduty"]
        elif severity == "high":
            return ["email", "slack"]
        elif severity == "medium":
            return ["slack"]
        else:
            return ["webhook"]
```

---

## Incident Response

### Automated Response

```python
# backend/core/security/incident_response.py
class IncidentResponseSystem:
    """
    Automated incident response for security events
    """
    
    async def respond_to_incident(
        self,
        incident_type: str,
        context: Dict
    ) -> Dict:
        """
        Automated incident response
        """
        response_actions = []
        
        if incident_type == "account_compromise":
            # Immediate actions
            response_actions.extend([
                await self.lock_user_account(context["user_id"]),
                await self.revoke_all_user_tokens(context["user_id"]),
                await self.terminate_all_sessions(context["user_id"]),
                await self.notify_user(context["user_id"], "security_alert"),
                await self.create_incident_ticket(incident_type, context)
            ])
            
        elif incident_type == "token_leak":
            response_actions.extend([
                await self.revoke_token(context["token_id"]),
                await self.rotate_client_secret(context["client_id"]),
                await self.notify_client_admin(context["client_id"]),
                await self.add_to_blocklist(context["token_id"])
            ])
            
        elif incident_type == "brute_force":
            response_actions.extend([
                await self.enable_captcha(context["ip_address"]),
                await self.rate_limit_ip(context["ip_address"], multiplier=0.1),
                await self.geo_block_if_suspicious(context["ip_address"])
            ])
            
        elif incident_type == "suspicious_activity":
            response_actions.extend([
                await self.require_mfa(context["user_id"]),
                await self.log_detailed_activity(context),
                await self.increase_monitoring_level(context["user_id"])
            ])
        
        # Log incident
        incident_id = await self.log_incident(incident_type, context, response_actions)
        
        return {
            "incident_id": incident_id,
            "type": incident_type,
            "actions_taken": response_actions,
            "status": "contained",
            "timestamp": datetime.utcnow()
        }
```

---

## Compliance

### Regulatory Compliance

```python
# backend/core/security/compliance.py
class ComplianceManager:
    """
    Manage regulatory compliance for OAuth
    """
    
    def __init__(self):
        self.regulations = {
            "GDPR": GDPRCompliance(),
            "CCPA": CCPACompliance(),
            "HIPAA": HIPAACompliance(),
            "PCI_DSS": PCIDSSCompliance()
        }
    
    async def ensure_compliance(
        self,
        operation: str,
        context: Dict
    ) -> Dict:
        """
        Ensure operation meets compliance requirements
        """
        compliance_results = {}
        
        for regulation_name, regulation in self.regulations.items():
            if regulation.applies_to(context):
                result = await regulation.validate(operation, context)
                compliance_results[regulation_name] = result
                
                if not result["compliant"]:
                    # Log compliance violation
                    logger.warning(
                        f"Compliance violation: {regulation_name} - "
                        f"{result['reason']}"
                    )
                    
                    # Take corrective action if possible
                    if result.get("corrective_action"):
                        await regulation.apply_corrective_action(
                            operation,
                            context
                        )
        
        return compliance_results

class GDPRCompliance:
    """
    GDPR compliance for OAuth
    """
    
    async def validate(self, operation: str, context: Dict) -> Dict:
        """
        Validate GDPR compliance
        """
        if operation == "data_collection":
            # Ensure explicit consent
            if not context.get("explicit_consent"):
                return {
                    "compliant": False,
                    "reason": "Explicit consent required",
                    "corrective_action": "request_consent"
                }
            
            # Ensure data minimization
            if len(context.get("requested_data", [])) > 10:
                return {
                    "compliant": False,
                    "reason": "Excessive data collection",
                    "corrective_action": "minimize_data"
                }
        
        elif operation == "data_retention":
            # Check retention period
            retention_days = context.get("retention_days", 0)
            if retention_days > 730:  # 2 years
                return {
                    "compliant": False,
                    "reason": "Excessive retention period",
                    "corrective_action": "reduce_retention"
                }
        
        elif operation == "data_transfer":
            # Check for adequate protection
            destination = context.get("destination_country")
            if destination and not self.has_adequacy_decision(destination):
                if not context.get("safeguards"):
                    return {
                        "compliant": False,
                        "reason": "Inadequate data protection",
                        "corrective_action": "implement_safeguards"
                    }
        
        return {"compliant": True}
```

---

## Security Checklist

```markdown
## OAuth Security Checklist

### Client Security
- [ ] Secure client registration process
- [ ] Strong client authentication (mTLS preferred)
- [ ] Client secret rotation policy
- [ ] Redirect URI validation
- [ ] PKCE required for public clients

### Token Security
- [ ] Cryptographically secure token generation
- [ ] Token encryption at rest
- [ ] Short token lifetimes
- [ ] Token binding implemented
- [ ] Refresh token rotation

### Transport Security
- [ ] TLS 1.2+ enforced
- [ ] HSTS enabled
- [ ] Certificate pinning for mobile apps
- [ ] Secure cipher suites only

### Session Security
- [ ] Secure session generation
- [ ] Session timeout policies
- [ ] Session fixation prevention
- [ ] Device fingerprinting

### Monitoring
- [ ] Security event logging
- [ ] Real-time alerting
- [ ] Anomaly detection
- [ ] Regular security audits

### Compliance
- [ ] GDPR compliance
- [ ] CCPA compliance
- [ ] Industry-specific regulations
- [ ] Regular compliance audits

### Incident Response
- [ ] Incident response plan
- [ ] Automated responses configured
- [ ] Recovery procedures documented
- [ ] Regular drills conducted
```

---

## Resources

- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [OAuth 2.0 Threat Model (RFC 6819)](https://tools.ietf.org/html/rfc6819)
- [OWASP OAuth Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Security_Cheat_Sheet.html)
- [NIST Digital Identity Guidelines](https://pages.nist.gov/800-63-3/)