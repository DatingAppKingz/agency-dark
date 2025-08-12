"""
Simple OAuth implementation for localhost testing.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Form, Response
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import secrets
import hashlib
import base64
import json
from datetime import datetime, timedelta
import jwt

from core.database import get_db
from models.user import User
from sqlalchemy import select
import os

router = APIRouter()

# In-memory storage for demo purposes
oauth_clients = {
    "demo_client": {
        "client_id": "demo_client",
        "client_secret": "demo_secret",
        "redirect_uris": ["http://localhost:3000/callback"],
        "allowed_scopes": ["openid", "profile", "email"],
        "name": "Demo Application"
    }
}

# Store authorization codes temporarily
auth_codes = {}
# Store tokens
active_tokens = {}

@router.get("/.well-known/openid-configuration")
async def openid_configuration():
    """OpenID Connect discovery endpoint."""
    base_url = os.environ.get("OAUTH_ISSUER", "http://localhost:8000")
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/api/v1/oauth/authorize",
        "token_endpoint": f"{base_url}/api/v1/oauth/token",
        "userinfo_endpoint": f"{base_url}/api/v1/oauth/userinfo",
        "jwks_uri": f"{base_url}/api/v1/oauth/jwks",
        "response_types_supported": ["code", "token", "id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["HS256"],
        "scopes_supported": ["openid", "profile", "email"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "claims_supported": ["sub", "name", "email", "email_verified", "picture"],
        "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
    }

@router.get("/providers")
async def get_providers():
    """Get available OAuth providers."""
    return {
        "providers": [
            {
                "id": "google",
                "name": "Google",
                "enabled": False,
                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            },
            {
                "id": "internal",
                "name": "Internal OAuth",
                "enabled": True,
                "authorization_url": "/api/v1/oauth/authorize",
            }
        ]
    }

@router.get("/authorize")
async def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "openid profile email",
    state: Optional[str] = None,
    prompt: Optional[str] = None,
):
    """OAuth authorization endpoint."""
    # Validate client
    if client_id not in oauth_clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    client = oauth_clients[client_id]
    if redirect_uri not in client["redirect_uris"]:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    
    # For internal AgencyDark client, show login page or auto-approve if already logged in
    if client_id == "demo_client" or client_id == "agencydark_web":
        # Check if user is already logged in (simplified for demo)
        # In production, this would check the session/cookie
        user_logged_in = False  # For demo, we'll show login page
        
        if user_logged_in:
            # User already logged in, auto-approve
            code = secrets.token_urlsafe(32)
            auth_codes[code] = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "created_at": datetime.utcnow(),
                "user_id": "demo_user",
            }
            
            redirect_url = f"{redirect_uri}?code={code}"
            if state:
                redirect_url += f"&state={state}"
            
            return RedirectResponse(url=redirect_url)
        else:
            # Show login page for internal use
            login_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Agency Dark - Login</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    }}
                    .login-card {{
                        background: white;
                        padding: 2.5rem;
                        border-radius: 12px;
                        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
                        max-width: 400px;
                        width: 100%;
                    }}
                    h1 {{
                        margin: 0 0 0.5rem 0;
                        font-size: 2rem;
                        color: #1a202c;
                        text-align: center;
                    }}
                    .subtitle {{
                        color: #718096;
                        text-align: center;
                        margin-bottom: 2rem;
                    }}
                    .form-group {{
                        margin-bottom: 1.5rem;
                    }}
                    label {{
                        display: block;
                        margin-bottom: 0.5rem;
                        color: #4a5568;
                        font-weight: 500;
                    }}
                    input {{
                        width: 100%;
                        padding: 0.75rem;
                        border: 1px solid #e2e8f0;
                        border-radius: 6px;
                        font-size: 1rem;
                        transition: border-color 0.2s;
                        box-sizing: border-box;
                    }}
                    input:focus {{
                        outline: none;
                        border-color: #667eea;
                        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
                    }}
                    button {{
                        width: 100%;
                        padding: 0.875rem;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-size: 1rem;
                        font-weight: 600;
                        cursor: pointer;
                        transition: transform 0.2s, box-shadow 0.2s;
                    }}
                    button:hover {{
                        transform: translateY(-1px);
                        box-shadow: 0 10px 20px rgba(102, 126, 234, 0.2);
                    }}
                    .demo-note {{
                        margin-top: 1.5rem;
                        padding: 1rem;
                        background: #f7fafc;
                        border-radius: 6px;
                        color: #4a5568;
                        font-size: 0.875rem;
                    }}
                    .demo-note strong {{
                        color: #2d3748;
                    }}
                </style>
            </head>
            <body>
                <div class="login-card">
                    <h1>Agency Dark</h1>
                    <p class="subtitle">Sign in to your account</p>
                    
                    <form method="post" action="/api/v1/oauth/authorize/login">
                        <input type="hidden" name="client_id" value="{client_id}">
                        <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                        <input type="hidden" name="response_type" value="{response_type}">
                        <input type="hidden" name="scope" value="{scope}">
                        <input type="hidden" name="state" value="{state or ''}">
                        
                        <div class="form-group">
                            <label for="email">Email</label>
                            <input type="email" id="email" name="email" value="admin@agency.com" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="password">Password</label>
                            <input type="password" id="password" name="password" value="admin123" required>
                        </div>
                        
                        <button type="submit">Sign In</button>
                        
                        <div class="demo-note">
                            <strong>Demo Mode:</strong> Click Sign In to continue with the pre-filled demo credentials.
                        </div>
                    </form>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=login_html)
    
    # Show consent page only for external clients
    if prompt != "none" and client_id not in ["demo_client", "agencydark_web"]:
        consent_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorize Access</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .consent-card {{
                    background: white;
                    padding: 2rem;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    max-width: 400px;
                    width: 100%;
                }}
                h1 {{
                    margin: 0 0 1rem 0;
                    font-size: 1.5rem;
                    color: #333;
                }}
                .app-name {{
                    font-weight: bold;
                    color: #667eea;
                }}
                .scopes {{
                    background: #f7fafc;
                    padding: 1rem;
                    border-radius: 4px;
                    margin: 1rem 0;
                }}
                .scope-item {{
                    margin: 0.5rem 0;
                    color: #4a5568;
                }}
                .buttons {{
                    display: flex;
                    gap: 1rem;
                    margin-top: 1.5rem;
                }}
                button {{
                    flex: 1;
                    padding: 0.75rem;
                    border: none;
                    border-radius: 4px;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: opacity 0.2s;
                }}
                button:hover {{
                    opacity: 0.9;
                }}
                .approve {{
                    background: #667eea;
                    color: white;
                }}
                .deny {{
                    background: #e2e8f0;
                    color: #4a5568;
                }}
            </style>
        </head>
        <body>
            <div class="consent-card">
                <h1>Authorization Request</h1>
                <p><span class="app-name">{client['name']}</span> wants to access your account</p>
                
                <div class="scopes">
                    <strong>This application will be able to:</strong>
                    <div class="scope-item">✓ View your basic profile information</div>
                    <div class="scope-item">✓ View your email address</div>
                </div>
                
                <form method="post" action="/api/v1/oauth/authorize/consent">
                    <input type="hidden" name="client_id" value="{client_id}">
                    <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                    <input type="hidden" name="response_type" value="{response_type}">
                    <input type="hidden" name="scope" value="{scope}">
                    <input type="hidden" name="state" value="{state or ''}">
                    
                    <div class="buttons">
                        <button type="submit" name="action" value="approve" class="approve">
                            Authorize
                        </button>
                        <button type="submit" name="action" value="deny" class="deny">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=consent_html)
    
    # Auto-approve for prompt=none
    code = secrets.token_urlsafe(32)
    auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "created_at": datetime.utcnow(),
        "user_id": "demo_user",  # In production, get from session
    }
    
    # Build redirect URL
    redirect_url = f"{redirect_uri}?code={code}"
    if state:
        redirect_url += f"&state={state}"
    
    return RedirectResponse(url=redirect_url)

@router.post("/authorize/login")
async def authorize_login(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    response_type: str = Form(...),
    scope: str = Form(...),
    state: Optional[str] = Form(None),
    email: str = Form(...),
    password: str = Form(...),
):
    """Handle login form submission for internal OAuth."""
    # Validate client
    if client_id not in oauth_clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    client = oauth_clients[client_id]
    if redirect_uri not in client["redirect_uris"]:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    
    # Simple demo authentication (in production, verify against database)
    if email == "admin@agency.com" and password == "admin123":
        # Login successful - generate authorization code
        code = secrets.token_urlsafe(32)
        auth_codes[code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "created_at": datetime.utcnow(),
            "user_id": "demo_user",  # In production, get actual user ID
        }
        
        # Build redirect URL with code
        redirect_url = f"{redirect_uri}?code={code}"
        if state:
            redirect_url += f"&state={state}"
        
        # In production, also set a session cookie here
        return RedirectResponse(url=redirect_url)
    else:
        # Login failed - redirect back to login with error
        error_url = f"/api/v1/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type={response_type}&scope={scope}&error=invalid_credentials"
        if state:
            error_url += f"&state={state}"
        return RedirectResponse(url=error_url)

@router.post("/authorize/consent")
async def authorize_consent(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    response_type: str = Form(...),
    scope: str = Form(...),
    state: Optional[str] = Form(None),
    action: str = Form(...),
):
    """Handle consent form submission."""
    # Validate client
    if client_id not in oauth_clients:
        raise HTTPException(status_code=400, detail="Invalid client_id")
    
    client = oauth_clients[client_id]
    if redirect_uri not in client["redirect_uris"]:
        raise HTTPException(status_code=400, detail="Invalid redirect_uri")
    
    if action == "deny":
        # User denied access
        redirect_url = f"{redirect_uri}?error=access_denied&error_description=User denied authorization"
        if state:
            redirect_url += f"&state={state}"
        return RedirectResponse(url=redirect_url)
    
    # User approved - generate authorization code
    code = secrets.token_urlsafe(32)
    auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "created_at": datetime.utcnow(),
        "user_id": "demo_user",  # In production, get from session
    }
    
    # Build redirect URL with code
    redirect_url = f"{redirect_uri}?code={code}"
    if state:
        redirect_url += f"&state={state}"
    
    return RedirectResponse(url=redirect_url)

@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    refresh_token: Optional[str] = Form(None),
):
    """OAuth token endpoint."""
    # Validate client
    if client_id not in oauth_clients:
        raise HTTPException(status_code=400, detail="Invalid client")
    
    client = oauth_clients[client_id]
    if client["client_secret"] != client_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    
    if grant_type == "authorization_code":
        if not code or code not in auth_codes:
            raise HTTPException(status_code=400, detail="Invalid authorization code")
        
        code_data = auth_codes.pop(code)
        if code_data["client_id"] != client_id:
            raise HTTPException(status_code=400, detail="Code not issued to this client")
        
        # Generate tokens
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        token_data = {
            "user_id": code_data["user_id"],
            "client_id": client_id,
            "scope": code_data["scope"],
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        
        active_tokens[access_token] = token_data
        active_tokens[refresh_token] = {**token_data, "is_refresh": True}
        
        # Generate ID token
        id_token_payload = {
            "iss": os.environ.get("OAUTH_ISSUER", "http://localhost:8000"),
            "sub": code_data["user_id"],
            "aud": client_id,
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "email": "demo@example.com",
            "name": "Demo User",
        }
        
        id_token = jwt.encode(
            id_token_payload,
            os.environ.get("JWT_SECRET_KEY", "your-secret-key-here"),
            algorithm="HS256"
        )
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": refresh_token,
            "id_token": id_token,
            "scope": code_data["scope"],
        }
    
    elif grant_type == "refresh_token":
        if not refresh_token or refresh_token not in active_tokens:
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        
        token_data = active_tokens[refresh_token]
        if not token_data.get("is_refresh"):
            raise HTTPException(status_code=400, detail="Not a refresh token")
        
        # Generate new access token
        new_access_token = secrets.token_urlsafe(32)
        active_tokens[new_access_token] = {
            **token_data,
            "is_refresh": False,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        
        return {
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": token_data["scope"],
        }
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported grant type")

@router.get("/userinfo")
async def userinfo(request: Request):
    """OAuth userinfo endpoint."""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = auth_header[7:]
    if token not in active_tokens:
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    token_data = active_tokens[token]
    if token_data["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token expired")
    
    return {
        "sub": token_data["user_id"],
        "name": "Demo User",
        "email": "demo@example.com",
        "email_verified": True,
        "picture": "https://via.placeholder.com/150",
    }

@router.post("/revoke")
async def revoke(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):
    """OAuth token revocation endpoint."""
    # Validate client
    if client_id not in oauth_clients:
        return Response(status_code=200)  # Silent failure per spec
    
    client = oauth_clients[client_id]
    if client["client_secret"] != client_secret:
        return Response(status_code=200)  # Silent failure per spec
    
    # Revoke token
    if token in active_tokens:
        del active_tokens[token]
    
    return Response(status_code=200)

@router.get("/jwks")
async def jwks():
    """JSON Web Key Set endpoint."""
    # For demo, return a simple symmetric key reference
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": "1",
                "use": "sig",
                "alg": "HS256",
            }
        ]
    }

@router.get("/clients")
async def list_clients():
    """List OAuth clients (admin endpoint)."""
    return {
        "clients": [
            {
                "client_id": client_id,
                "name": client_data["name"],
                "redirect_uris": client_data["redirect_uris"],
                "allowed_scopes": client_data["allowed_scopes"],
            }
            for client_id, client_data in oauth_clients.items()
        ]
    }

@router.post("/introspect")
async def introspect(
    token: str = Form(...),
    token_type_hint: Optional[str] = Form(None),
):
    """OAuth token introspection endpoint."""
    if token not in active_tokens:
        return {"active": False}
    
    token_data = active_tokens[token]
    if token_data["expires_at"] < datetime.utcnow():
        return {"active": False}
    
    return {
        "active": True,
        "scope": token_data["scope"],
        "client_id": token_data["client_id"],
        "username": token_data["user_id"],
        "exp": int(token_data["expires_at"].timestamp()),
    }