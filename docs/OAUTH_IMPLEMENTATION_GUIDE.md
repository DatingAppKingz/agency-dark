# Embedded OAuth for AgencyDark: FastAPI + Authlib Implementation Guide

## Why Authlib is Perfect for AgencyDark

As mentioned in your document, Authlib is the most comprehensive OAuth/OIDC library for Python and the ideal choice for embedding OAuth directly into your FastAPI application. It provides:

- Full OAuth 2.0 & OpenID Connect support
- Built-in FastAPI/Starlette integration  
- Both OAuth provider AND consumer capabilities
- PKCE support out of the box
- JWT/JWE/JWK handling
- Multi-tenant friendly architecture

## Architecture Overview

Instead of deploying a separate IdP like Keycloak, we'll embed the OAuth server directly into your FastAPI application:

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌─────────────────┐
│                 │     │       AgencyDark App         │     │                 │
│  Agency Staff   │────▶│  ┌────────────────────┐     │────▶│    Supabase     │
│   (Chatters)    │     │  │  OAuth Provider    │     │     │   PostgreSQL    │
│                 │     │  │    (Authlib)       │     │     │                 │
└─────────────────┘     │  └────────────────────┘     │     └─────────────────┘
                        │  ┌────────────────────┐     │
┌─────────────────┐     │  │  OAuth Consumer    │     │     ┌─────────────────┐
│   External      │────▶│  │    (Authlib)       │     │────▶│  Upstash Redis  │
│     APIs        │     │  └────────────────────┘     │     │    (Sessions)   │
│  (Instagram)    │     └──────────────────────────────┘     └─────────────────┘
└─────────────────┘
```

## Installation

```bash
pip install authlib[crypto]
pip install fastapi
pip install sqlalchemy
pip install asyncpg  # for async PostgreSQL
pip install redis
pip install python-jose[cryptography]  # for JWT
pip install bcrypt
```

## Database Schema for Multi-Tenant OAuth

```python
# models/oauth.py
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class OAuthClient(Base):
    __tablename__ = 'oauth_clients'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id'), nullable=False)
    client_id = Column(String(48), unique=True, nullable=False, index=True)
    client_secret = Column(String(120))
    client_name = Column(String(100))
    
    # OAuth2 metadata
    redirect_uris = Column(ARRAY(String), nullable=False)
    grant_types = Column(ARRAY(String), nullable=False, default=['authorization_code'])
    response_types = Column(ARRAY(String), nullable=False, default=['code'])
    scope = Column(Text, default='')
    
    # Multi-tenant isolation
    allowed_agencies = Column(ARRAY(UUID), default=[])  # For cross-agency access
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    def check_client_secret(self, client_secret):
        return self.client_secret == client_secret
    
    @property
    def client_metadata(self):
        return {
            'client_name': self.client_name,
            'redirect_uris': self.redirect_uris,
            'grant_types': self.grant_types,
            'response_types': self.response_types,
            'scope': self.scope,
        }

class OAuthToken(Base):
    __tablename__ = 'oauth_tokens'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    client_id = Column(String(48), ForeignKey('oauth_clients.client_id'))
    
    # Token data
    token_type = Column(String(40))
    access_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, index=True)
    scope = Column(Text, default='')
    
    # Expiration
    expires_at = Column(DateTime)
    
    # Additional claims for multi-tenancy
    extra_data = Column(JSON)
    
    created_at = Column(DateTime, server_default=func.now())

class OAuthAuthorizationCode(Base):
    __tablename__ = 'oauth_authorization_codes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey('agencies.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    client_id = Column(String(48), ForeignKey('oauth_clients.client_id'))
    
    code = Column(String(120), unique=True, nullable=False, index=True)
    redirect_uri = Column(Text)
    scope = Column(Text, default='')
    
    # PKCE support
    code_challenge = Column(String(128))
    code_challenge_method = Column(String(10))
    
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

## Authlib OAuth Server Implementation

```python
# oauth/provider.py
from authlib.integrations.sqla_oauth2 import (
    OAuth2ClientMixin,
    OAuth2AuthorizationCodeMixin,
    OAuth2TokenMixin,
    create_query_client_func,
    create_save_token_func,
    create_bearer_token_validator,
)
from authlib.integrations.fastapi_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc7636 import CodeChallenge
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request
from typing import Optional
import time

# Custom grant for multi-tenant authorization
class MultiTenantAuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = ['client_secret_basic', 'client_secret_post']
    
    def save_authorization_code(self, code, request):
        """Save authorization code with agency context"""
        client = request.client
        user = request.user
        agency_id = getattr(user, 'agency_id', None)
        
        auth_code = OAuthAuthorizationCode(
            code=code,
            client_id=client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user_id=user.id,
            agency_id=agency_id,
            code_challenge=request.data.get('code_challenge'),
            code_challenge_method=request.data.get('code_challenge_method'),
            expires_at=time.time() + 600  # 10 minutes
        )
        
        self.server.db.add(auth_code)
        self.server.db.commit()
        return auth_code

    def query_authorization_code(self, code, client):
        """Query auth code with agency validation"""
        auth_code = self.server.db.query(OAuthAuthorizationCode).filter_by(
            code=code,
            client_id=client.client_id
        ).first()
        
        if auth_code and auth_code.expires_at > time.time():
            return auth_code
        return None

    def delete_authorization_code(self, authorization_code):
        """Delete used authorization code"""
        self.server.db.delete(authorization_code)
        self.server.db.commit()

    def authenticate_user(self, authorization_code):
        """Load user with agency context"""
        return self.server.db.query(User).filter_by(
            id=authorization_code.user_id
        ).first()

# Initialize authorization server
def create_authorization_server(app, db_session):
    query_client = create_query_client_func(db_session, OAuthClient)
    save_token = create_save_token_func(db_session, OAuthToken)
    
    authorization_server = AuthorizationServer(
        app,
        query_client=query_client,
        save_token=save_token,
    )
    
    # Register grants
    authorization_server.register_grant(MultiTenantAuthorizationCodeGrant, [
        CodeChallenge(required=True),  # Require PKCE
    ])
    authorization_server.register_grant(grants.RefreshTokenGrant)
    authorization_server.register_grant(grants.ClientCredentialsGrant)
    
    return authorization_server

# Resource protector for validating tokens
def create_resource_protector(db_session):
    bearer_token_validator = create_bearer_token_validator(db_session, OAuthToken)
    from authlib.integrations.fastapi_oauth2 import ResourceProtector
    
    resource_protector = ResourceProtector()
    resource_protector.register_token_validator(bearer_token_validator)
    
    return resource_protector
```

## FastAPI OAuth Endpoints

```python
# api/oauth.py
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.oauth2 import OAuth2Error
from typing import Optional
import json

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Dependency to get current agency from subdomain or header
async def get_current_agency(request: Request, db: AsyncSession = Depends(get_db)):
    # Extract from subdomain
    host = request.headers.get('host', '')
    subdomain = host.split('.')[0] if '.' in host else None
    
    # Or from header
    agency_id = request.headers.get('x-agency-id', subdomain)
    
    if not agency_id:
        raise HTTPException(status_code=400, detail="Agency identification required")
    
    agency = await db.query(Agency).filter(
        (Agency.subdomain == agency_id) | (Agency.id == agency_id)
    ).first()
    
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    return agency

# Authorization endpoint
@router.get("/authorize")
async def authorize(
    request: Request,
    agency: Agency = Depends(get_current_agency),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """OAuth2 authorization endpoint with multi-tenant support"""
    # Ensure user belongs to the agency
    if current_user.agency_id != agency.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if client belongs to agency
    client_id = request.query_params.get('client_id')
    client = await db.query(OAuthClient).filter_by(
        client_id=client_id,
        agency_id=agency.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=400, detail="Invalid client")
    
    # In production, show consent screen here
    # For now, auto-approve
    return await create_authorization_response(request, current_user)

@router.post("/authorize")
async def authorize_post(
    request: Request,
    agency: Agency = Depends(get_current_agency),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    grant: str = Form(...)
):
    """Handle authorization consent"""
    if grant != 'true':
        # User denied consent
        return RedirectResponse(url='/dashboard')
    
    return await create_authorization_response(request, current_user)

async def create_authorization_response(request: Request, user: User):
    """Create authorization response with PKCE validation"""
    try:
        authorization = authorization_server.create_authorization_response(
            request=request,
            grant_user=user
        )
        return authorization
    except OAuth2Error as error:
        return error.get_response()

# Token endpoint
@router.post("/token")
async def issue_token(
    request: Request,
    agency: Agency = Depends(get_current_agency),
    db: AsyncSession = Depends(get_db)
):
    """OAuth2 token endpoint"""
    try:
        # Add agency context to request
        request.state.agency_id = agency.id
        
        token = authorization_server.create_token_response(request)
        
        # Add custom claims for multi-tenancy
        if isinstance(token, dict):
            token['agency_id'] = str(agency.id)
            token['agency_subdomain'] = agency.subdomain
        
        return token
    except OAuth2Error as error:
        return error.get_response()

# Token introspection endpoint
@router.post("/introspect")
async def introspect_token(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    agency: Agency = Depends(get_current_agency),
    db: AsyncSession = Depends(get_db)
):
    """Token introspection for multi-tenant validation"""
    token_data = await db.query(OAuthToken).filter_by(
        access_token=token,
        agency_id=agency.id
    ).first()
    
    if not token_data or token_data.expires_at < datetime.utcnow():
        return {"active": False}
    
    return {
        "active": True,
        "scope": token_data.scope,
        "client_id": token_data.client_id,
        "username": token_data.user.email,
        "exp": int(token_data.expires_at.timestamp()),
        "agency_id": str(token_data.agency_id),
        "user_id": str(token_data.user_id)
    }

# Revoke token endpoint
@router.post("/revoke")
async def revoke_token(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    agency: Agency = Depends(get_current_agency),
    db: AsyncSession = Depends(get_db)
):
    """Revoke access or refresh token"""
    token_data = await db.query(OAuthToken).filter(
        (OAuthToken.access_token == token) | (OAuthToken.refresh_token == token),
        OAuthToken.agency_id == agency.id
    ).first()
    
    if token_data:
        await db.delete(token_data)
        await db.commit()
    
    return Response(status_code=200)
```

## OAuth Consumer for External APIs

```python
# oauth/consumer.py
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.fastapi_oauth2 import OAuth2Token
from fastapi import Request
import json

# Initialize OAuth client
oauth = OAuth()

# Configure Instagram OAuth (per agency)
def configure_instagram_oauth(agency):
    """Configure Instagram OAuth with agency-specific credentials"""
    oauth.register(
        name=f'instagram_{agency.id}',
        client_id=agency.instagram_client_id,
        client_secret=agency.instagram_client_secret,
        authorize_url='https://api.instagram.com/oauth/authorize',
        access_token_url='https://api.instagram.com/oauth/access_token',
        client_kwargs={'scope': 'user_profile user_media'}
    )

# OnlyFans OAuth configuration (hypothetical)
def configure_onlyfans_oauth(agency):
    """Configure OnlyFans OAuth if/when available"""
    oauth.register(
        name=f'onlyfans_{agency.id}',
        client_id=agency.onlyfans_client_id,
        client_secret=agency.onlyfans_client_secret,
        authorize_url='https://onlyfans.com/oauth/authorize',
        access_token_url='https://onlyfans.com/oauth/token',
        client_kwargs={'scope': 'read:messages write:messages'}
    )

# External OAuth endpoints
@router.get("/connect/{provider}")
async def connect_external_provider(
    provider: str,
    request: Request,
    agency: Agency = Depends(get_current_agency),
    current_user: User = Depends(get_current_user)
):
    """Initiate OAuth flow with external provider"""
    if provider == 'instagram':
        configure_instagram_oauth(agency)
        client = oauth.create_client(f'instagram_{agency.id}')
    elif provider == 'onlyfans':
        configure_onlyfans_oauth(agency)
        client = oauth.create_client(f'onlyfans_{agency.id}')
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")
    
    redirect_uri = f"{request.base_url}oauth/callback/{provider}"
    
    # Store state in Redis for multi-tenant callback
    state = generate_state()
    await redis.setex(
        f"oauth_state:{state}",
        600,  # 10 minutes
        json.dumps({
            'agency_id': str(agency.id),
            'user_id': str(current_user.id),
            'provider': provider
        })
    )
    
    return await client.authorize_redirect(request, redirect_uri, state=state)

@router.get("/callback/{provider}")
async def external_oauth_callback(
    provider: str,
    request: Request,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback from external provider"""
    # Retrieve state from Redis
    state_data = await redis.get(f"oauth_state:{state}")
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid state")
    
    state_info = json.loads(state_data)
    agency_id = state_info['agency_id']
    user_id = state_info['user_id']
    
    # Get agency and configure OAuth
    agency = await db.query(Agency).filter_by(id=agency_id).first()
    
    if provider == 'instagram':
        configure_instagram_oauth(agency)
        client = oauth.create_client(f'instagram_{agency.id}')
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")
    
    # Exchange code for token
    token = await client.authorize_access_token(request)
    
    # Store encrypted token in database
    external_token = ExternalOAuthToken(
        agency_id=agency_id,
        user_id=user_id,
        provider=provider,
        access_token=encrypt(token['access_token']),
        refresh_token=encrypt(token.get('refresh_token')),
        expires_at=datetime.fromtimestamp(token.get('expires_at', 0)),
        scope=token.get('scope', ''),
        raw_data=encrypt(json.dumps(token))
    )
    
    db.add(external_token)
    await db.commit()
    
    # Clean up Redis state
    await redis.delete(f"oauth_state:{state}")
    
    return RedirectResponse(url='/dashboard/integrations?success=true')
```

## Security Middleware for Adult Content

```python
# middleware/security.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import geoip2.database
from datetime import datetime, timedelta
import hashlib

class AdultContentSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, geoip_path: str, restricted_countries: list):
        super().__init__(app)
        self.geoip_reader = geoip2.database.Reader(geoip_path)
        self.restricted_countries = restricted_countries
    
    async def dispatch(self, request: Request, call_next):
        # Geo-blocking
        client_ip = request.client.host
        try:
            response = self.geoip_reader.country(client_ip)
            country_code = response.country.iso_code
            
            if country_code in self.restricted_countries:
                raise HTTPException(
                    status_code=451,
                    detail="Content not available in your region"
                )
        except geoip2.errors.AddressNotFoundError:
            pass  # Allow if IP not found
        
        # Age verification check for protected endpoints
        if request.url.path.startswith('/api/content/'):
            token = request.headers.get('authorization', '').replace('Bearer ', '')
            if token:
                # Validate age verification status
                user = await get_user_from_token(token)
                if user and not user.age_verified:
                    raise HTTPException(
                        status_code=403,
                        detail="Age verification required",
                        headers={"X-Age-Verify-URL": "/verify/age"}
                    )
        
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

# Age verification integration
class AgeVerificationService:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key
    
    async def verify_age(self, user_data: dict) -> dict:
        """Integrate with age verification providers"""
        if self.provider == 'yoti':
            return await self._verify_with_yoti(user_data)
        elif self.provider == 'verifyMyAge':
            return await self._verify_with_verifymyage(user_data)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _verify_with_yoti(self, user_data: dict) -> dict:
        # Implement Yoti age verification
        # This would make actual API calls to Yoti
        pass
    
    async def _verify_with_verifymyage(self, user_data: dict) -> dict:
        # Implement VerifyMyAge verification
        pass
```

## Redis Session Management

```python
# services/session.py
from typing import Optional, Dict, Any
import json
import secrets
from datetime import datetime, timedelta
from redis.asyncio import Redis

class MultiTenantSessionManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.default_ttl = 86400  # 24 hours
    
    async def create_session(
        self,
        user_id: str,
        agency_id: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new session with agency isolation"""
        session_id = secrets.token_urlsafe(32)
        session_key = f"session:{agency_id}:{session_id}"
        
        session_data = {
            "user_id": user_id,
            "agency_id": agency_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        await self.redis.setex(
            session_key,
            self.default_ttl,
            json.dumps(session_data)
        )
        
        # Track active sessions per user
        user_sessions_key = f"user_sessions:{agency_id}:{user_id}"
        await self.redis.sadd(user_sessions_key, session_id)
        await self.redis.expire(user_sessions_key, self.default_ttl)
        
        return session_id
    
    async def get_session(
        self,
        session_id: str,
        agency_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get session with agency validation"""
        session_key = f"session:{agency_id}:{session_id}"
        data = await self.redis.get(session_key)
        
        if not data:
            return None
        
        session = json.loads(data)
        
        # Update last activity
        session["last_activity"] = datetime.utcnow().isoformat()
        await self.redis.setex(
            session_key,
            self.default_ttl,
            json.dumps(session)
        )
        
        return session
    
    async def revoke_session(self, session_id: str, agency_id: str):
        """Revoke a specific session"""
        session_key = f"session:{agency_id}:{session_id}"
        session_data = await self.get_session(session_id, agency_id)
        
        if session_data:
            # Remove from user's active sessions
            user_sessions_key = f"user_sessions:{agency_id}:{session_data['user_id']}"
            await self.redis.srem(user_sessions_key, session_id)
            
            # Delete session
            await self.redis.delete(session_key)
    
    async def revoke_all_user_sessions(self, user_id: str, agency_id: str):
        """Revoke all sessions for a user in an agency"""
        user_sessions_key = f"user_sessions:{agency_id}:{user_id}"
        session_ids = await self.redis.smembers(user_sessions_key)
        
        # Delete all sessions
        if session_ids:
            session_keys = [
                f"session:{agency_id}:{sid.decode()}"
                for sid in session_ids
            ]
            await self.redis.delete(*session_keys)
        
        # Clear user sessions set
        await self.redis.delete(user_sessions_key)
```

## Complete FastAPI Application Setup

```python
# main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
import redis.asyncio as redis
import os

# Initialize services
redis_client = None
session_manager = None
authorization_server = None
resource_protector = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global redis_client, session_manager, authorization_server, resource_protector
    
    # Initialize Redis
    redis_client = await redis.from_url(
        os.getenv("UPSTASH_REDIS_URL"),
        decode_responses=True
    )
    
    # Initialize session manager
    session_manager = MultiTenantSessionManager(redis_client)
    
    # Initialize OAuth server
    authorization_server = create_authorization_server(app, get_db)
    resource_protector = create_resource_protector(get_db)
    
    yield
    
    # Shutdown
    await redis_client.close()

# Create FastAPI app
app = FastAPI(
    title="AgencyDark OAuth Server",
    description="Multi-tenant OAuth2 server for content creator agencies",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.agencydark.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware
app.add_middleware(
    AdultContentSecurityMiddleware,
    geoip_path="/path/to/GeoLite2-Country.mmdb",
    restricted_countries=["XX", "YY", "ZZ"]
)

# Database setup
engine = create_async_engine(
    os.getenv("SUPABASE_DATABASE_URL"),
    echo=False,
    pool_size=20,
    max_overflow=0
)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Include routers
app.include_router(oauth_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(content_router, prefix="/api/content")

# Protected endpoint example
@app.get("/api/me")
@resource_protector()
async def get_current_user_info(request: Request, token: OAuth2Token = Depends()):
    """Get current user info with multi-tenant context"""
    return {
        "user_id": token.user_id,
        "agency_id": token.agency_id,
        "scope": token.scope,
        "email": token.user.email,
        "role": token.user.role
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Environment Configuration

```bash
# .env
# OAuth Server Configuration
OAUTH_ACCESS_TOKEN_LIFETIME=3600  # 1 hour
OAUTH_REFRESH_TOKEN_LIFETIME=1209600  # 14 days
OAUTH_AUTHORIZATION_CODE_LIFETIME=600  # 10 minutes
OAUTH_REQUIRE_PKCE=true

# Security
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key

# Database
SUPABASE_DATABASE_URL=postgresql+asyncpg://user:pass@db.supabase.co:5432/postgres
UPSTASH_REDIS_URL=redis://default:xxx@redis.upstash.io:6379

# Adult Content Compliance
AGE_VERIFICATION_PROVIDER=yoti
AGE_VERIFICATION_API_KEY=your-api-key
RESTRICTED_COUNTRIES=CN,SA,AE,QA,KW,IN

# External OAuth Providers (stored per agency in DB)
# These would be configured per agency in the database
```

## Migration Strategy

### Week 1: Core OAuth Implementation
1. Set up Authlib with FastAPI
2. Create database models
3. Implement basic OAuth2 flows

### Week 2: Multi-Tenant Features
1. Add agency isolation
2. Implement tenant resolution
3. Add cross-tenant authorization

### Week 3: External OAuth Consumers
1. Instagram integration
2. Token encryption and storage
3. Webhook handling

### Week 4: Security & Compliance
1. Age verification integration
2. Geo-blocking
3. Audit logging

### Week 5-6: Testing & Deployment
1. Load testing
2. Security audit
3. Gradual rollout

## Advantages of This Approach

1. **Single Deployment:** Everything runs in your FastAPI app
2. **Direct Database Access:** No API calls to external IdP
3. **Full Control:** Customize every aspect for adult content requirements
4. **Cost Effective:** No additional infrastructure needed
5. **Performance:** Lower latency without external IdP calls
6. **Flexibility:** Easy to add custom claims and validations

This embedded approach with Authlib gives you enterprise-grade OAuth2/OIDC capabilities while maintaining complete control over your authentication system, perfect for the unique requirements of the AgencyDark platform.