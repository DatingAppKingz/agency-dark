"""
OAuth2 endpoints for authorization, token management, and introspection.
Implements RFC 6749 OAuth 2.0 Authorization Framework with multi-tenant support.
"""
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
import secrets
import logging
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Form, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import base64

from oauth.models import (
    OAuthClient,
    OAuthToken,
    OAuthAuthorizationCode,
    OAuthConsentRecord
)
from oauth.grants import (
    AgencyAuthorizationCodeGrant,
    AgencyPasswordGrant,
    AgencyClientCredentialsGrant,
    ConsentGrant
)
from oauth.provider import oauth_provider
from oauth.config import oauth_config
from oauth.compatibility import get_current_user, CurrentUser
from models.user import User
from core.database import get_db
from core.security_v2.authentication.password_handler import PasswordHandler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["OAuth2"])


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(..., description="OAuth response type (code, token)"),
    client_id: str = Query(..., description="OAuth client ID"),
    redirect_uri: Optional[str] = Query(None, description="Redirect URI"),
    scope: Optional[str] = Query("", description="Requested scopes"),
    state: Optional[str] = Query(None, description="Client state parameter"),
    code_challenge: Optional[str] = Query(None, description="PKCE code challenge"),
    code_challenge_method: Optional[str] = Query("S256", description="PKCE method"),
    prompt: Optional[str] = Query(None, description="Prompt parameter (none, login, consent)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user(required_scopes=[]))
):
    """
    OAuth2 Authorization Endpoint.
    Handles authorization requests and displays consent screen.
    """
    try:
        # Store database in request state for grants
        request.state.db = db
        
        # Check if user is authenticated
        if not current_user:
            # Store authorization request in session and redirect to login
            auth_request = {
                "response_type": response_type,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method
            }
            # In production, store this in session/Redis
            # For now, redirect to login with return URL
            login_url = f"/auth/login?return_to=/oauth/authorize&{request.url.query}"
            return RedirectResponse(url=login_url, status_code=302)
        
        # Get OAuth client
        result = await db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_client", "error_description": "Client not found"}
            )
        
        # Validate redirect URI
        if redirect_uri and not client.check_redirect_uri(redirect_uri):
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_request", "error_description": "Invalid redirect_uri"}
            )
        
        redirect_uri = redirect_uri or (client.redirect_uris[0] if client.redirect_uris else None)
        
        # Validate response type
        if not client.check_response_type(response_type):
            return JSONResponse(
                status_code=400,
                content={"error": "unsupported_response_type", "error_description": f"Response type '{response_type}' not supported"}
            )
        
        # Check PKCE requirement
        if oauth_config.REQUIRE_PKCE and response_type == "code" and not code_challenge:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_request", "error_description": "PKCE required: missing code_challenge"}
            )
        
        # Check for existing consent
        consent_grant = ConsentGrant(db)
        
        # Handle different prompt values
        if prompt == "none":
            # Check for existing consent - if none, return error
            result = await db.execute(
                select(OAuthConsentRecord).where(
                    and_(
                        OAuthConsentRecord.user_id == current_user.id,
                        OAuthConsentRecord.client_id == client.client_id,
                        OAuthConsentRecord.revoked_at.is_(None)
                    )
                )
            )
            consent = result.scalar_one_or_none()
            
            if not consent or not consent.is_valid:
                # No valid consent, cannot proceed with prompt=none
                error_params = {"error": "consent_required"}
                if state:
                    error_params["state"] = state
                return _build_error_redirect(redirect_uri, error_params)
        
        elif prompt == "login":
            # Force re-authentication
            # Clear current session and redirect to login
            login_url = f"/auth/login?return_to=/oauth/authorize&{request.url.query}"
            return RedirectResponse(url=login_url, status_code=302)
        
        elif prompt == "consent" or oauth_config.REQUIRE_CONSENT:
            # Show consent screen
            return await _show_consent_screen(
                client=client,
                user=current_user,
                scope=scope or "",
                state=state,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method
            )
        
        # Generate authorization code
        code = secrets.token_urlsafe(32)
        
        # Save authorization code
        auth_code = OAuthAuthorizationCode(
            code=code,
            client_id=client.client_id,
            redirect_uri=redirect_uri,
            scope=scope or "",
            user_id=current_user.id,
            agency_id=client.agency_id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=oauth_config.AUTHORIZATION_CODE_LIFETIME
            )
        )
        
        db.add(auth_code)
        await db.commit()
        
        # Build redirect with authorization code
        params = {"code": code}
        if state:
            params["state"] = state
        
        return _build_success_redirect(redirect_uri, params)
        
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "server_error", "error_description": "Internal server error"}
        )


@router.post("/authorize")
async def authorize_consent(
    request: Request,
    client_id: str = Form(...),
    scope: str = Form(...),
    redirect_uri: str = Form(...),
    state: Optional[str] = Form(None),
    code_challenge: Optional[str] = Form(None),
    code_challenge_method: Optional[str] = Form("S256"),
    consent: str = Form(...),
    remember: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(CurrentUser)
):
    """
    Process consent form submission.
    """
    try:
        # Check consent decision
        if consent != "allow":
            # User denied consent
            error_params = {"error": "access_denied", "error_description": "User denied consent"}
            if state:
                error_params["state"] = state
            return _build_error_redirect(redirect_uri, error_params)
        
        # Save consent if remember is checked
        if remember or oauth_config.REQUIRE_CONSENT:
            consent_grant = ConsentGrant(db)
            await consent_grant.save_user_consent(
                user_id=current_user.id,
                client_id=client_id,
                scope=scope,
                remember=remember
            )
        
        # Generate authorization code
        code = secrets.token_urlsafe(32)
        
        # Get client
        result = await db.execute(
            select(OAuthClient).where(OAuthClient.client_id == client_id)
        )
        client = result.scalar_one_or_none()
        
        if not client:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_client"}
            )
        
        # Save authorization code
        auth_code = OAuthAuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            user_id=current_user.id,
            agency_id=client.agency_id,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=oauth_config.AUTHORIZATION_CODE_LIFETIME
            )
        )
        
        db.add(auth_code)
        await db.commit()
        
        # Redirect with code
        params = {"code": code}
        if state:
            params["state"] = state
        
        return _build_success_redirect(redirect_uri, params)
        
    except Exception as e:
        logger.error(f"Consent processing error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "server_error"}
        )


@router.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    scope: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 Token Endpoint.
    Handles token requests for various grant types.
    """
    try:
        request.state.db = db
        
        # Handle different grant types
        if grant_type == "authorization_code":
            return await _handle_authorization_code_grant(
                request, code, redirect_uri, client_id, client_secret,
                code_verifier, db
            )
        
        elif grant_type == "refresh_token":
            return await _handle_refresh_token_grant(
                request, refresh_token, client_id, client_secret, scope, db
            )
        
        elif grant_type == "password":
            # Legacy support during migration
            return await _handle_password_grant(
                request, username, password, client_id, client_secret, scope, db
            )
        
        elif grant_type == "client_credentials":
            return await _handle_client_credentials_grant(
                request, client_id, client_secret, scope, db
            )
        
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "unsupported_grant_type"}
            )
            
    except Exception as e:
        logger.error(f"Token endpoint error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "server_error"}
        )


@router.post("/introspect")
async def introspect(
    token: str = Form(..., description="Token to introspect"),
    token_type_hint: Optional[str] = Form(None, description="Token type hint"),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 Token Introspection Endpoint.
    Returns metadata about a token.
    """
    try:
        # Authenticate client
        result = await db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client or not client.check_client_secret(client_secret):
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_client"}
            )
        
        # Find token
        result = await db.execute(
            select(OAuthToken).where(
                OAuthToken.access_token == token
            )
        )
        token_obj = result.scalar_one_or_none()
        
        if not token_obj:
            # Try as refresh token
            result = await db.execute(
                select(OAuthToken).where(
                    OAuthToken.refresh_token == token
                )
            )
            token_obj = result.scalar_one_or_none()
        
        if not token_obj:
            return {"active": False}
        
        # Check if token belongs to requesting client's agency
        if oauth_config.AGENCY_ISOLATION_STRICT:
            if token_obj.agency_id != client.agency_id:
                return {"active": False}
        
        # Return token metadata
        response = {
            "active": not token_obj.is_expired,
            "scope": token_obj.scope,
            "client_id": token_obj.client_id,
            "token_type": token_obj.token_type
        }
        
        if token_obj.user_id:
            response["sub"] = str(token_obj.user_id)
        
        if token_obj.expires_at:
            response["exp"] = int(token_obj.expires_at.timestamp())
        
        response["iat"] = int(token_obj.created_at.timestamp())
        response["aud"] = str(token_obj.agency_id)
        
        return response
        
    except Exception as e:
        logger.error(f"Introspection error: {e}")
        return {"active": False}


@router.post("/revoke")
async def revoke(
    token: str = Form(..., description="Token to revoke"),
    token_type_hint: Optional[str] = Form(None, description="Token type hint"),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 Token Revocation Endpoint.
    Revokes an access or refresh token.
    """
    try:
        # Authenticate client
        result = await db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client or not client.check_client_secret(client_secret):
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_client"}
            )
        
        # Find and revoke token
        success = await oauth_provider.revoke_token(
            token=token,
            token_type_hint=token_type_hint,
            client=client,
            db=db
        )
        
        # Always return 200 OK per RFC 7009
        return Response(status_code=200)
        
    except Exception as e:
        logger.error(f"Revocation error: {e}")
        # Still return 200 to not leak information
        return Response(status_code=200)


@router.get("/userinfo")
async def userinfo(
    current_user: User = Depends(get_current_user(required_scopes=["profile"]))
):
    """
    OpenID Connect UserInfo Endpoint.
    Returns claims about the authenticated user.
    """
    try:
        userinfo = {
            "sub": str(current_user.id),
            "email": current_user.email,
            "email_verified": getattr(current_user, "email_verified", False)
        }
        
        # Add additional claims based on scopes
        if hasattr(current_user, "name"):
            userinfo["name"] = current_user.name
        
        if hasattr(current_user, "picture"):
            userinfo["picture"] = current_user.picture
        
        if hasattr(current_user, "agency_id"):
            userinfo["agency_id"] = str(current_user.agency_id)
        
        if hasattr(current_user, "role"):
            userinfo["role"] = current_user.role
        
        return userinfo
        
    except Exception as e:
        logger.error(f"UserInfo error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Helper functions

async def _handle_authorization_code_grant(
    request: Request,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: Optional[str],
    code_verifier: Optional[str],
    db: AsyncSession
) -> JSONResponse:
    """Handle authorization code grant type."""
    
    # Get client
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_client"}
        )
    
    # Verify client secret for confidential clients
    if client.client_secret and not client.check_client_secret(client_secret):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_client"}
        )
    
    # Get authorization code
    result = await db.execute(
        select(OAuthAuthorizationCode).where(
            and_(
                OAuthAuthorizationCode.code == code,
                OAuthAuthorizationCode.client_id == client_id
            )
        )
    )
    auth_code = result.scalar_one_or_none()
    
    if not auth_code or auth_code.is_expired:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": "Invalid or expired authorization code"}
        )
    
    # Verify redirect URI
    if auth_code.redirect_uri != redirect_uri:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant", "error_description": "Redirect URI mismatch"}
        )
    
    # Verify PKCE if present
    if auth_code.code_challenge:
        if not code_verifier:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_request", "error_description": "Missing code_verifier"}
            )
        
        # Verify challenge
        if auth_code.code_challenge_method == "plain":
            if auth_code.code_challenge != code_verifier:
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_grant", "error_description": "Invalid code_verifier"}
                )
        else:  # S256
            import hashlib
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip("=")
            
            if auth_code.code_challenge != challenge:
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_grant", "error_description": "Invalid code_verifier"}
                )
    
    # Generate tokens
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    
    # Create token record
    token = OAuthToken(
        agency_id=auth_code.agency_id,
        user_id=auth_code.user_id,
        client_id=client.client_id,
        token_type="Bearer",
        access_token=access_token,
        refresh_token=refresh_token,
        scope=auth_code.scope,
        expires_at=datetime.now(timezone.utc) + timedelta(
            seconds=oauth_config.ACCESS_TOKEN_LIFETIME
        )
    )
    
    db.add(token)
    
    # Delete used authorization code
    await db.delete(auth_code)
    await db.commit()
    
    return JSONResponse(content=token.to_dict())


async def _handle_refresh_token_grant(
    request: Request,
    refresh_token: str,
    client_id: str,
    client_secret: Optional[str],
    scope: Optional[str],
    db: AsyncSession
) -> JSONResponse:
    """Handle refresh token grant type."""
    
    # Get client
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_client"}
        )
    
    # Verify client secret
    if client.client_secret and not client.check_client_secret(client_secret):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_client"}
        )
    
    # Get refresh token
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.refresh_token == refresh_token
        )
    )
    old_token = result.scalar_one_or_none()
    
    if not old_token or not old_token.is_refresh_token_active:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant"}
        )
    
    # Verify client match
    if old_token.client_id != client_id:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_grant"}
        )
    
    # Generate new tokens
    new_access_token = secrets.token_urlsafe(32)
    new_refresh_token = secrets.token_urlsafe(32)
    
    # Create new token record
    new_token = OAuthToken(
        agency_id=old_token.agency_id,
        user_id=old_token.user_id,
        client_id=client.client_id,
        token_type="Bearer",
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        scope=scope or old_token.scope,
        expires_at=datetime.now(timezone.utc) + timedelta(
            seconds=oauth_config.ACCESS_TOKEN_LIFETIME
        )
    )
    
    # Revoke old token
    old_token.revoke()
    
    db.add(new_token)
    await db.commit()
    
    return JSONResponse(content=new_token.to_dict())


async def _handle_password_grant(
    request: Request,
    username: str,
    password: str,
    client_id: str,
    client_secret: str,
    scope: Optional[str],
    db: AsyncSession
) -> JSONResponse:
    """Handle password grant type (legacy support)."""
    
    password_grant = AgencyPasswordGrant(request, None)
    password_grant.db = db
    
    return await password_grant.create_token_response()


async def _handle_client_credentials_grant(
    request: Request,
    client_id: str,
    client_secret: str,
    scope: Optional[str],
    db: AsyncSession
) -> JSONResponse:
    """Handle client credentials grant type."""
    
    client_grant = AgencyClientCredentialsGrant(request, None)
    client_grant.db = db
    
    return await client_grant.create_token_response()


async def _show_consent_screen(
    client: OAuthClient,
    user: User,
    scope: str,
    state: Optional[str],
    redirect_uri: str,
    code_challenge: Optional[str],
    code_challenge_method: Optional[str]
) -> HTMLResponse:
    """Display OAuth consent screen."""
    
    scopes = scope.split() if scope else []
    scope_descriptions = [
        {
            "name": s,
            "description": oauth_config.get_scope_description(s)
        }
        for s in scopes
    ]
    
    # Simple HTML consent form (in production, use proper templates)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Authorization Request</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .scope {{ margin: 10px 0; padding: 10px; background: #f5f5f5; }}
            button {{ margin: 10px 5px; padding: 10px 20px; }}
        </style>
    </head>
    <body>
        <h1>Authorization Request</h1>
        <p><strong>{client.client_name or client.client_id}</strong> is requesting access to your account.</p>
        
        <h3>Requested Permissions:</h3>
        {''.join([f'<div class="scope">• {s["description"]}</div>' for s in scope_descriptions])}
        
        <form method="post" action="/oauth/authorize">
            <input type="hidden" name="client_id" value="{client.client_id}">
            <input type="hidden" name="scope" value="{scope}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="state" value="{state or ''}">
            <input type="hidden" name="code_challenge" value="{code_challenge or ''}">
            <input type="hidden" name="code_challenge_method" value="{code_challenge_method or ''}">
            
            <label>
                <input type="checkbox" name="remember" value="true">
                Remember this decision
            </label>
            
            <div>
                <button type="submit" name="consent" value="allow">Allow</button>
                <button type="submit" name="consent" value="deny">Deny</button>
            </div>
        </form>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


def _build_success_redirect(redirect_uri: str, params: Dict[str, str]) -> RedirectResponse:
    """Build successful redirect with parameters."""
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
    
    parsed = urlparse(redirect_uri)
    query_params = parse_qs(parsed.query)
    query_params.update(params)
    
    new_query = urlencode(query_params, doseq=True)
    final_url = urlunparse(parsed._replace(query=new_query))
    
    return RedirectResponse(url=final_url, status_code=302)


def _build_error_redirect(redirect_uri: str, params: Dict[str, str]) -> RedirectResponse:
    """Build error redirect with parameters."""
    return _build_success_redirect(redirect_uri, params)