# External OAuth Provider Setup Guide

## Overview
This guide provides step-by-step instructions for configuring external OAuth providers (Google, Instagram, Microsoft) with the Agency Dark platform, enabling social login and account linking features.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Google OAuth Setup](#google-oauth-setup)
- [Instagram OAuth Setup](#instagram-oauth-setup)
- [Microsoft OAuth Setup](#microsoft-oauth-setup)
- [Generic OAuth Provider](#generic-oauth-provider)
- [Provider Configuration](#provider-configuration)
- [Webhook Configuration](#webhook-configuration)
- [Testing Providers](#testing-providers)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before configuring external providers:

1. **Admin Access**: Ensure you have admin access to Agency Dark
2. **Provider Accounts**: Create developer accounts with each provider
3. **SSL Certificate**: Your application must use HTTPS
4. **Redirect URIs**: Have your OAuth callback URLs ready

---

## Google OAuth Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable Google+ API and Google Identity API

### Step 2: Configure OAuth Consent Screen

```
1. Navigate to APIs & Services > OAuth consent screen
2. Choose User Type:
   - Internal: For G Suite users only
   - External: For any Google account

3. Fill in Application Information:
   - App name: Agency Dark
   - User support email: support@agencydark.com
   - App logo: Upload your logo
   - App domain: https://agencydark.com
   - Privacy policy: https://agencydark.com/privacy
   - Terms of service: https://agencydark.com/terms

4. Add Scopes:
   - openid
   - email
   - profile
   - https://www.googleapis.com/auth/userinfo.email
   - https://www.googleapis.com/auth/userinfo.profile

5. Add Test Users (if in development)
```

### Step 3: Create OAuth Credentials

```
1. Go to APIs & Services > Credentials
2. Click "Create Credentials" > "OAuth client ID"
3. Select Application Type: Web application
4. Configure:
   - Name: Agency Dark Production
   - Authorized JavaScript origins:
     - https://agencydark.com
     - https://app.agencydark.com
   - Authorized redirect URIs:
     - https://api.agencydark.com/oauth/callback/google
     - https://app.agencydark.com/auth/google/callback

5. Save and note:
   - Client ID: 123456789.apps.googleusercontent.com
   - Client Secret: GOCSPX-xxxxxxxxxxxxx
```

### Step 4: Configure in Agency Dark

```python
# backend/config/oauth_providers.py
GOOGLE_OAUTH = {
    "client_id": "123456789.apps.googleusercontent.com",
    "client_secret": env("GOOGLE_CLIENT_SECRET"),
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "userinfo_endpoint": "https://www.googleapis.com/oauth2/v2/userinfo",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
    "scopes": ["openid", "email", "profile"],
    "response_type": "code",
    "access_type": "offline",  # For refresh tokens
    "prompt": "consent",  # Force consent to get refresh token
    "hosted_domain": None,  # Set to limit to specific G Suite domain
}
```

### Step 5: Implement Google Login Button

```tsx
// frontend/src/components/auth/GoogleLogin.tsx
import React from 'react';
import { FaGoogle } from 'react-icons/fa';

export const GoogleLogin: React.FC = () => {
  const handleGoogleLogin = () => {
    const params = new URLSearchParams({
      client_id: process.env.REACT_APP_GOOGLE_CLIENT_ID,
      redirect_uri: `${window.location.origin}/auth/google/callback`,
      response_type: 'code',
      scope: 'openid email profile',
      access_type: 'offline',
      prompt: 'consent',
      state: generateState(),
    });

    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
  };

  return (
    <button 
      onClick={handleGoogleLogin}
      className="google-login-btn"
    >
      <FaGoogle /> Sign in with Google
    </button>
  );
};
```

---

## Instagram OAuth Setup

### Step 1: Create Facebook App

Instagram OAuth requires a Facebook App:

1. Go to [Facebook Developers](https://developers.facebook.com)
2. Create a new app or select existing
3. Choose app type: "Consumer" or "Business"

### Step 2: Add Instagram Basic Display

```
1. In your app dashboard, click "Add Product"
2. Find "Instagram Basic Display" and click "Set Up"
3. Click "Create New App" under Instagram Basic Display
4. Fill in:
   - Display Name: Agency Dark
   - Contact Email: support@agencydark.com
```

### Step 3: Configure Instagram App

```
1. Go to Instagram Basic Display > Basic Display
2. Add OAuth Redirect URIs:
   - https://api.agencydark.com/oauth/callback/instagram
   - https://app.agencydark.com/auth/instagram/callback

3. Add Deauthorize Callback URL:
   - https://api.agencydark.com/oauth/instagram/deauthorize

4. Add Data Deletion Request URL:
   - https://api.agencydark.com/oauth/instagram/delete

5. Add Instagram Testers:
   - Settings > Roles > Instagram Testers
   - Add test Instagram accounts
```

### Step 4: Get Instagram Credentials

```
Instagram Basic Display > Basic Display

- Instagram App ID: 123456789
- Instagram App Secret: abcdef123456
- Client OAuth Settings: Enabled
```

### Step 5: Configure in Agency Dark

```python
# backend/config/oauth_providers.py
INSTAGRAM_OAUTH = {
    "client_id": env("INSTAGRAM_APP_ID"),
    "client_secret": env("INSTAGRAM_APP_SECRET"),
    "authorization_endpoint": "https://api.instagram.com/oauth/authorize",
    "token_endpoint": "https://api.instagram.com/oauth/access_token",
    "userinfo_endpoint": "https://graph.instagram.com/me",
    "scopes": ["user_profile", "user_media"],
    "response_type": "code",
    "fields": "id,username,account_type,media_count",
    "exchange_endpoint": "https://graph.instagram.com/access_token",  # For long-lived tokens
}
```

### Step 6: Handle Instagram Token Exchange

```python
# backend/oauth/providers/instagram.py
class InstagramOAuthProvider:
    async def exchange_for_long_lived_token(self, short_token: str) -> str:
        """Exchange short-lived token for long-lived token (60 days)"""
        response = await httpx.get(
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self.client_secret,
                "access_token": short_token
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]
    
    async def refresh_long_lived_token(self, token: str) -> str:
        """Refresh long-lived token before expiry"""
        response = await httpx.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": token
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]
```

---

## Microsoft OAuth Setup

### Step 1: Register Application in Azure

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to Azure Active Directory > App registrations
3. Click "New registration"

### Step 2: Configure Application

```
1. Register an application:
   - Name: Agency Dark
   - Supported account types:
     * Single tenant (this directory only)
     * Multi-tenant (any Azure AD directory)
     * Personal Microsoft accounts only
     * Multi-tenant and personal accounts (recommended)
   
   - Redirect URI:
     - Platform: Web
     - URI: https://api.agencydark.com/oauth/callback/microsoft

2. Note the Application (client) ID

3. Go to Certificates & secrets:
   - New client secret
   - Description: Production Secret
   - Expires: 24 months
   - Note the secret value (shown only once)
```

### Step 3: Configure API Permissions

```
1. Go to API permissions
2. Add permissions:
   - Microsoft Graph:
     * User.Read (Delegated)
     * email (Delegated)
     * openid (Delegated)
     * profile (Delegated)
     * offline_access (Delegated) - for refresh tokens

3. Grant admin consent (if required)
```

### Step 4: Configure in Agency Dark

```python
# backend/config/oauth_providers.py
MICROSOFT_OAUTH = {
    "client_id": env("MICROSOFT_CLIENT_ID"),
    "client_secret": env("MICROSOFT_CLIENT_SECRET"),
    "tenant": "common",  # or specific tenant ID
    "authorization_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    "token_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "userinfo_endpoint": "https://graph.microsoft.com/v1.0/me",
    "jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
    "scopes": ["openid", "email", "profile", "User.Read", "offline_access"],
    "response_type": "code",
    "response_mode": "query",
    "prompt": "select_account",
}
```

### Step 5: Handle Microsoft-Specific Features

```python
# backend/oauth/providers/microsoft.py
class MicrosoftOAuthProvider:
    async def get_user_photo(self, access_token: str) -> bytes:
        """Get user's profile photo from Microsoft Graph"""
        response = await httpx.get(
            "https://graph.microsoft.com/v1.0/me/photo/$value",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code == 200:
            return response.content
        return None
    
    async def get_user_groups(self, access_token: str) -> list:
        """Get user's AD groups for enterprise scenarios"""
        response = await httpx.get(
            "https://graph.microsoft.com/v1.0/me/memberOf",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json().get("value", [])
```

---

## Generic OAuth Provider

### Configuration Template

For any OAuth 2.0 compliant provider:

```python
# backend/config/oauth_providers.py
GENERIC_OAUTH = {
    "provider_name": "Custom Provider",
    "client_id": env("CUSTOM_CLIENT_ID"),
    "client_secret": env("CUSTOM_CLIENT_SECRET"),
    "authorization_endpoint": "https://provider.com/oauth/authorize",
    "token_endpoint": "https://provider.com/oauth/token",
    "userinfo_endpoint": "https://provider.com/oauth/userinfo",
    "jwks_uri": "https://provider.com/.well-known/jwks.json",  # Optional
    "scopes": ["openid", "email", "profile"],
    "response_type": "code",
    "grant_types": ["authorization_code", "refresh_token"],
    
    # Field mappings for user info
    "user_field_mappings": {
        "id": "sub",
        "email": "email",
        "name": "name",
        "picture": "avatar_url",
        "username": "preferred_username"
    },
    
    # Custom headers if needed
    "custom_headers": {
        "X-API-Version": "2.0"
    },
    
    # Token configuration
    "token_auth_method": "client_secret_basic",  # or client_secret_post
    "pkce_required": False,
    
    # Additional parameters
    "additional_params": {
        "audience": "https://api.provider.com"
    }
}
```

### Generic Provider Implementation

```python
# backend/oauth/providers/generic.py
from typing import Dict, Any, Optional
import httpx
from urllib.parse import urlencode

class GenericOAuthProvider:
    """
    Generic OAuth 2.0 provider implementation
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
    
    def get_authorization_url(
        self,
        redirect_uri: str,
        state: str,
        scopes: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """Build authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": self.config.get("response_type", "code"),
            "state": state,
            "scope": " ".join(scopes or self.config.get("scopes", [])),
            **self.config.get("additional_params", {}),
            **kwargs
        }
        
        return f"{self.config['authorization_endpoint']}?{urlencode(params)}"
    
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
        }
        
        if code_verifier and self.config.get("pkce_required"):
            data["code_verifier"] = code_verifier
        
        # Determine authentication method
        auth = None
        if self.config.get("token_auth_method") == "client_secret_basic":
            auth = (self.client_id, self.client_secret)
        else:
            data["client_secret"] = self.client_secret
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config["token_endpoint"],
                data=data,
                auth=auth,
                headers=self.config.get("custom_headers", {})
            )
            response.raise_for_status()
            return response.json()
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.config["userinfo_endpoint"],
                headers={
                    "Authorization": f"Bearer {access_token}",
                    **self.config.get("custom_headers", {})
                }
            )
            response.raise_for_status()
            
            user_data = response.json()
            
            # Map fields if configured
            if "user_field_mappings" in self.config:
                mapped_data = {}
                for our_field, their_field in self.config["user_field_mappings"].items():
                    if their_field in user_data:
                        mapped_data[our_field] = user_data[their_field]
                return mapped_data
            
            return user_data
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config["token_endpoint"],
                data=data,
                headers=self.config.get("custom_headers", {})
            )
            response.raise_for_status()
            return response.json()
```

---

## Provider Configuration

### Database Schema

```sql
-- OAuth provider configuration table
CREATE TABLE oauth_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(50) UNIQUE NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    client_secret_encrypted TEXT NOT NULL,
    authorization_endpoint TEXT NOT NULL,
    token_endpoint TEXT NOT NULL,
    userinfo_endpoint TEXT,
    jwks_uri TEXT,
    scopes TEXT[],
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Provider user mappings
CREATE TABLE oauth_provider_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider_name VARCHAR(50),
    provider_user_id VARCHAR(255) NOT NULL,
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP,
    provider_data JSONB DEFAULT '{}',
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    UNIQUE(provider_name, provider_user_id)
);
```

### Admin API for Provider Management

```python
# backend/api/admin/oauth_providers.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List

router = APIRouter(prefix="/admin/oauth-providers")

@router.get("/", response_model=List[OAuthProviderResponse])
async def list_providers(
    current_user: User = Depends(require_admin)
):
    """List all configured OAuth providers"""
    providers = await db.fetch_all(
        "SELECT * FROM oauth_providers ORDER BY provider_name"
    )
    return providers

@router.post("/", response_model=OAuthProviderResponse)
async def create_provider(
    provider: OAuthProviderCreate,
    current_user: User = Depends(require_admin)
):
    """Add new OAuth provider"""
    # Encrypt client secret
    encrypted_secret = encrypt_value(provider.client_secret)
    
    result = await db.fetch_one(
        """
        INSERT INTO oauth_providers 
        (provider_name, client_id, client_secret_encrypted, 
         authorization_endpoint, token_endpoint, userinfo_endpoint,
         scopes, config)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        provider.provider_name,
        provider.client_id,
        encrypted_secret,
        provider.authorization_endpoint,
        provider.token_endpoint,
        provider.userinfo_endpoint,
        provider.scopes,
        provider.config
    )
    
    return result

@router.put("/{provider_name}")
async def update_provider(
    provider_name: str,
    updates: OAuthProviderUpdate,
    current_user: User = Depends(require_admin)
):
    """Update OAuth provider configuration"""
    # Build update query dynamically
    update_fields = []
    values = []
    
    if updates.client_id:
        update_fields.append("client_id = $1")
        values.append(updates.client_id)
    
    if updates.client_secret:
        update_fields.append("client_secret_encrypted = $2")
        values.append(encrypt_value(updates.client_secret))
    
    # ... other fields
    
    await db.execute(
        f"""
        UPDATE oauth_providers 
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE provider_name = ${len(values) + 1}
        """,
        *values,
        provider_name
    )
    
    return {"status": "updated"}

@router.post("/{provider_name}/test")
async def test_provider(
    provider_name: str,
    current_user: User = Depends(require_admin)
):
    """Test OAuth provider configuration"""
    provider = await get_provider_config(provider_name)
    
    # Test authorization endpoint
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                provider["authorization_endpoint"],
                params={"client_id": provider["client_id"]},
                follow_redirects=False
            )
            auth_test = response.status_code in [200, 302, 400]
        except:
            auth_test = False
    
    # Test JWKS endpoint if configured
    jwks_test = None
    if provider.get("jwks_uri"):
        try:
            response = await client.get(provider["jwks_uri"])
            jwks_test = response.status_code == 200
        except:
            jwks_test = False
    
    return {
        "provider": provider_name,
        "authorization_endpoint": auth_test,
        "jwks_endpoint": jwks_test,
        "status": "healthy" if auth_test else "unhealthy"
    }
```

---

## Webhook Configuration

### Provider Webhook Handlers

```python
# backend/api/webhooks/oauth_providers.py
from fastapi import APIRouter, Request, HTTPException
import hmac
import hashlib

router = APIRouter(prefix="/webhooks/oauth")

@router.post("/google/revoke")
async def handle_google_revocation(request: Request):
    """Handle Google token revocation webhook"""
    body = await request.body()
    
    # Verify webhook signature if configured
    if not verify_google_webhook(request.headers, body):
        raise HTTPException(400, "Invalid signature")
    
    data = await request.json()
    
    # Revoke tokens for affected user
    await revoke_provider_tokens("google", data["sub"])
    
    return {"status": "acknowledged"}

@router.post("/instagram/deauthorize")
async def handle_instagram_deauthorization(request: Request):
    """Handle Instagram app deauthorization"""
    # Instagram sends signed request
    signed_request = (await request.form())["signed_request"]
    
    # Verify and decode
    data = verify_instagram_signed_request(signed_request)
    
    # Remove user's Instagram connection
    await unlink_provider_account("instagram", data["user_id"])
    
    return {"status": "acknowledged"}

@router.post("/microsoft/notifications")
async def handle_microsoft_notification(request: Request):
    """Handle Microsoft Graph change notifications"""
    # Validate token from Microsoft
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        # Initial subscription validation
        return Response(content=validation_token, media_type="text/plain")
    
    # Process notification
    data = await request.json()
    for notification in data.get("value", []):
        if notification["changeType"] == "updated":
            # User profile updated
            await sync_user_profile("microsoft", notification["resource"])
    
    return {"status": "processed"}

def verify_google_webhook(headers: dict, body: bytes) -> bool:
    """Verify Google webhook signature"""
    signature = headers.get("X-Google-Signature")
    if not signature:
        return False
    
    expected = hmac.new(
        GOOGLE_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)

def verify_instagram_signed_request(signed_request: str) -> dict:
    """Verify and decode Instagram signed request"""
    signature, payload = signed_request.split(".")
    
    # Decode payload
    decoded_payload = base64.urlsafe_b64decode(
        payload + "=" * (4 - len(payload) % 4)
    )
    data = json.loads(decoded_payload)
    
    # Verify signature
    expected = hmac.new(
        INSTAGRAM_APP_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid signature")
    
    return data
```

---

## Testing Providers

### Test Suite for Providers

```python
# tests/test_oauth_providers.py
import pytest
from unittest.mock import patch, Mock

@pytest.mark.asyncio
async def test_google_oauth_flow():
    """Test complete Google OAuth flow"""
    provider = GoogleOAuthProvider()
    
    # Test authorization URL generation
    auth_url = provider.get_authorization_url(
        redirect_uri="http://localhost:3000/callback",
        state="test-state"
    )
    
    assert "accounts.google.com" in auth_url
    assert "client_id=" in auth_url
    assert "scope=openid" in auth_url
    
    # Mock token exchange
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600
        }
        
        tokens = await provider.exchange_code(
            code="test-code",
            redirect_uri="http://localhost:3000/callback"
        )
        
        assert tokens["access_token"] == "test-access-token"

@pytest.mark.asyncio
async def test_provider_error_handling():
    """Test provider error scenarios"""
    provider = GenericOAuthProvider(GENERIC_OAUTH)
    
    # Test invalid code
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.status_code = 400
        mock_post.return_value.json.return_value = {
            "error": "invalid_grant"
        }
        
        with pytest.raises(HTTPException):
            await provider.exchange_code("invalid-code", "http://localhost")

@pytest.mark.asyncio
async def test_token_refresh():
    """Test token refresh for various providers"""
    providers = [
        GoogleOAuthProvider(),
        MicrosoftOAuthProvider(),
        GenericOAuthProvider(CUSTOM_CONFIG)
    ]
    
    for provider in providers:
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "access_token": "new-access-token",
                "expires_in": 3600
            }
            
            new_tokens = await provider.refresh_token("refresh-token")
            assert new_tokens["access_token"] == "new-access-token"
```

### Manual Testing Checklist

```markdown
## Provider Testing Checklist

### Google OAuth
- [ ] Authorization flow initiates correctly
- [ ] Consent screen shows correct scopes
- [ ] Code exchange works
- [ ] User info retrieval works
- [ ] Refresh token works
- [ ] Revocation webhook works
- [ ] Error handling for invalid credentials

### Instagram OAuth
- [ ] Authorization flow works
- [ ] Short-lived token exchange works
- [ ] Long-lived token exchange works
- [ ] User media access works
- [ ] Deauthorization callback works
- [ ] Data deletion request works
- [ ] Rate limiting handled

### Microsoft OAuth
- [ ] Authorization flow works
- [ ] Multi-tenant scenarios work
- [ ] Personal accounts work
- [ ] Azure AD accounts work
- [ ] Group membership retrieval works
- [ ] Profile photo retrieval works
- [ ] Token refresh works

### Generic Provider
- [ ] Configuration accepts all required fields
- [ ] Authorization URL builds correctly
- [ ] Token exchange works
- [ ] Field mapping works
- [ ] Custom headers applied
- [ ] PKCE works if required
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Redirect URI Mismatch

**Error**: `redirect_uri_mismatch`

**Solution**:
```python
# Ensure exact match including protocol, domain, path, and trailing slash
REDIRECT_URIS = [
    "https://api.agencydark.com/oauth/callback/google",  # Correct
    "http://api.agencydark.com/oauth/callback/google",   # Wrong protocol
    "https://api.agencydark.com/oauth/callback/google/", # Wrong trailing slash
]
```

#### 2. Invalid Client Credentials

**Error**: `invalid_client`

**Solution**:
```python
# Check credential encoding
import base64

# For Basic auth
credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
headers = {"Authorization": f"Basic {credentials}"}

# For POST body
data = {
    "client_id": client_id,
    "client_secret": client_secret  # Not base64 encoded
}
```

#### 3. Scope Issues

**Error**: `invalid_scope` or missing permissions

**Solution**:
```python
# Google: Use exact scope strings
GOOGLE_SCOPES = [
    "openid",
    "email", 
    "profile",
    # Not "user.email" or "user.profile"
]

# Microsoft: Include offline_access for refresh tokens
MICROSOFT_SCOPES = [
    "openid",
    "email",
    "profile",
    "offline_access",  # Required for refresh tokens
    "User.Read"
]
```

#### 4. Instagram Token Expiration

**Issue**: Instagram tokens expire quickly

**Solution**:
```python
# Exchange for long-lived token immediately
async def handle_instagram_callback(code: str):
    # Get short-lived token
    short_token = await exchange_code(code)
    
    # Immediately exchange for long-lived token
    long_token = await exchange_for_long_lived_token(short_token)
    
    # Schedule refresh before 60 days
    schedule_token_refresh(long_token, days=55)
```

#### 5. CORS Issues

**Error**: CORS blocked by browser

**Solution**:
```python
# Backend CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.agencydark.com",
        "http://localhost:3000"  # Development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"]
)
```

#### 6. Rate Limiting

**Error**: Provider rate limit exceeded

**Solution**:
```python
# Implement exponential backoff
import asyncio

async def make_provider_request(url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            response = await httpx.get(url)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                await asyncio.sleep(retry_after)
                continue
            return response
        except Exception as e:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

---

## Security Considerations

### 1. Token Storage
```python
# Always encrypt tokens at rest
from cryptography.fernet import Fernet

def encrypt_token(token: str) -> str:
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    cipher = Fernet(ENCRYPTION_KEY)
    return cipher.decrypt(encrypted.encode()).decode()
```

### 2. State Parameter Validation
```python
# Prevent CSRF attacks
def generate_state() -> str:
    return secrets.token_urlsafe(32)

def validate_state(received: str, expected: str) -> bool:
    return secrets.compare_digest(received, expected)
```

### 3. Webhook Security
```python
# Verify webhook signatures
def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)
```

---

## Resources

### Provider Documentation
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Instagram Basic Display API](https://developers.facebook.com/docs/instagram-basic-display-api)
- [Microsoft Identity Platform](https://docs.microsoft.com/en-us/azure/active-directory/develop/)

### OAuth Standards
- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)

### Tools
- [OAuth 2.0 Playground](https://www.oauth.com/playground/)
- [JWT.io](https://jwt.io/) - Token decoder
- [Postman](https://www.postman.com/) - API testing