# OAuth2.0 & SSO Solutions for AgencyDark

## Current OAuth Implementation Issues

Based on the codebase analysis:
1. **Custom OAuth implementation** in `modules/sso/oauth.py` - reinventing the wheel
2. **No standard OAuth library** - using raw `httpx` and `jwt` for OAuth flows
3. **Missing OAuth features** - No PKCE, refresh token rotation, or token introspection
4. **Limited provider support** - Manual configuration required for each provider
5. **No standardized SSO** - Custom implementation prone to security vulnerabilities

## Recommended Open-Source Solutions

### 1. **Authlib** (Recommended for FastAPI)
**Why:** Most comprehensive OAuth/OIDC library for Python

```bash
pip install authlib
```

**Pros:**
- Full OAuth 2.0 & OpenID Connect support
- Built-in FastAPI integration
- Supports all OAuth flows (Authorization Code, Client Credentials, etc.)
- PKCE support out of the box
- JWT validation with JWK support
- Provider presets (Google, GitHub, etc.)

**Implementation Example:**
```python
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI

oauth = OAuth()
oauth.register(
    name='google',
    client_id='...',
    client_secret='...',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
```

### 2. **Keycloak** (Self-Hosted Identity Provider)
**Why:** Enterprise-grade, open-source identity and access management

**Features:**
- Complete OAuth2.0/OIDC provider
- SAML 2.0 support
- User federation (LDAP, Active Directory)
- Social login (Google, Facebook, etc.)
- Multi-factor authentication
- Admin console for management

**Integration:**
```python
# Use python-keycloak library
pip install python-keycloak

from keycloak import KeycloakOpenID

keycloak_openid = KeycloakOpenID(
    server_url="https://keycloak.example.com/auth/",
    client_id="agency-dark",
    realm_name="master",
    client_secret_key="secret"
)

# Get token
token = keycloak_openid.token("user", "password")
```

### 3. **FastAPI-Users** (FastAPI-Specific Solution)
**Why:** Purpose-built for FastAPI with batteries included

```bash
pip install fastapi-users[sqlalchemy,oauth]
```

**Features:**
- Ready-to-use OAuth2 flows
- Database integration (SQLAlchemy)
- JWT or database sessions
- Registration/verification flows
- Password reset
- Social auth providers

**Implementation:**
```python
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy, AuthenticationBackend

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)
```

### 4. **Authentik** (Self-Hosted Alternative to Keycloak)
**Why:** Modern, lightweight identity provider

**Features:**
- OAuth2/OIDC/SAML provider
- Built-in user directory
- Flow-based authentication
- Docker-ready deployment
- Modern UI
- API-first design

### 5. **Ory Kratos + Hydra** (Microservices Approach)
**Why:** Cloud-native identity infrastructure

**Components:**
- **Kratos:** User management & authentication
- **Hydra:** OAuth2 & OIDC provider
- **Oathkeeper:** Identity & Access Proxy
- **Keto:** Authorization (permissions)

```yaml
# docker-compose.yml
services:
  kratos:
    image: oryd/kratos:latest
  hydra:
    image: oryd/hydra:latest
```

### 6. **Auth0/Okta SDK** (SaaS Solution)
**Why:** Managed service, no infrastructure needed

```bash
pip install auth0-python
```

**Pros:**
- Zero maintenance
- Enterprise features
- Compliance certifications
- Global availability

**Cons:**
- Monthly costs
- Vendor lock-in
- Data sovereignty concerns

## Implementation Recommendations

### For AgencyDark Specifically:

#### Option 1: **Authlib + Redis** (Minimal Changes)
Best for quick implementation with existing architecture.

```python
# backend/core/auth/oauth_provider.py
from authlib.integrations.starlette_client import OAuth
from authlib.integrations.base_client import OAuthError
import redis.asyncio as redis

class OAuthManager:
    def __init__(self, redis_client):
        self.oauth = OAuth()
        self.redis = redis_client
        
    def register_providers(self):
        # OnlyFans OAuth (if available)
        self.oauth.register(
            name='onlyfans',
            client_id=settings.ONLYFANS_CLIENT_ID,
            client_secret=settings.ONLYFANS_CLIENT_SECRET,
            authorize_url='https://onlyfans.com/oauth/authorize',
            token_url='https://onlyfans.com/oauth/token',
            client_kwargs={'scope': 'read:user read:messages'}
        )
        
        # Google OAuth for agency staff
        self.oauth.register(
            name='google',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
```

#### Option 2: **Keycloak** (Enterprise Solution)
Best for multi-tenant, enterprise requirements.

**Benefits for AgencyDark:**
- Separate realm per agency
- Custom authentication flows
- Integrate with existing user database
- Social login for models
- Admin portal for agency owners

**Deployment:**
```yaml
# docker-compose.yml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:latest
    environment:
      - KEYCLOAK_ADMIN=admin
      - KEYCLOAK_ADMIN_PASSWORD=admin
      - KC_DB=postgres
      - KC_DB_URL=jdbc:postgresql://postgres/keycloak
    ports:
      - "8080:8080"
    depends_on:
      - postgres
```

#### Option 3: **FastAPI-Users** (Complete Rewrite)
Best if willing to refactor authentication entirely.

**Migration Path:**
1. Install FastAPI-Users
2. Create user manager
3. Migrate existing users
4. Add OAuth providers
5. Update endpoints

## Security Considerations

### Must-Have Features:
1. **PKCE** (Proof Key for Code Exchange) - Essential for public clients
2. **State Parameter** - CSRF protection
3. **Nonce** - Replay attack protection
4. **Token Rotation** - Refresh token security
5. **JWK Rotation** - Key management

### Implementation Checklist:
- [ ] Use secure random state generation
- [ ] Validate redirect URIs
- [ ] Implement token expiration
- [ ] Store tokens encrypted
- [ ] Use HTTPS only
- [ ] Implement rate limiting
- [ ] Audit OAuth events
- [ ] Handle token revocation

## Migration Strategy

### Phase 1: Add OAuth Library (Week 1)
1. Install Authlib
2. Keep existing JWT auth
3. Add OAuth as secondary option
4. Test with single provider

### Phase 2: Provider Integration (Week 2-3)
1. Add Google OAuth
2. Add Microsoft/Azure AD
3. Add custom OIDC providers
4. Test multi-provider flow

### Phase 3: Migration (Week 4)
1. Migrate existing users
2. Add account linking
3. Deprecate old auth endpoints
4. Update documentation

### Phase 4: Advanced Features (Month 2)
1. Add SAML support
2. Implement SSO dashboard
3. Add MFA/2FA
4. Enterprise features

## Cost-Benefit Analysis

### Authlib (Recommended)
- **Cost:** Free (MIT License)
- **Time to Implement:** 1-2 weeks
- **Maintenance:** Low
- **Security:** High
- **Flexibility:** High

### Keycloak
- **Cost:** Free (Apache 2.0) + Infrastructure
- **Time to Implement:** 2-4 weeks
- **Maintenance:** Medium
- **Security:** Enterprise-grade
- **Flexibility:** Very High

### FastAPI-Users
- **Cost:** Free (MIT License)
- **Time to Implement:** 3-4 weeks (refactor)
- **Maintenance:** Low
- **Security:** Good
- **Flexibility:** Medium

## Conclusion

**Immediate Recommendation:** Implement **Authlib** for OAuth2.0/OIDC support while keeping the existing JWT authentication. This provides:
- Quick implementation (1-2 weeks)
- Minimal breaking changes
- Industry-standard security
- Support for multiple providers
- Easy integration with existing Redis/PostgreSQL

**Long-term Recommendation:** Deploy **Keycloak** as a dedicated identity provider for:
- Multi-agency isolation
- Enterprise SSO requirements
- Compliance needs
- Advanced authentication flows

This hybrid approach allows AgencyDark to quickly fix OAuth issues while planning for enterprise-scale identity management.

---
*Document created: November 2024*  
*Purpose: Evaluate OAuth2.0/SSO solutions for AgencyDark platform*