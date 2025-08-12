# OAuth 2.0 API Endpoints Documentation

## Overview
This document provides comprehensive documentation for all OAuth 2.0 endpoints implemented in the Agency Dark platform. Our implementation follows RFC 6749 (OAuth 2.0) and RFC 7636 (PKCE) standards with additional security enhancements.

## Table of Contents
- [Authorization Endpoint](#authorization-endpoint)
- [Token Endpoint](#token-endpoint)
- [Introspection Endpoint](#introspection-endpoint)
- [Revocation Endpoint](#revocation-endpoint)
- [User Info Endpoint](#user-info-endpoint)
- [Discovery Endpoint](#discovery-endpoint)

---

## Authorization Endpoint

### Endpoint
```
GET /oauth/authorize
```

### Description
Initiates the OAuth 2.0 authorization flow. This endpoint authenticates the resource owner and obtains authorization to access protected resources.

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `response_type` | string | Yes | Must be `code` for authorization code flow |
| `client_id` | string | Yes | The client identifier issued during registration |
| `redirect_uri` | string | Yes | The callback URL where the authorization code will be sent |
| `scope` | string | No | Space-delimited list of requested permissions |
| `state` | string | Recommended | Opaque value for maintaining state between request and callback |
| `code_challenge` | string | Required for public clients | Base64-URL-encoded SHA256 hash of the code verifier (PKCE) |
| `code_challenge_method` | string | Required with code_challenge | Must be `S256` |
| `agency_id` | string | No | For multi-tenant scenarios, specifies the agency context |
| `prompt` | string | No | `none`, `login`, `consent`, or `select_account` |
| `max_age` | integer | No | Maximum authentication age in seconds |

### Response

#### Success Response
Redirects to the specified `redirect_uri` with:
```
HTTP/1.1 302 Found
Location: https://client.example.com/callback?
  code=SFxqY3BXNEpLUmxzYkJZUGJLNDM5&
  state=af0ifjsldkj
```

#### Error Response
Redirects to the specified `redirect_uri` with:
```
HTTP/1.1 302 Found
Location: https://client.example.com/callback?
  error=invalid_request&
  error_description=Missing+required+parameter+client_id&
  state=af0ifjsldkj
```

### Error Codes

| Code | Description |
|------|-------------|
| `invalid_request` | The request is missing a required parameter or includes an invalid parameter value |
| `unauthorized_client` | The client is not authorized to request an authorization code |
| `access_denied` | The resource owner or authorization server denied the request |
| `unsupported_response_type` | The authorization server does not support obtaining an authorization code using this method |
| `invalid_scope` | The requested scope is invalid, unknown, or malformed |
| `server_error` | The authorization server encountered an unexpected condition |
| `temporarily_unavailable` | The authorization server is currently unable to handle the request |

### Example Request
```bash
curl -X GET "https://api.agencydark.com/oauth/authorize?\
response_type=code&\
client_id=abc123&\
redirect_uri=https://myapp.com/callback&\
scope=read:profile%20write:campaigns&\
state=xyz789&\
code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&\
code_challenge_method=S256"
```

### Security Considerations
- Always validate the `redirect_uri` against pre-registered values
- Use PKCE for all public clients (mobile apps, SPAs)
- Implement CSRF protection using the `state` parameter
- Authorization codes expire after 10 minutes
- Each authorization code can only be used once

---

## Token Endpoint

### Endpoint
```
POST /oauth/token
```

### Description
Exchanges authorization codes for access tokens, refreshes access tokens, and supports client credentials grant.

### Request Headers
```
Content-Type: application/x-www-form-urlencoded
Authorization: Basic {base64(client_id:client_secret)}
```

### Request Parameters

#### Authorization Code Grant

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `grant_type` | string | Yes | Must be `authorization_code` |
| `code` | string | Yes | The authorization code received from the authorization endpoint |
| `redirect_uri` | string | Yes | Must match the redirect URI used in the authorization request |
| `code_verifier` | string | Required for PKCE | The code verifier for the PKCE request |
| `client_id` | string | Required if no Authorization header | The client identifier |
| `client_secret` | string | Required for confidential clients | The client secret |

#### Refresh Token Grant

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `grant_type` | string | Yes | Must be `refresh_token` |
| `refresh_token` | string | Yes | The refresh token issued to the client |
| `scope` | string | No | Requested scope (must not exceed original scope) |

#### Client Credentials Grant

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `grant_type` | string | Yes | Must be `client_credentials` |
| `scope` | string | No | Space-delimited list of requested permissions |

### Response

#### Success Response
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "8xLOxBtZp8",
  "scope": "read:profile write:campaigns",
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Error Response
```json
{
  "error": "invalid_grant",
  "error_description": "The provided authorization code is invalid or has expired"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `invalid_request` | The request is missing a required parameter or includes an unsupported parameter value |
| `invalid_client` | Client authentication failed |
| `invalid_grant` | The provided authorization grant is invalid, expired, or revoked |
| `unauthorized_client` | The authenticated client is not authorized to use this authorization grant type |
| `unsupported_grant_type` | The authorization grant type is not supported by the authorization server |
| `invalid_scope` | The requested scope is invalid, unknown, malformed, or exceeds the scope granted |

### Example Requests

#### Authorization Code Exchange
```bash
curl -X POST https://api.agencydark.com/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic YWJjMTIzOm15c2VjcmV0" \
  -d "grant_type=authorization_code&\
code=SFxqY3BXNEpLUmxzYkJZUGJLNDM5&\
redirect_uri=https://myapp.com/callback&\
code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
```

#### Refresh Token
```bash
curl -X POST https://api.agencydark.com/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic YWJjMTIzOm15c2VjcmV0" \
  -d "grant_type=refresh_token&\
refresh_token=8xLOxBtZp8"
```

### Security Considerations
- Access tokens expire after 1 hour by default
- Refresh tokens expire after 30 days of inactivity
- Implement rate limiting to prevent brute force attacks
- Use TLS for all token endpoint requests
- Store refresh tokens securely (encrypted at rest)

---

## Introspection Endpoint

### Endpoint
```
POST /oauth/introspect
```

### Description
Allows resource servers to query the authorization server to determine the active state of an OAuth 2.0 token and its metadata.

### Request Headers
```
Content-Type: application/x-www-form-urlencoded
Authorization: Bearer {access_token} OR Basic {base64(client_id:client_secret)}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `token` | string | Yes | The token to be introspected |
| `token_type_hint` | string | No | A hint about the type of the token (`access_token` or `refresh_token`) |

### Response

#### Active Token Response
```json
{
  "active": true,
  "scope": "read:profile write:campaigns",
  "client_id": "abc123",
  "username": "user@example.com",
  "token_type": "Bearer",
  "exp": 1681923600,
  "iat": 1681920000,
  "nbf": 1681920000,
  "sub": "user:12345",
  "aud": ["https://api.agencydark.com"],
  "iss": "https://auth.agencydark.com",
  "jti": "token-unique-id",
  "agency_id": "agency_456",
  "permissions": ["campaigns.read", "campaigns.write", "profile.read"]
}
```

#### Inactive Token Response
```json
{
  "active": false
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | boolean | Indicates whether the token is currently active |
| `scope` | string | Space-separated list of scopes |
| `client_id` | string | Client identifier for the token |
| `username` | string | Human-readable identifier for the resource owner |
| `token_type` | string | Type of the token (usually "Bearer") |
| `exp` | integer | Expiration time (Unix timestamp) |
| `iat` | integer | Issue time (Unix timestamp) |
| `nbf` | integer | Not before time (Unix timestamp) |
| `sub` | string | Subject identifier |
| `aud` | array | Intended audience |
| `iss` | string | Token issuer |
| `jti` | string | JWT ID (unique identifier) |
| `agency_id` | string | Agency context for multi-tenant scenarios |
| `permissions` | array | Detailed permission list |

### Example Request
```bash
curl -X POST https://api.agencydark.com/oauth/introspect \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic YWJjMTIzOm15c2VjcmV0" \
  -d "token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...&\
token_type_hint=access_token"
```

### Security Considerations
- Introspection requests must be authenticated
- Implement rate limiting to prevent token scanning
- Cache introspection results for performance (with appropriate TTL)
- Log all introspection requests for audit purposes

---

## Revocation Endpoint

### Endpoint
```
POST /oauth/revoke
```

### Description
Revokes an access token or refresh token, immediately invalidating it across all resource servers.

### Request Headers
```
Content-Type: application/x-www-form-urlencoded
Authorization: Basic {base64(client_id:client_secret)}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `token` | string | Yes | The token to be revoked |
| `token_type_hint` | string | No | A hint about the type of the token (`access_token` or `refresh_token`) |

### Response

#### Success Response
```
HTTP/1.1 200 OK
```

The server responds with HTTP 200 regardless of whether the token was found or not (to prevent token scanning).

#### Error Response
```json
{
  "error": "unsupported_token_type",
  "error_description": "The authorization server does not support revocation of this token type"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `unsupported_token_type` | The authorization server does not support revocation of the presented token type |
| `invalid_client` | Client authentication failed |

### Example Request
```bash
curl -X POST https://api.agencydark.com/oauth/revoke \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Authorization: Basic YWJjMTIzOm15c2VjcmV0" \
  -d "token=8xLOxBtZp8&\
token_type_hint=refresh_token"
```

### Security Considerations
- Revoking a refresh token also revokes all associated access tokens
- Implement immediate propagation to all resource servers
- Log all revocation requests for audit purposes
- Allow users to revoke their own tokens through the UI
- Support bulk revocation for compromised clients

---

## User Info Endpoint

### Endpoint
```
GET /oauth/userinfo
```

### Description
Returns claims about the authenticated user. This endpoint is protected and requires a valid access token.

### Request Headers
```
Authorization: Bearer {access_token}
```

### Response

#### Success Response
```json
{
  "sub": "user:12345",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "email_verified": true,
  "picture": "https://cdn.agencydark.com/users/12345/photo.jpg",
  "agency_id": "agency_456",
  "agency_name": "Creative Agency Inc.",
  "roles": ["admin", "campaign_manager"],
  "permissions": [
    "campaigns.read",
    "campaigns.write",
    "campaigns.delete",
    "users.read",
    "analytics.read"
  ],
  "locale": "en-US",
  "timezone": "America/New_York",
  "created_at": "2023-01-15T10:30:00Z",
  "updated_at": "2024-01-10T14:20:00Z"
}
```

#### Error Response
```json
{
  "error": "invalid_token",
  "error_description": "The access token is invalid or has expired"
}
```

### Example Request
```bash
curl -X GET https://api.agencydark.com/oauth/userinfo \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Discovery Endpoint

### Endpoint
```
GET /.well-known/oauth-authorization-server
```

### Description
Provides metadata about the OAuth 2.0 authorization server configuration.

### Response
```json
{
  "issuer": "https://auth.agencydark.com",
  "authorization_endpoint": "https://api.agencydark.com/oauth/authorize",
  "token_endpoint": "https://api.agencydark.com/oauth/token",
  "introspection_endpoint": "https://api.agencydark.com/oauth/introspect",
  "revocation_endpoint": "https://api.agencydark.com/oauth/revoke",
  "userinfo_endpoint": "https://api.agencydark.com/oauth/userinfo",
  "jwks_uri": "https://api.agencydark.com/.well-known/jwks.json",
  "registration_endpoint": "https://api.agencydark.com/oauth/register",
  "scopes_supported": [
    "openid",
    "profile",
    "email",
    "read:campaigns",
    "write:campaigns",
    "delete:campaigns",
    "read:analytics",
    "read:users",
    "write:users",
    "admin"
  ],
  "response_types_supported": ["code", "token", "id_token"],
  "response_modes_supported": ["query", "fragment"],
  "grant_types_supported": [
    "authorization_code",
    "refresh_token",
    "client_credentials"
  ],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["RS256"],
  "token_endpoint_auth_methods_supported": [
    "client_secret_basic",
    "client_secret_post",
    "private_key_jwt"
  ],
  "code_challenge_methods_supported": ["S256"],
  "claims_supported": [
    "sub",
    "name",
    "email",
    "email_verified",
    "picture",
    "agency_id",
    "roles",
    "permissions"
  ],
  "service_documentation": "https://docs.agencydark.com/oauth",
  "ui_locales_supported": ["en-US", "es-ES", "fr-FR"],
  "claims_parameter_supported": true,
  "request_parameter_supported": false,
  "request_uri_parameter_supported": false,
  "require_request_uri_registration": false,
  "op_policy_uri": "https://agencydark.com/privacy",
  "op_tos_uri": "https://agencydark.com/terms"
}
```

### Example Request
```bash
curl -X GET https://api.agencydark.com/.well-known/oauth-authorization-server
```

---

## Rate Limiting

All OAuth endpoints implement rate limiting to prevent abuse:

| Endpoint | Rate Limit | Window |
|----------|------------|---------|
| Authorization | 20 requests | per minute per IP |
| Token | 60 requests | per minute per client |
| Introspection | 100 requests | per minute per client |
| Revocation | 30 requests | per minute per client |
| User Info | 60 requests | per minute per user |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when the rate limit resets

---

## Webhook Events

The OAuth system can send webhooks for the following events:

| Event | Description |
|-------|-------------|
| `token.issued` | New access token issued |
| `token.refreshed` | Access token refreshed |
| `token.revoked` | Token revoked |
| `authorization.granted` | User granted authorization |
| `authorization.denied` | User denied authorization |
| `client.blocked` | Client blocked due to suspicious activity |

Webhook payloads are signed using HMAC-SHA256 with a shared secret.

---

## Migration from JWT

For clients migrating from the legacy JWT authentication:

1. Register your application to obtain OAuth client credentials
2. Update authentication flows to use OAuth endpoints
3. Implement PKCE for public clients
4. Update token storage to handle OAuth tokens
5. Implement token refresh logic
6. Update API calls to use Bearer tokens

Detailed migration guide available at: [JWT to OAuth Migration Guide](../guides/jwt-to-oauth-migration.md)

---

## Support

For technical support and questions:
- Documentation: https://docs.agencydark.com/oauth
- API Status: https://status.agencydark.com
- Support Email: oauth-support@agencydark.com
- Developer Forum: https://forum.agencydark.com/oauth