# OAuth Migration Detailed Subtasks

## Overview
This document provides granular subtasks for each phase of the OAuth migration, based on deep analysis of the AgencyDark codebase.

## Phase 1: Foundation (Week 1)

### Day 1-2: Dependencies & Database Setup

#### 1.1 Install Dependencies
```bash
# Core OAuth dependencies
- [x] pip install authlib[crypto]==1.3.0
- [x] pip install geoip2==4.8.0
- [x] pip install aiosmtplib==3.0.1
- [x] pip install python-multipart==0.0.6 (if not installed)

# Development dependencies
- [ ] pip install httpx-oauth==0.13.0 (for testing)
- [ ] pip install pytest-asyncio==0.21.1
- [ ] pip install pytest-mock==3.12.0
```

#### 1.2 Database Schema Creation
**File**: `backend/alembic/versions/043_add_oauth_tables.py`

- [ ] Create migration file using: `alembic revision -m "Add OAuth tables"`
- [ ] Define oauth_clients table schema
  - [ ] id (UUID, primary key)
  - [ ] agency_id (UUID, foreign key to agencies)
  - [ ] client_id (VARCHAR(48), unique, indexed)
  - [ ] client_secret (VARCHAR(120), encrypted)
  - [ ] client_name (VARCHAR(100))
  - [ ] redirect_uris (TEXT[])
  - [ ] grant_types (TEXT[], default=['authorization_code'])
  - [ ] response_types (TEXT[], default=['code'])
  - [ ] scope (TEXT)
  - [ ] allowed_agencies (UUID[])
  - [ ] created_at, updated_at timestamps

- [ ] Define oauth_tokens table schema
  - [ ] id (UUID, primary key)
  - [ ] agency_id (UUID, foreign key)
  - [ ] user_id (UUID, foreign key)
  - [ ] client_id (VARCHAR(48), foreign key)
  - [ ] token_type (VARCHAR(40))
  - [ ] access_token (VARCHAR(255), unique, indexed)
  - [ ] refresh_token (VARCHAR(255), unique, indexed)
  - [ ] scope (TEXT)
  - [ ] expires_at (TIMESTAMP)
  - [ ] extra_data (JSONB)
  - [ ] created_at timestamp

- [ ] Define oauth_authorization_codes table schema
  - [ ] id (UUID, primary key)
  - [ ] agency_id (UUID, foreign key)
  - [ ] user_id (UUID, foreign key)
  - [ ] client_id (VARCHAR(48), foreign key)
  - [ ] code (VARCHAR(120), unique, indexed)
  - [ ] redirect_uri (TEXT)
  - [ ] scope (TEXT)
  - [ ] code_challenge (VARCHAR(128))
  - [ ] code_challenge_method (VARCHAR(10))
  - [ ] expires_at (TIMESTAMP)
  - [ ] created_at timestamp

- [ ] Define external_oauth_tokens table (for Instagram, etc.)
  - [ ] id (UUID, primary key)
  - [ ] agency_id (UUID, foreign key)
  - [ ] user_id (UUID, foreign key)
  - [ ] provider (VARCHAR(50))
  - [ ] access_token (TEXT, encrypted)
  - [ ] refresh_token (TEXT, encrypted)
  - [ ] expires_at (TIMESTAMP)
  - [ ] scope (TEXT)
  - [ ] raw_data (TEXT, encrypted)
  - [ ] created_at, updated_at timestamps

#### 1.3 Update Existing Tables
- [ ] Alter users table
  - [ ] ADD COLUMN age_verified BOOLEAN DEFAULT FALSE
  - [ ] ADD COLUMN oauth_provider VARCHAR(50)
  - [ ] ADD COLUMN oauth_id VARCHAR(255)
  - [ ] ADD COLUMN oauth_metadata JSONB

- [ ] Create indexes
  - [ ] CREATE INDEX idx_oauth_clients_agency_id ON oauth_clients(agency_id)
  - [ ] CREATE INDEX idx_oauth_tokens_user_id ON oauth_tokens(user_id)
  - [ ] CREATE INDEX idx_oauth_tokens_expires_at ON oauth_tokens(expires_at)
  - [ ] CREATE INDEX idx_external_oauth_tokens_provider ON external_oauth_tokens(provider, user_id)

- [ ] Run migration: `alembic upgrade head`
- [ ] Verify tables created correctly

### Day 3-4: Core OAuth Implementation

#### 1.4 Create OAuth Directory Structure
```
backend/oauth/
├── __init__.py
├── models.py
├── provider.py
├── consumer.py
├── grants.py
├── validators.py
├── exceptions.py
└── utils.py
```

- [ ] Create directory structure
- [ ] Add __init__.py with proper exports

#### 1.5 Implement OAuth Models
**File**: `backend/oauth/models.py`

- [ ] Import SQLAlchemy and required types
- [ ] Create OAuthClient model class
  - [ ] Implement client_metadata property
  - [ ] Implement check_client_secret method
  - [ ] Add get_allowed_scope method
  - [ ] Add check_redirect_uri method
  - [ ] Add check_response_type method
  - [ ] Add check_grant_type method

- [ ] Create OAuthToken model class
  - [ ] Implement is_expired property
  - [ ] Implement is_refresh_token_active property
  - [ ] Add revoke method
  - [ ] Add to_dict method for serialization

- [ ] Create OAuthAuthorizationCode model class
  - [ ] Implement is_expired property
  - [ ] Add get_redirect_uri method
  - [ ] Add delete method

- [ ] Create ExternalOAuthToken model class
  - [ ] Implement encryption/decryption methods
  - [ ] Add token refresh logic
  - [ ] Add provider-specific metadata handling

#### 1.6 Implement OAuth Provider Base
**File**: `backend/oauth/provider.py`

- [ ] Import Authlib components
- [ ] Create MultiTenantAuthorizationCodeGrant class
  - [ ] Override save_authorization_code method
  - [ ] Override query_authorization_code method
  - [ ] Override delete_authorization_code method
  - [ ] Override authenticate_user method
  - [ ] Add agency_id validation to all methods

- [ ] Create MultiTenantRefreshTokenGrant class
  - [ ] Override authenticate_refresh_token method
  - [ ] Override authenticate_user method
  - [ ] Override revoke_old_credential method

- [ ] Create create_authorization_server function
  - [ ] Initialize AuthorizationServer
  - [ ] Register MultiTenantAuthorizationCodeGrant
  - [ ] Register RefreshTokenGrant
  - [ ] Register ClientCredentialsGrant
  - [ ] Configure PKCE as required

- [ ] Create create_resource_protector function
  - [ ] Initialize ResourceProtector
  - [ ] Register BearerTokenValidator
  - [ ] Add custom token introspection

### Day 5: Session Management & Compatibility

#### 1.7 Redis Session Manager Enhancement
**File**: `backend/services/session_manager.py`

- [ ] Create MultiTenantSessionManager class
  - [ ] Implement create_session method
    - [ ] Generate secure session_id
    - [ ] Store with agency-prefixed key
    - [ ] Set appropriate TTL
    - [ ] Track user sessions in set

  - [ ] Implement get_session method
    - [ ] Validate agency_id match
    - [ ] Update last_activity timestamp
    - [ ] Refresh TTL on access

  - [ ] Implement revoke_session method
    - [ ] Remove from user sessions set
    - [ ] Delete session key
    - [ ] Log revocation event

  - [ ] Implement revoke_all_user_sessions method
    - [ ] Get all session IDs for user
    - [ ] Batch delete all sessions
    - [ ] Clear user sessions set

  - [ ] Add session cleanup job
    - [ ] Scan for expired sessions
    - [ ] Remove orphaned session keys
    - [ ] Update metrics

#### 1.8 Compatibility Layer
**File**: `backend/oauth/compatibility.py`

- [ ] Create OAuth to JWT adapter
  - [ ] Convert OAuth tokens to JWT format
  - [ ] Map OAuth claims to JWT claims
  - [ ] Handle token refresh seamlessly

- [ ] Update CurrentUser dependency
  - [ ] Check for OAuth token first
  - [ ] Fall back to JWT if no OAuth
  - [ ] Maintain consistent user object

- [ ] Create migration utilities
  - [ ] Convert existing sessions to OAuth
  - [ ] Preserve user permissions
  - [ ] Handle role mappings

## Phase 2: OAuth Provider Implementation (Week 2)

### Day 6-7: Authorization Server

#### 2.1 OAuth Configuration
**File**: `backend/oauth/config.py`

- [ ] Create OAuthConfig class
  - [ ] ACCESS_TOKEN_LIFETIME (default: 3600)
  - [ ] REFRESH_TOKEN_LIFETIME (default: 1209600)
  - [ ] AUTHORIZATION_CODE_LIFETIME (default: 600)
  - [ ] REQUIRE_PKCE (default: True)
  - [ ] SUPPORTED_SCOPES list
  - [ ] ISSUER URL configuration

- [ ] Update .env.example
  - [ ] Add OAuth configuration variables
  - [ ] Document required settings
  - [ ] Provide development defaults

#### 2.2 Custom Grants Implementation
**File**: `backend/oauth/grants.py`

- [ ] Implement AgencyAuthorizationCodeGrant
  - [ ] Add validate_authorization_request
  - [ ] Add create_authorization_response
  - [ ] Implement agency-level scope validation
  - [ ] Add consent screen data preparation

- [ ] Implement AgencyPasswordGrant (for legacy support)
  - [ ] Validate username/password
  - [ ] Check agency membership
  - [ ] Generate appropriate tokens

- [ ] Implement AgencyClientCredentialsGrant
  - [ ] Validate client credentials
  - [ ] Check agency authorization
  - [ ] Issue M2M tokens

### Day 8-9: OAuth Endpoints

#### 2.3 Core OAuth Endpoints
**File**: `backend/api/v1/oauth.py`

- [ ] Create OAuth router
- [ ] Implement GET /oauth/authorize
  - [ ] Parse authorization request
  - [ ] Validate client_id
  - [ ] Check user authentication
  - [ ] Verify agency membership
  - [ ] Display consent screen
  - [ ] Handle user consent

- [ ] Implement POST /oauth/authorize
  - [ ] Process consent form
  - [ ] Generate authorization code
  - [ ] Store with PKCE challenge
  - [ ] Redirect with code

- [ ] Implement POST /oauth/token
  - [ ] Handle authorization_code grant
  - [ ] Handle refresh_token grant
  - [ ] Handle client_credentials grant
  - [ ] Validate PKCE verifier
  - [ ] Issue tokens with agency claims

- [ ] Implement POST /oauth/introspect
  - [ ] Validate requesting client
  - [ ] Check token validity
  - [ ] Return token metadata
  - [ ] Include agency information

- [ ] Implement POST /oauth/revoke
  - [ ] Accept access or refresh token
  - [ ] Validate token ownership
  - [ ] Revoke token and related tokens
  - [ ] Clean up sessions

#### 2.4 Discovery & Metadata
**File**: `backend/api/v1/oauth_metadata.py`

- [ ] Implement GET /.well-known/openid-configuration
  - [ ] Return issuer URL
  - [ ] List authorization_endpoint
  - [ ] List token_endpoint
  - [ ] List supported grant_types
  - [ ] List supported response_types
  - [ ] Include PKCE methods supported

- [ ] Implement GET /.well-known/oauth-authorization-server
  - [ ] OAuth 2.0 specific metadata
  - [ ] Token introspection endpoint
  - [ ] Token revocation endpoint
  - [ ] Supported scopes

### Day 10: Multi-Tenant Support

#### 2.5 Agency Isolation
**File**: `backend/oauth/multitenancy.py`

- [ ] Create get_current_agency dependency
  - [ ] Extract from subdomain
  - [ ] Extract from header
  - [ ] Extract from JWT claim
  - [ ] Validate agency exists

- [ ] Implement agency-scoped operations
  - [ ] Filter clients by agency
  - [ ] Scope tokens by agency
  - [ ] Validate cross-agency access

- [ ] Add agency validation middleware
  - [ ] Check every OAuth operation
  - [ ] Enforce agency boundaries
  - [ ] Log violations

#### 2.6 Consent Management
**File**: `backend/oauth/consent.py`

- [ ] Create consent storage model
  - [ ] User consent records
  - [ ] Scope approvals
  - [ ] Consent timestamps
  - [ ] Revocation tracking

- [ ] Implement consent UI templates
  - [ ] Create Jinja2 templates
  - [ ] Agency branding support
  - [ ] Scope descriptions
  - [ ] Remember consent option

## Phase 3: External OAuth Integration (Week 3)

### Day 11-12: OAuth Consumer

#### 3.1 External Provider Configuration
**File**: `backend/oauth/consumer.py`

- [ ] Create OAuth client registry
- [ ] Implement Instagram OAuth
  - [ ] Configure endpoints
  - [ ] Handle authorization flow
  - [ ] Process access tokens
  - [ ] Store encrypted tokens

- [ ] Implement Google OAuth
  - [ ] Configure discovery URL
  - [ ] Handle OIDC flow
  - [ ] Validate ID tokens
  - [ ] Extract user info

- [ ] Implement Microsoft OAuth
  - [ ] Configure Azure AD endpoints
  - [ ] Handle multi-tenant apps
  - [ ] Process claims
  - [ ] Handle group memberships

- [ ] Prepare OnlyFans OAuth (stub)
  - [ ] Placeholder configuration
  - [ ] Documentation for future
  - [ ] Webhook readiness

#### 3.2 External OAuth Endpoints
**File**: `backend/api/v1/external_oauth.py`

- [ ] GET /oauth/connect/{provider}
  - [ ] Validate provider
  - [ ] Generate state parameter
  - [ ] Store state in Redis
  - [ ] Build authorization URL
  - [ ] Redirect to provider

- [ ] GET /oauth/callback/{provider}
  - [ ] Validate state parameter
  - [ ] Exchange code for token
  - [ ] Encrypt and store tokens
  - [ ] Link to user account
  - [ ] Handle errors gracefully

- [ ] POST /oauth/disconnect/{provider}
  - [ ] Verify user ownership
  - [ ] Revoke provider tokens
  - [ ] Remove stored tokens
  - [ ] Update user account

### Day 13-14: Token Security

#### 3.3 Token Encryption
**File**: `backend/oauth/encryption.py`

- [ ] Implement encryption service
  - [ ] Use Fernet for symmetric encryption
  - [ ] Rotate encryption keys
  - [ ] Handle key versioning
  - [ ] Implement secure key storage

- [ ] Create token storage service
  - [ ] Encrypt before storage
  - [ ] Decrypt on retrieval
  - [ ] Handle token refresh
  - [ ] Implement TTL management

#### 3.4 Webhook Handlers
**File**: `backend/api/v1/oauth_webhooks.py`

- [ ] Implement provider webhooks
  - [ ] Token revocation webhooks
  - [ ] Account deactivation
  - [ ] Security alerts
  - [ ] Rate limit notifications

- [ ] Add webhook validation
  - [ ] Verify signatures
  - [ ] Validate timestamps
  - [ ] Check source IPs
  - [ ] Log all events

## Phase 4: Security & Compliance (Week 4)

### Day 15-16: Adult Content Middleware

#### 4.1 Security Middleware
**File**: `backend/middleware/adult_security.py`

- [ ] Implement AdultContentSecurityMiddleware
  - [ ] GeoIP initialization
  - [ ] Country code extraction
  - [ ] Blocking logic
  - [ ] Custom error responses

- [ ] Add geo-blocking
  - [ ] Load restricted countries list
  - [ ] Check each request
  - [ ] Log blocked attempts
  - [ ] Provide bypass for testing

- [ ] Implement age gates
  - [ ] Check age_verified flag
  - [ ] Redirect to verification
  - [ ] Set verification cookies
  - [ ] Handle exemptions

#### 4.2 Security Headers
**File**: `backend/middleware/security_headers.py`

- [ ] Add security headers
  - [ ] X-Content-Type-Options: nosniff
  - [ ] X-Frame-Options: DENY
  - [ ] X-XSS-Protection: 1; mode=block
  - [ ] Referrer-Policy: strict-origin
  - [ ] Content-Security-Policy
  - [ ] Strict-Transport-Security

- [ ] Configure CORS properly
  - [ ] Allowed origins per agency
  - [ ] Credential support
  - [ ] Preflight caching
  - [ ] Method restrictions

### Day 17-18: Age Verification

#### 4.3 Age Verification Service
**File**: `backend/services/age_verification.py`

- [ ] Create base verification service
  - [ ] Provider abstraction
  - [ ] Common interface
  - [ ] Result caching
  - [ ] Audit logging

- [ ] Implement Yoti integration
  - [ ] API client setup
  - [ ] Document upload
  - [ ] Verification flow
  - [ ] Result processing

- [ ] Implement VerifyMyAge integration
  - [ ] API configuration
  - [ ] Age check flow
  - [ ] Token validation
  - [ ] Compliance reporting

#### 4.4 Verification Endpoints
**File**: `backend/api/v1/age_verification.py`

- [ ] POST /verify/age/start
  - [ ] Initiate verification
  - [ ] Choose provider
  - [ ] Generate session
  - [ ] Return redirect URL

- [ ] GET /verify/age/callback
  - [ ] Process verification result
  - [ ] Update user record
  - [ ] Set verification cookie
  - [ ] Redirect to app

- [ ] GET /verify/age/status
  - [ ] Check verification status
  - [ ] Return expiry info
  - [ ] Provide re-verify option

## Phase 5: Migration & Testing (Week 5)

### Day 19-20: User Migration

#### 5.1 Migration Script
**File**: `backend/scripts/migrate_to_oauth.py`

- [ ] Create migration script structure
  - [ ] Command-line arguments
  - [ ] Progress tracking
  - [ ] Error handling
  - [ ] Rollback capability

- [ ] Implement user migration
  - [ ] Query existing users
  - [ ] Create OAuth clients per agency
  - [ ] Generate client credentials
  - [ ] Store securely

- [ ] Convert sessions
  - [ ] Read existing JWT sessions
  - [ ] Create OAuth tokens
  - [ ] Preserve expiry times
  - [ ] Maintain user context

- [ ] Migrate API keys
  - [ ] Convert to OAuth clients
  - [ ] Set appropriate scopes
  - [ ] Update rate limits
  - [ ] Preserve key metadata

#### 5.2 Data Validation
**File**: `backend/scripts/validate_migration.py`

- [ ] Validate migrated data
  - [ ] Check user accounts
  - [ ] Verify token validity
  - [ ] Test authentication flows
  - [ ] Compare permissions

- [ ] Generate migration report
  - [ ] Success statistics
  - [ ] Failed migrations
  - [ ] Warning conditions
  - [ ] Remediation steps

### Day 21-22: Testing

#### 5.3 Unit Tests
**File**: `backend/tests/unit/test_oauth.py`

- [ ] Test OAuth grants
  - [ ] Authorization code grant
  - [ ] PKCE validation
  - [ ] Refresh token grant
  - [ ] Client credentials grant

- [ ] Test token operations
  - [ ] Token generation
  - [ ] Token validation
  - [ ] Token introspection
  - [ ] Token revocation

- [ ] Test multi-tenancy
  - [ ] Agency isolation
  - [ ] Cross-agency denial
  - [ ] Scope validation
  - [ ] Permission checks

#### 5.4 Integration Tests
**File**: `backend/tests/integration/test_oauth_flow.py`

- [ ] Test complete OAuth flows
  - [ ] Authorization flow
  - [ ] Token exchange
  - [ ] Token refresh
  - [ ] Session management

- [ ] Test external OAuth
  - [ ] Provider connections
  - [ ] Callback handling
  - [ ] Token storage
  - [ ] Account linking

- [ ] Test security features
  - [ ] Geo-blocking
  - [ ] Age verification
  - [ ] Rate limiting
  - [ ] CSRF protection

#### 5.5 Load Testing
**File**: `backend/tests/load/test_oauth_performance.py`

- [ ] Create load test scenarios
  - [ ] Concurrent authorizations
  - [ ] Token generation rate
  - [ ] Introspection performance
  - [ ] Database query optimization

- [ ] Measure performance metrics
  - [ ] Response times
  - [ ] Throughput
  - [ ] Error rates
  - [ ] Resource usage

## Phase 6: Cutover & Cleanup (Week 6)

### Day 23: Feature Flags

#### 6.1 Feature Flag Implementation
**File**: `backend/core/feature_flags.py`

- [ ] Create feature flag system
  - [ ] OAuth enable/disable
  - [ ] Per-agency control
  - [ ] Gradual rollout
  - [ ] Emergency killswitch

- [ ] Implement flag checks
  - [ ] Authentication routing
  - [ ] Endpoint availability
  - [ ] UI feature toggles
  - [ ] API versioning

### Day 24-25: Complete Migration

#### 6.2 Cutover Process
- [ ] Enable OAuth for test agency
- [ ] Monitor for 24 hours
- [ ] Enable for 10% of agencies
- [ ] Monitor metrics and errors
- [ ] Enable for 50% of agencies
- [ ] Final monitoring period
- [ ] Enable for all agencies
- [ ] Disable JWT fallback

#### 6.3 Code Cleanup
**Files to Remove/Archive**:

- [ ] Archive old JWT implementation
  - [ ] Move to archive/ directory
  - [ ] Document removal reason
  - [ ] Keep for reference

- [ ] Remove deprecated endpoints
  - [ ] Old /auth endpoints
  - [ ] Legacy session endpoints
  - [ ] Deprecated middleware

- [ ] Update imports
  - [ ] Replace JWT imports
  - [ ] Update CurrentUser usage
  - [ ] Fix test imports

- [ ] Clean up configuration
  - [ ] Remove JWT settings
  - [ ] Update .env.example
  - [ ] Update documentation

### Day 26: Monitoring

#### 6.4 Monitoring Setup
**File**: `backend/monitoring/oauth_metrics.py`

- [ ] Create OAuth metrics
  - [ ] Authorization success rate
  - [ ] Token generation rate
  - [ ] Provider usage stats
  - [ ] Error tracking

- [ ] Set up alerts
  - [ ] High error rates
  - [ ] Slow response times
  - [ ] Provider outages
  - [ ] Security violations

- [ ] Create dashboards
  - [ ] Real-time metrics
  - [ ] Historical trends
  - [ ] Provider breakdown
  - [ ] Agency statistics

## Post-Migration Tasks

### Documentation Updates
- [ ] Update API documentation
- [ ] Create OAuth integration guide
- [ ] Update security documentation
- [ ] Create troubleshooting guide
- [ ] Update developer onboarding

### Training & Support
- [ ] Create training materials
- [ ] Conduct team training
- [ ] Update support scripts
- [ ] Create FAQ document
- [ ] Prepare rollback procedures

### Optimization
- [ ] Database index optimization
- [ ] Redis cache tuning
- [ ] Connection pool sizing
- [ ] Query optimization
- [ ] Rate limit adjustments

## Success Criteria

### Technical Metrics
- [ ] 100% of users successfully migrated
- [ ] OAuth endpoints respond < 100ms p95
- [ ] Zero data loss during migration
- [ ] 99.9% authentication success rate
- [ ] All tests passing

### Business Metrics
- [ ] No increase in support tickets
- [ ] User satisfaction maintained
- [ ] No service disruptions
- [ ] Compliance requirements met
- [ ] Security audit passed

## Risk Register

### High Risk Items
1. **Session disruption during migration**
   - Mitigation: Parallel authentication
   - Contingency: Immediate rollback

2. **Provider API changes**
   - Mitigation: Version pinning
   - Contingency: Multiple providers

3. **Performance degradation**
   - Mitigation: Load testing
   - Contingency: Scaling plan

### Medium Risk Items
1. **User confusion with new flow**
   - Mitigation: Clear communication
   - Contingency: Support documentation

2. **External provider outages**
   - Mitigation: Multiple providers
   - Contingency: Local auth fallback

## Dependencies Tracking

### External Dependencies
- [ ] Authlib library stability
- [ ] PostgreSQL 13+ features
- [ ] Redis 6+ availability
- [ ] Age verification API access
- [ ] GeoIP database updates

### Internal Dependencies
- [ ] Frontend team readiness
- [ ] DevOps infrastructure
- [ ] QA team availability
- [ ] Security team approval
- [ ] Management sign-off

---

This comprehensive subtask list provides 200+ actionable items for implementing OAuth2.0 in AgencyDark, ensuring nothing is overlooked during the migration process.