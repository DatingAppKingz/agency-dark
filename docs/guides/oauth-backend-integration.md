# OAuth Backend Integration Guide

## Overview
This guide provides comprehensive instructions for integrating OAuth 2.0 authentication into backend services and APIs that consume the Agency Dark OAuth authorization server.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Resource Server Setup](#resource-server-setup)
- [Token Validation](#token-validation)
- [Scope-Based Authorization](#scope-based-authorization)
- [Multi-Tenant Support](#multi-tenant-support)
- [Service-to-Service Authentication](#service-to-service-authentication)
- [Security Best Practices](#security-best-practices)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before implementing OAuth in your backend:

1. **Client Registration**: Register your service as an OAuth client
2. **Public Keys**: Obtain the authorization server's public keys for token validation
3. **Dependencies**: Install required packages:
   ```bash
   # Python
   pip install pyjwt cryptography httpx redis

   # Node.js
   npm install jsonwebtoken axios node-cache
   ```

---

## Quick Start

### Python FastAPI Example

```python
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import jwt
from typing import Optional, Dict, Any

app = FastAPI()
security = HTTPBearer()

class OAuthValidator:
    def __init__(self):
        self.introspection_endpoint = "https://api.agencydark.com/oauth/introspect"
        self.client_id = "your-client-id"
        self.client_secret = "your-client-secret"
    
    async def validate_token(
        self, 
        credentials: HTTPAuthorizationCredentials = Security(security)
    ) -> Dict[str, Any]:
        """Validate OAuth token via introspection"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.introspection_endpoint,
                data={"token": credentials.credentials},
                auth=(self.client_id, self.client_secret)
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Token validation failed")
            
            token_info = response.json()
            
            if not token_info.get("active"):
                raise HTTPException(status_code=401, detail="Token is not active")
            
            return token_info

oauth_validator = OAuthValidator()

@app.get("/protected")
async def protected_route(token_info: Dict = Depends(oauth_validator.validate_token)):
    return {
        "message": "Access granted",
        "user": token_info.get("sub"),
        "scopes": token_info.get("scope")
    }
```

### Node.js Express Example

```javascript
const express = require('express');
const axios = require('axios');

const app = express();

class OAuthValidator {
    constructor() {
        this.introspectionEndpoint = 'https://api.agencydark.com/oauth/introspect';
        this.clientId = process.env.OAUTH_CLIENT_ID;
        this.clientSecret = process.env.OAUTH_CLIENT_SECRET;
    }

    async validateToken(req, res, next) {
        const authHeader = req.headers.authorization;
        
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'No token provided' });
        }

        const token = authHeader.substring(7);

        try {
            const response = await axios.post(
                this.introspectionEndpoint,
                new URLSearchParams({ token }),
                {
                    auth: {
                        username: this.clientId,
                        password: this.clientSecret
                    }
                }
            );

            if (!response.data.active) {
                return res.status(401).json({ error: 'Token is not active' });
            }

            req.tokenInfo = response.data;
            next();
        } catch (error) {
            res.status(401).json({ error: 'Token validation failed' });
        }
    }
}

const oauthValidator = new OAuthValidator();

app.get('/protected', 
    oauthValidator.validateToken.bind(oauthValidator),
    (req, res) => {
        res.json({
            message: 'Access granted',
            user: req.tokenInfo.sub,
            scopes: req.tokenInfo.scope
        });
    }
);
```

---

## Resource Server Setup

### Complete Python Implementation

```python
# oauth_resource_server.py
import os
import time
import json
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from functools import wraps
import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis
from enum import Enum

class TokenValidationMethod(Enum):
    """Token validation strategies"""
    INTROSPECTION = "introspection"  # Server-side validation
    LOCAL_JWT = "local_jwt"          # Local JWT validation
    HYBRID = "hybrid"                 # Local with periodic introspection

class OAuthResourceServer:
    """
    Complete OAuth 2.0 Resource Server implementation
    """
    
    def __init__(
        self,
        authorization_server: str,
        client_id: str,
        client_secret: str,
        validation_method: TokenValidationMethod = TokenValidationMethod.HYBRID,
        cache_ttl: int = 300,  # 5 minutes
        redis_url: Optional[str] = None
    ):
        self.auth_server = authorization_server
        self.client_id = client_id
        self.client_secret = client_secret
        self.validation_method = validation_method
        self.cache_ttl = cache_ttl
        
        # Endpoints
        self.introspection_endpoint = f"{authorization_server}/oauth/introspect"
        self.jwks_endpoint = f"{authorization_server}/.well-known/jwks.json"
        self.discovery_endpoint = f"{authorization_server}/.well-known/oauth-authorization-server"
        
        # Initialize cache
        self.cache = redis.Redis.from_url(redis_url) if redis_url else None
        
        # JWT validation setup
        self.public_keys: Dict[str, Any] = {}
        self.last_key_fetch = 0
        self.key_refresh_interval = 3600  # 1 hour
        
        # Security
        self.security = HTTPBearer()
        
        # Performance metrics
        self.metrics = {
            "validations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "introspection_calls": 0,
            "failures": 0
        }

    async def fetch_public_keys(self) -> None:
        """Fetch and cache public keys from JWKS endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_endpoint)
            response.raise_for_status()
            
            jwks = response.json()
            self.public_keys = {}
            
            for key in jwks.get("keys", []):
                if key.get("kty") == "RSA":
                    self.public_keys[key["kid"]] = jwt.algorithms.RSAAlgorithm.from_jwk(
                        json.dumps(key)
                    )
            
            self.last_key_fetch = time.time()

    async def validate_token_local(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token locally using public keys"""
        # Refresh keys if needed
        if time.time() - self.last_key_fetch > self.key_refresh_interval:
            await self.fetch_public_keys()
        
        # Decode token header to get key ID
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            
            if not kid or kid not in self.public_keys:
                await self.fetch_public_keys()  # Try refreshing keys
                if kid not in self.public_keys:
                    return None
            
            # Verify token
            decoded = jwt.decode(
                token,
                self.public_keys[kid],
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.auth_server
            )
            
            # Check expiration
            if decoded.get("exp", 0) < time.time():
                return None
            
            return {
                "active": True,
                **decoded
            }
            
        except jwt.PyJWTError:
            return None

    async def validate_token_introspection(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate token via introspection endpoint"""
        self.metrics["introspection_calls"] += 1
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.introspection_endpoint,
                data={"token": token, "token_type_hint": "access_token"},
                auth=(self.client_id, self.client_secret),
                timeout=5.0
            )
            
            if response.status_code != 200:
                return None
            
            return response.json()

    async def validate_token(
        self,
        credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())
    ) -> Dict[str, Any]:
        """
        Main token validation method
        """
        token = credentials.credentials
        self.metrics["validations"] += 1
        
        # Check cache first
        if self.cache:
            cache_key = f"oauth:token:{token[:20]}"  # Use prefix for security
            cached = self.cache.get(cache_key)
            if cached:
                self.metrics["cache_hits"] += 1
                return json.loads(cached)
        
        self.metrics["cache_misses"] += 1
        
        # Validate based on configured method
        token_info = None
        
        if self.validation_method == TokenValidationMethod.LOCAL_JWT:
            token_info = await self.validate_token_local(token)
        elif self.validation_method == TokenValidationMethod.INTROSPECTION:
            token_info = await self.validate_token_introspection(token)
        elif self.validation_method == TokenValidationMethod.HYBRID:
            # Try local first, fall back to introspection
            token_info = await self.validate_token_local(token)
            if not token_info:
                token_info = await self.validate_token_introspection(token)
        
        if not token_info or not token_info.get("active"):
            self.metrics["failures"] += 1
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Cache the result
        if self.cache and token_info:
            cache_key = f"oauth:token:{token[:20]}"
            self.cache.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(token_info)
            )
        
        return token_info

    def require_scopes(self, *required_scopes: str):
        """
        Decorator to require specific OAuth scopes
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Get token info from request context
                request = kwargs.get("request") or args[0] if args else None
                if not request or not hasattr(request.state, "token_info"):
                    raise HTTPException(status_code=401, detail="No token info available")
                
                token_info = request.state.token_info
                token_scopes = set(token_info.get("scope", "").split())
                
                if not all(scope in token_scopes for scope in required_scopes):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Missing required scopes: {required_scopes}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    def require_agency(self, agency_id: Optional[str] = None):
        """
        Decorator to require specific agency context
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                request = kwargs.get("request") or args[0] if args else None
                if not request or not hasattr(request.state, "token_info"):
                    raise HTTPException(status_code=401, detail="No token info available")
                
                token_info = request.state.token_info
                token_agency = token_info.get("agency_id")
                
                if agency_id and token_agency != agency_id:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Access denied for agency: {agency_id}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    async def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        total = self.metrics["validations"]
        if total == 0:
            return self.metrics
        
        return {
            **self.metrics,
            "cache_hit_rate": self.metrics["cache_hits"] / total,
            "failure_rate": self.metrics["failures"] / total,
            "avg_introspection_per_validation": self.metrics["introspection_calls"] / total
        }

# Usage Example
oauth_server = OAuthResourceServer(
    authorization_server="https://api.agencydark.com",
    client_id=os.getenv("OAUTH_CLIENT_ID"),
    client_secret=os.getenv("OAUTH_CLIENT_SECRET"),
    validation_method=TokenValidationMethod.HYBRID,
    redis_url=os.getenv("REDIS_URL")
)

# FastAPI Integration
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def add_token_info(request: Request, call_next):
    """Middleware to add token info to request state"""
    if request.headers.get("authorization"):
        try:
            credentials = await oauth_server.security(request)
            token_info = await oauth_server.validate_token(credentials)
            request.state.token_info = token_info
        except:
            pass  # Let route handlers deal with auth
    
    response = await call_next(request)
    return response

@app.get("/campaigns")
@oauth_server.require_scopes("read:campaigns")
async def get_campaigns(request: Request):
    """Endpoint requiring read:campaigns scope"""
    return {"campaigns": [], "user": request.state.token_info.get("sub")}

@app.post("/campaigns")
@oauth_server.require_scopes("write:campaigns")
async def create_campaign(request: Request, campaign: dict):
    """Endpoint requiring write:campaigns scope"""
    return {"created": True, "campaign": campaign}

@app.delete("/campaigns/{campaign_id}")
@oauth_server.require_scopes("write:campaigns", "delete:campaigns")
async def delete_campaign(request: Request, campaign_id: str):
    """Endpoint requiring multiple scopes"""
    return {"deleted": True, "id": campaign_id}
```

---

## Token Validation

### Validation Strategies Comparison

| Strategy | Pros | Cons | Use Case |
|----------|------|------|----------|
| **Introspection** | Always current, Simple to implement | Network latency, Higher load on auth server | Low-traffic APIs, High-security requirements |
| **Local JWT** | Fast, No network calls | Requires key management, Token revocation delay | High-traffic APIs, Performance critical |
| **Hybrid** | Balance of speed and accuracy | More complex, Cache management | Most production scenarios |

### Implementing Token Caching

```python
import hashlib
from typing import Optional, Dict, Any
import json

class TokenCache:
    """
    Secure token caching with privacy preservation
    """
    
    def __init__(self, redis_client, default_ttl: int = 300):
        self.redis = redis_client
        self.default_ttl = default_ttl
    
    def _hash_token(self, token: str) -> str:
        """Create secure hash of token for cache key"""
        # Use only prefix to prevent token leakage
        prefix = token[:20] if len(token) > 20 else token
        return hashlib.sha256(f"oauth:{prefix}".encode()).hexdigest()
    
    async def get(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve token info from cache"""
        key = self._hash_token(token)
        cached = self.redis.get(key)
        
        if cached:
            data = json.loads(cached)
            # Check if still valid
            if data.get("exp", 0) > time.time():
                return data
            else:
                # Remove expired entry
                self.redis.delete(key)
        
        return None
    
    async def set(self, token: str, token_info: Dict[str, Any]) -> None:
        """Cache token info"""
        key = self._hash_token(token)
        
        # Calculate TTL based on token expiry
        exp = token_info.get("exp", 0)
        ttl = min(
            self.default_ttl,
            max(0, exp - int(time.time()))
        )
        
        if ttl > 0:
            self.redis.setex(
                key,
                ttl,
                json.dumps(token_info)
            )
    
    async def invalidate(self, token: str) -> None:
        """Remove token from cache"""
        key = self._hash_token(token)
        self.redis.delete(key)
    
    async def invalidate_user(self, user_id: str) -> None:
        """Invalidate all tokens for a user"""
        pattern = f"oauth:user:{user_id}:*"
        for key in self.redis.scan_iter(pattern):
            self.redis.delete(key)
```

---

## Scope-Based Authorization

### Implementing Fine-Grained Permissions

```python
from typing import List, Set, Dict, Any
from functools import wraps
import re

class ScopeAuthorizer:
    """
    Advanced scope-based authorization
    """
    
    # Define scope hierarchy
    SCOPE_HIERARCHY = {
        "admin": ["write", "read", "delete"],
        "write": ["read"],
        "delete": ["read"]
    }
    
    # Define resource-specific scopes
    RESOURCE_SCOPES = {
        "campaigns": ["read", "write", "delete", "admin"],
        "users": ["read", "write", "admin"],
        "analytics": ["read", "export"],
        "billing": ["read", "write", "admin"]
    }
    
    @classmethod
    def parse_scopes(cls, scope_string: str) -> Set[str]:
        """Parse scope string into set of scopes"""
        if not scope_string:
            return set()
        return set(scope_string.split())
    
    @classmethod
    def has_scope(cls, token_scopes: Set[str], required_scope: str) -> bool:
        """Check if token has required scope (with hierarchy)"""
        # Direct match
        if required_scope in token_scopes:
            return True
        
        # Check hierarchical scopes
        resource, action = cls._parse_scope(required_scope)
        if resource and action:
            # Check for admin scope on resource
            if f"{resource}:admin" in token_scopes:
                return True
            
            # Check for higher-level actions
            for scope in token_scopes:
                s_resource, s_action = cls._parse_scope(scope)
                if s_resource == resource:
                    if s_action in cls.SCOPE_HIERARCHY:
                        if action in cls.SCOPE_HIERARCHY[s_action]:
                            return True
        
        # Check wildcard scopes
        for scope in token_scopes:
            if cls._matches_wildcard(scope, required_scope):
                return True
        
        return False
    
    @classmethod
    def _parse_scope(cls, scope: str) -> tuple:
        """Parse scope into resource and action"""
        parts = scope.split(":")
        if len(parts) == 2:
            return parts[0], parts[1]
        return None, None
    
    @classmethod
    def _matches_wildcard(cls, pattern: str, scope: str) -> bool:
        """Check if wildcard pattern matches scope"""
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace("*", ".*").replace(":", "\\:")
        return bool(re.match(f"^{regex_pattern}$", scope))
    
    @classmethod
    def filter_resources(
        cls,
        resources: List[Dict[str, Any]],
        token_scopes: Set[str],
        resource_type: str
    ) -> List[Dict[str, Any]]:
        """Filter resources based on scopes"""
        filtered = []
        
        for resource in resources:
            # Check if user has read access to resource type
            if cls.has_scope(token_scopes, f"{resource_type}:read"):
                # Additional filtering based on resource properties
                if resource.get("public") or \
                   cls.has_scope(token_scopes, f"{resource_type}:admin") or \
                   resource.get("owner_id") == token_scopes.get("sub"):
                    filtered.append(resource)
        
        return filtered

# Usage Example
def require_scope(scope: str):
    """Decorator to require specific scope"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            token_info = request.state.token_info
            token_scopes = ScopeAuthorizer.parse_scopes(
                token_info.get("scope", "")
            )
            
            if not ScopeAuthorizer.has_scope(token_scopes, scope):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing required scope: {scope}"
                )
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

@app.get("/api/campaigns")
@require_scope("campaigns:read")
async def list_campaigns(request: Request):
    """List campaigns with scope-based filtering"""
    all_campaigns = await get_all_campaigns()
    token_scopes = ScopeAuthorizer.parse_scopes(
        request.state.token_info.get("scope", "")
    )
    
    filtered = ScopeAuthorizer.filter_resources(
        all_campaigns,
        token_scopes,
        "campaigns"
    )
    
    return {"campaigns": filtered}
```

---

## Multi-Tenant Support

### Implementing Agency Isolation

```python
from typing import Optional, Dict, Any
from fastapi import HTTPException

class MultiTenantManager:
    """
    Multi-tenant (agency) support for OAuth
    """
    
    def __init__(self):
        self.agency_cache = {}
    
    async def extract_agency_context(
        self, 
        request: Request,
        token_info: Dict[str, Any]
    ) -> str:
        """Extract agency context from request or token"""
        
        # Priority 1: Token contains agency_id
        if token_info.get("agency_id"):
            return token_info["agency_id"]
        
        # Priority 2: Subdomain
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain and subdomain != "www":
                return await self.resolve_agency_from_subdomain(subdomain)
        
        # Priority 3: Header
        if request.headers.get("X-Agency-ID"):
            return request.headers["X-Agency-ID"]
        
        # Priority 4: Query parameter
        if request.query_params.get("agency_id"):
            return request.query_params["agency_id"]
        
        # Default agency or error
        raise HTTPException(
            status_code=400,
            detail="Agency context required but not provided"
        )
    
    async def resolve_agency_from_subdomain(self, subdomain: str) -> str:
        """Resolve agency ID from subdomain"""
        # Check cache
        if subdomain in self.agency_cache:
            return self.agency_cache[subdomain]
        
        # Query database
        agency = await db.fetchone(
            "SELECT id FROM agencies WHERE subdomain = ?",
            (subdomain,)
        )
        
        if not agency:
            raise HTTPException(
                status_code=404,
                detail=f"Agency not found for subdomain: {subdomain}"
            )
        
        # Cache result
        self.agency_cache[subdomain] = agency["id"]
        return agency["id"]
    
    def validate_agency_access(
        self,
        token_info: Dict[str, Any],
        required_agency: str
    ) -> bool:
        """Validate token has access to agency"""
        token_agency = token_info.get("agency_id")
        
        # Super admin can access any agency
        if "super:admin" in token_info.get("scope", ""):
            return True
        
        # Token must match required agency
        return token_agency == required_agency

# Middleware for multi-tenant support
@app.middleware("http")
async def multi_tenant_middleware(request: Request, call_next):
    """Add agency context to requests"""
    if hasattr(request.state, "token_info"):
        tenant_manager = MultiTenantManager()
        try:
            agency_id = await tenant_manager.extract_agency_context(
                request,
                request.state.token_info
            )
            request.state.agency_id = agency_id
        except:
            pass  # Let route handlers deal with it
    
    response = await call_next(request)
    return response

# Usage in endpoints
@app.get("/api/agency/campaigns")
@require_scope("campaigns:read")
async def get_agency_campaigns(request: Request):
    """Get campaigns for current agency"""
    if not hasattr(request.state, "agency_id"):
        raise HTTPException(status_code=400, detail="Agency context required")
    
    campaigns = await db.fetch(
        "SELECT * FROM campaigns WHERE agency_id = ?",
        (request.state.agency_id,)
    )
    
    return {"agency_id": request.state.agency_id, "campaigns": campaigns}
```

---

## Service-to-Service Authentication

### Client Credentials Flow Implementation

```python
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class ServiceAuthenticator:
    """
    Service-to-service authentication using Client Credentials flow
    """
    
    def __init__(
        self,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        scopes: List[str]
    ):
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        
        self.current_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.refresh_lock = asyncio.Lock()
    
    async def get_token(self) -> str:
        """Get valid service token, refreshing if needed"""
        async with self.refresh_lock:
            if self._token_needs_refresh():
                await self._refresh_token()
        
        return self.current_token
    
    def _token_needs_refresh(self) -> bool:
        """Check if token needs refresh"""
        if not self.current_token or not self.token_expires_at:
            return True
        
        # Refresh 5 minutes before expiry
        buffer = timedelta(minutes=5)
        return datetime.utcnow() + buffer >= self.token_expires_at
    
    async def _refresh_token(self) -> None:
        """Refresh service token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "scope": " ".join(self.scopes)
                },
                auth=(self.client_id, self.client_secret)
            )
            
            response.raise_for_status()
            token_data = response.json()
            
            self.current_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    async def make_authenticated_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """Make authenticated request to another service"""
        token = await self.get_token()
        
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers
        
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, **kwargs)
            
            # Retry once if 401
            if response.status_code == 401:
                await self._refresh_token()
                token = await self.get_token()
                headers["Authorization"] = f"Bearer {token}"
                response = await client.request(method, url, **kwargs)
            
            return response

# Usage example
analytics_service = ServiceAuthenticator(
    token_endpoint="https://api.agencydark.com/oauth/token",
    client_id="analytics-service",
    client_secret=os.getenv("ANALYTICS_SERVICE_SECRET"),
    scopes=["read:campaigns", "read:analytics", "write:reports"]
)

# Make authenticated call to another service
async def get_campaign_analytics(campaign_id: str):
    response = await analytics_service.make_authenticated_request(
        "GET",
        f"https://campaigns.agencydark.com/api/campaigns/{campaign_id}/metrics"
    )
    response.raise_for_status()
    return response.json()
```

---

## Security Best Practices

### 1. Token Storage
```python
# Never log tokens
import logging

class SecureLogger(logging.Logger):
    def _sanitize_message(self, msg):
        # Remove tokens from log messages
        import re
        msg = re.sub(r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer ***', str(msg))
        msg = re.sub(r'"access_token"\s*:\s*"[^"]*"', '"access_token": "***"', msg)
        return msg
    
    def debug(self, msg, *args, **kwargs):
        super().debug(self._sanitize_message(msg), *args, **kwargs)
```

### 2. Rate Limiting
```python
from typing import Dict
import time

class RateLimiter:
    def __init__(self, max_requests: int = 100, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.clients: Dict[str, List[float]] = {}
    
    async def check_rate_limit(self, client_id: str) -> bool:
        now = time.time()
        
        if client_id not in self.clients:
            self.clients[client_id] = []
        
        # Remove old requests
        self.clients[client_id] = [
            req_time for req_time in self.clients[client_id]
            if now - req_time < self.window
        ]
        
        # Check limit
        if len(self.clients[client_id]) >= self.max_requests:
            return False
        
        self.clients[client_id].append(now)
        return True
```

### 3. Security Headers
```python
from fastapi import Response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # OAuth-specific headers
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    
    return response
```

---

## Testing

### Unit Tests

```python
# test_oauth_validator.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from oauth_resource_server import OAuthResourceServer, TokenValidationMethod

@pytest.fixture
def oauth_server():
    return OAuthResourceServer(
        authorization_server="https://test.example.com",
        client_id="test-client",
        client_secret="test-secret",
        validation_method=TokenValidationMethod.INTROSPECTION
    )

@pytest.mark.asyncio
async def test_token_validation_success(oauth_server):
    with patch.object(oauth_server, 'validate_token_introspection') as mock_introspect:
        mock_introspect.return_value = {
            "active": True,
            "sub": "user:123",
            "scope": "read:campaigns write:campaigns"
        }
        
        credentials = Mock(credentials="test-token")
        result = await oauth_server.validate_token(credentials)
        
        assert result["active"] is True
        assert result["sub"] == "user:123"

@pytest.mark.asyncio
async def test_token_validation_expired(oauth_server):
    with patch.object(oauth_server, 'validate_token_introspection') as mock_introspect:
        mock_introspect.return_value = {"active": False}
        
        credentials = Mock(credentials="expired-token")
        
        with pytest.raises(HTTPException) as exc_info:
            await oauth_server.validate_token(credentials)
        
        assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_scope_requirement():
    from scope_authorizer import ScopeAuthorizer
    
    token_scopes = {"campaigns:read", "campaigns:write"}
    
    assert ScopeAuthorizer.has_scope(token_scopes, "campaigns:read") is True
    assert ScopeAuthorizer.has_scope(token_scopes, "campaigns:delete") is False
    assert ScopeAuthorizer.has_scope(token_scopes, "users:read") is False
```

### Integration Tests

```python
# test_oauth_integration.py
import httpx
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def test_token():
    """Get test token for integration tests"""
    return "test-bearer-token"

def test_protected_endpoint_with_valid_token(test_token):
    with TestClient(app) as client:
        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        assert response.status_code == 200

def test_protected_endpoint_without_token():
    with TestClient(app) as client:
        response = client.get("/protected")
        assert response.status_code == 401

def test_scope_protected_endpoint(test_token):
    with TestClient(app) as client:
        response = client.get(
            "/campaigns",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        # Depends on token scopes
        assert response.status_code in [200, 403]
```

---

## Troubleshooting

### Common Issues

#### 1. Token Validation Failures
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Add detailed error handling
try:
    token_info = await oauth_server.validate_token(credentials)
except HTTPException as e:
    logger.error(f"Token validation failed: {e.detail}")
    # Check introspection endpoint connectivity
    # Verify client credentials
    # Check token format
```

#### 2. Performance Issues
```python
# Monitor validation performance
import time

start = time.time()
token_info = await oauth_server.validate_token(credentials)
duration = time.time() - start

if duration > 0.1:  # 100ms threshold
    logger.warning(f"Slow token validation: {duration:.3f}s")
    # Consider switching to hybrid or local validation
    # Implement caching
    # Check network latency
```

#### 3. Multi-Tenant Issues
```python
# Debug agency resolution
logger.debug(f"Request host: {request.headers.get('host')}")
logger.debug(f"Token agency: {token_info.get('agency_id')}")
logger.debug(f"Resolved agency: {request.state.agency_id}")
```

---

## Migration from JWT

### Step-by-Step Migration

1. **Update Dependencies**
```python
# Old JWT validation
def validate_jwt(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

# New OAuth validation
async def validate_oauth(token: str):
    return await oauth_server.validate_token(token)
```

2. **Update Middleware**
```python
# Old JWT middleware
@app.middleware("http")
async def jwt_middleware(request: Request, call_next):
    token = extract_jwt_from_header(request)
    if token:
        request.state.user = validate_jwt(token)
    return await call_next(request)

# New OAuth middleware
@app.middleware("http")
async def oauth_middleware(request: Request, call_next):
    if request.headers.get("authorization"):
        token_info = await oauth_server.validate_token(request)
        request.state.token_info = token_info
        request.state.user = token_info.get("sub")
    return await call_next(request)
```

3. **Update Authorization Logic**
```python
# Old role-based check
if request.state.user.role != "admin":
    raise HTTPException(403)

# New scope-based check
if not ScopeAuthorizer.has_scope(token_scopes, "admin"):
    raise HTTPException(403)
```

---

## Performance Optimization

### Caching Strategy
```python
# Implement multi-level caching
class MultiLevelCache:
    def __init__(self):
        self.memory_cache = {}  # L1: In-memory
        self.redis_cache = redis.Redis()  # L2: Redis
    
    async def get(self, key: str):
        # Check memory first
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Check Redis
        value = self.redis_cache.get(key)
        if value:
            self.memory_cache[key] = value
            return value
        
        return None
```

### Connection Pooling
```python
# Reuse HTTP connections
class ConnectionPool:
    def __init__(self):
        self.client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100
            )
        )
```

---

## Monitoring

### Metrics Collection
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
token_validations = Counter('oauth_token_validations_total', 'Total token validations')
validation_duration = Histogram('oauth_validation_duration_seconds', 'Token validation duration')
cache_hits = Counter('oauth_cache_hits_total', 'Cache hit count')
active_tokens = Gauge('oauth_active_tokens', 'Number of active tokens')

# Instrument code
@validation_duration.time()
async def validate_token_with_metrics(token: str):
    token_validations.inc()
    result = await oauth_server.validate_token(token)
    if cached:
        cache_hits.inc()
    return result
```

---

## Resources

- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [OAuth 2.0 Token Introspection RFC 7662](https://tools.ietf.org/html/rfc7662)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Agency Dark OAuth API Documentation](../api/oauth-endpoints.md)