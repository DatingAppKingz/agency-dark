"""
SSO API Endpoints
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from core.database import get_db
from core.security import get_current_user
from core.domain.models import User, UserRole
from ..manager import sso_manager
from ..models import SSOProviderType
from ..schemas import (
    SSOProviderCreate,
    SSOProviderUpdate,
    SSOProviderResponse,
    SSOSessionResponse,
    SAMLMetadataResponse
)

router = APIRouter(prefix="/sso", tags=["sso"])


@router.get("/providers", response_model=List[SSOProviderResponse])
async def list_sso_providers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List SSO providers for the agency"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    providers = await sso_manager.get_agency_providers(db, current_user.agency_id)
    return [SSOProviderResponse.from_orm(p) for p in providers]


@router.post("/providers", response_model=SSOProviderResponse)
async def create_sso_provider(
    provider_data: SSOProviderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new SSO provider"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Only agency owners can create SSO providers")
    
    try:
        provider = await sso_manager.create_provider(
            db,
            current_user.agency_id,
            provider_data.dict(exclude_unset=True)
        )
        return SSOProviderResponse.from_orm(provider)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers/{provider_id}", response_model=SSOProviderResponse)
async def get_sso_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get SSO provider details"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if provider.agency_id != current_user.agency_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return SSOProviderResponse.from_orm(provider)


@router.put("/providers/{provider_id}", response_model=SSOProviderResponse)
async def update_sso_provider(
    provider_id: UUID,
    update_data: SSOProviderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update SSO provider configuration"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Only agency owners can update SSO providers")
    
    # Verify provider exists and belongs to agency
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if provider.agency_id != current_user.agency_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        provider = await sso_manager.update_provider(
            db,
            provider_id,
            update_data.dict(exclude_unset=True)
        )
        return SSOProviderResponse.from_orm(provider)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/providers/{provider_id}")
async def delete_sso_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete (deactivate) SSO provider"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]:
        raise HTTPException(status_code=403, detail="Only agency owners can delete SSO providers")
    
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if provider.agency_id != current_user.agency_id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    provider.is_active = False
    provider.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Provider deactivated successfully"}


# SAML Endpoints

@router.get("/saml/login/{provider_id}")
async def saml_login(
    provider_id: UUID,
    return_to: Optional[str] = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Initiate SAML login"""
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider or provider.provider_type != SSOProviderType.SAML:
        raise HTTPException(status_code=404, detail="SAML provider not found")
    
    handler = sso_manager.get_auth_handler(provider)
    
    # Build request data for SAML
    request_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.headers.get('host'),
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': {},
        'return_to': return_to
    }
    
    auth_url = handler.init_auth_request(request_data)
    return RedirectResponse(url=auth_url)


@router.post("/saml/acs")
async def saml_acs(
    request: Request,
    SAMLResponse: str = Body(...),
    RelayState: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """SAML Assertion Consumer Service"""
    # Parse relay state to get provider ID
    if not RelayState:
        raise HTTPException(status_code=400, detail="RelayState missing")
    
    try:
        relay_data = json.loads(RelayState)
        provider_id = UUID(relay_data.get('provider_id'))
    except:
        raise HTTPException(status_code=400, detail="Invalid RelayState")
    
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider or provider.provider_type != SSOProviderType.SAML:
        raise HTTPException(status_code=404, detail="SAML provider not found")
    
    handler = sso_manager.get_auth_handler(provider)
    
    # Build request data
    request_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.headers.get('host'),
        'script_name': request.url.path,
        'get_data': {},
        'post_data': {'SAMLResponse': SAMLResponse}
    }
    
    # Process SAML response
    success, user_data, error = handler.process_response(request_data, SAMLResponse)
    
    if not success:
        raise HTTPException(status_code=400, detail=f"SAML authentication failed: {error}")
    
    # Authenticate user
    try:
        user, access_token = await sso_manager.authenticate_user(
            db,
            provider,
            user_data,
            {
                'ip_address': request.client.host,
                'user_agent': request.headers.get('user-agent')
            }
        )
        
        # Redirect with token
        return_to = relay_data.get('return_to', '/dashboard')
        return RedirectResponse(
            url=f"{return_to}?token={access_token}",
            status_code=302
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/saml/metadata/{provider_id}")
async def saml_metadata(
    provider_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get SAML SP metadata"""
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider or provider.provider_type != SSOProviderType.SAML:
        raise HTTPException(status_code=404, detail="SAML provider not found")
    
    handler = sso_manager.get_auth_handler(provider)
    
    request_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.headers.get('host')
    }
    
    metadata = handler.get_metadata(request_data)
    
    return Response(
        content=metadata,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=sp-metadata-{provider_id}.xml"}
    )


@router.post("/saml/logout")
async def saml_logout(
    request: Request,
    session_id: UUID = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Initiate SAML logout"""
    request_data = {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.headers.get('host'),
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': {}
    }
    
    logout_url = await sso_manager.logout_user(db, session_id, request_data)
    
    if logout_url:
        return {"logout_url": logout_url}
    else:
        return {"message": "Logout successful"}


# OAuth/OIDC Endpoints

@router.get("/oauth/authorize/{provider_id}")
async def oauth_authorize(
    provider_id: UUID,
    return_to: Optional[str] = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Initiate OAuth/OIDC authorization"""
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider or provider.provider_type not in [SSOProviderType.OAUTH2, SSOProviderType.OIDC]:
        raise HTTPException(status_code=404, detail="OAuth provider not found")
    
    handler = sso_manager.get_auth_handler(provider)
    
    # Generate state and nonce
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32) if provider.provider_type == SSOProviderType.OIDC else None
    
    # Store state in session/cache (implementation depends on your session management)
    # For now, we'll encode it in the state parameter
    import json
    import base64
    
    state_data = {
        'provider_id': str(provider_id),
        'return_to': return_to,
        'nonce': nonce,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    encoded_state = base64.urlsafe_b64encode(
        json.dumps(state_data).encode()
    ).decode().rstrip('=')
    
    # Build redirect URI
    redirect_uri = f"{request.url.scheme}://{request.headers.get('host')}/api/v1/sso/oauth/callback"
    
    # Get authorization URL
    auth_url = await handler.get_authorization_url(
        state=encoded_state,
        redirect_uri=redirect_uri,
        nonce=nonce
    )
    
    return RedirectResponse(url=auth_url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """OAuth/OIDC callback"""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error} - {error_description}")
    
    # Decode state
    try:
        import json
        import base64
        
        padded_state = state + '=' * (4 - len(state) % 4)
        state_data = json.loads(base64.urlsafe_b64decode(padded_state))
        provider_id = UUID(state_data['provider_id'])
        nonce = state_data.get('nonce')
        return_to = state_data.get('return_to', '/dashboard')
    except:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    provider = await sso_manager.get_provider(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    handler = sso_manager.get_auth_handler(provider)
    
    # Build redirect URI
    redirect_uri = f"{request.url.scheme}://{request.headers.get('host')}/api/v1/sso/oauth/callback"
    
    try:
        # Exchange code for tokens
        token_response = await handler.exchange_code_for_token(code, redirect_uri)
        
        # Get user info
        user_info = await handler.get_user_info(token_response['access_token'])
        
        # Validate ID token if OIDC
        id_token_claims = None
        if provider.provider_type == SSOProviderType.OIDC and 'id_token' in token_response:
            id_token_claims = await handler.validate_id_token(
                token_response['id_token'],
                nonce
            )
        
        # Prepare auth response
        auth_response = {
            'user_info': user_info,
            'id_token_claims': id_token_claims,
            'access_token': token_response.get('access_token'),
            'refresh_token': token_response.get('refresh_token'),
            'expires_in': token_response.get('expires_in')
        }
        
        # Authenticate user
        user, access_token = await sso_manager.authenticate_user(
            db,
            provider,
            auth_response,
            {
                'ip_address': request.client.host,
                'user_agent': request.headers.get('user-agent')
            }
        )
        
        # Redirect with token
        return RedirectResponse(
            url=f"{return_to}?token={access_token}",
            status_code=302
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Session Management

@router.get("/sessions", response_model=List[SSOSessionResponse])
async def list_user_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's SSO sessions"""
    sessions = await sso_manager.get_user_sessions(db, current_user.id)
    return [SSOSessionResponse.from_orm(s) for s in sessions]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke specific SSO session"""
    # Verify session belongs to user
    sessions = await sso_manager.get_user_sessions(db, current_user.id)
    if not any(s.id == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
    
    await sso_manager.logout_user(db, session_id)
    return {"message": "Session revoked successfully"}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    except_current: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke all user's SSO sessions"""
    # Get current session ID from token if needed
    current_session_id = None  # This would come from the token
    
    count = await sso_manager.revoke_user_sessions(
        db,
        current_user.id,
        except_session_id=current_session_id if except_current else None
    )
    
    return {"message": f"{count} sessions revoked"}