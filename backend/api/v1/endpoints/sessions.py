"""Session management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from core.dependencies import get_db, get_current_user
from core.domain.models import User
from core.application.session_service import SessionService
from core.exceptions import NotFoundError

router = APIRouter()


# Session response schemas
from pydantic import BaseModel
from typing import Dict, Any


class SessionResponse(BaseModel):
    """Session response schema."""
    id: int
    user_id: int
    ip_address: Optional[str]
    user_agent: Optional[str]
    device_type: Optional[str]
    device_name: Optional[str]
    location: Optional[str]
    last_activity_at: datetime
    expires_at: datetime
    created_at: datetime
    is_current: bool = False
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Session list response."""
    sessions: List[SessionResponse]
    total: int
    active: int


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    include_expired: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> SessionListResponse:
    """
    List all sessions for the current user.
    
    Shows all active sessions with device info and last activity.
    """
    sessions = await SessionService.list_user_sessions(
        db=db,
        user_id=current_user.id,
        include_expired=include_expired
    )
    
    # Get current session token from auth header
    current_token = None
    if authorization and authorization.startswith("Bearer "):
        current_token = authorization.split(" ")[1]
    
    # Build response
    session_responses = []
    active_count = 0
    
    for session in sessions:
        is_current = session.token == current_token if current_token else False
        
        if session.expires_at > datetime.utcnow():
            active_count += 1
        
        session_responses.append(
            SessionResponse(
                id=session.id,
                user_id=session.user_id,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                device_type=session.device_type,
                device_name=session.device_name,
                location=session.location,
                last_activity_at=session.last_activity_at,
                expires_at=session.expires_at,
                created_at=session.created_at,
                is_current=is_current
            )
        )
    
    return SessionListResponse(
        sessions=session_responses,
        total=len(sessions),
        active=active_count
    )


@router.get("/current", response_model=SessionResponse)
async def get_current_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> SessionResponse:
    """
    Get details of the current session.
    
    Returns information about the session being used for this request.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No session token provided")
    
    session_token = authorization.split(" ")[1]
    
    session = await SessionService.get_current_session(
        db=db,
        session_token=session_token
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        device_type=session.device_type,
        device_name=session.device_name,
        location=session.location,
        last_activity_at=session.last_activity_at,
        expires_at=session.expires_at,
        created_at=session.created_at,
        is_current=True
    )


@router.post("/revoke-all")
async def revoke_all_sessions(
    except_current: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> dict:
    """
    Revoke all sessions for the current user.
    
    By default, keeps the current session active.
    Set except_current=false to revoke all sessions including current.
    """
    current_token = None
    if except_current and authorization and authorization.startswith("Bearer "):
        current_token = authorization.split(" ")[1]
    
    revoked_count = await SessionService.revoke_all_sessions(
        db=db,
        user_id=current_user.id,
        except_current=current_token
    )
    
    return {
        "message": f"Successfully revoked {revoked_count} session(s)",
        "revoked_count": revoked_count,
        "kept_current": except_current and current_token is not None
    }


@router.delete("/{session_id}")
async def revoke_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Revoke a specific session.
    
    Immediately invalidates the session and removes it from the system.
    """
    try:
        await SessionService.revoke_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id
        )
        
        return {"message": "Session revoked successfully"}
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/cleanup")
async def cleanup_expired_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Clean up expired sessions.
    
    Admin only: Removes all expired sessions from the system.
    """
    # Check if user is admin
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cleaned_count = await SessionService.cleanup_expired_sessions(db)
    
    return {
        "message": f"Cleaned up {cleaned_count} expired session(s)",
        "cleaned_count": cleaned_count
    }