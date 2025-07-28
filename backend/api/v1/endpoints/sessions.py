"""
Session Management API Endpoints

Provides endpoints for users to manage their active sessions.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import CurrentUser
from core.auth.session_manager import session_manager
from core.domain.schemas import (
    SessionInfo,
    SessionListResponse,
    SessionRevokeRequest,
    SessionStats
)

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
async def get_user_sessions(
    request: Request,
    current_user: CurrentUser,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get all sessions for the current user."""
    sessions = await session_manager.get_user_sessions(
        str(current_user.id),
        db,
        include_inactive=include_inactive
    )
    
    # Mark current session
    current_session_id = getattr(request.state, "session_id", None)
    for session in sessions:
        if session["id"] == current_session_id:
            session["is_current"] = True
    
    return SessionListResponse(
        sessions=sessions,
        total=len(sessions),
        max_allowed=session_manager.max_sessions_per_user
    )


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Revoke a specific session."""
    success = await session_manager.revoke_session(
        session_id,
        str(current_user.id),
        db,
        reason="User requested"
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already revoked"
        )
    
    return {"message": "Session revoked successfully"}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    request: Request,
    current_user: CurrentUser,
    keep_current: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Revoke all sessions except optionally the current one."""
    current_session_id = None
    if keep_current:
        current_session_id = getattr(request.state, "session_id", None)
    
    count = await session_manager.revoke_all_sessions(
        str(current_user.id),
        db,
        except_current=current_session_id,
        reason="User requested logout from all devices"
    )
    
    return {
        "message": f"Revoked {count} session(s)",
        "revoked_count": count
    }


@router.get("/sessions/stats", response_model=SessionStats)
async def get_session_stats(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get session statistics for the current user."""
    stats = await session_manager.get_session_stats(
        str(current_user.id),
        db
    )
    
    return SessionStats(**stats)


@router.post("/sessions/verify")
async def verify_session(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Verify the current session is valid and active."""
    # Get session from request state
    session_id = getattr(request.state, "session_id", None)
    
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session"
        )
    
    # Update activity
    updated = await session_manager.update_session_activity(session_id, db)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )
    
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "session_id": session_id
    }


@router.post("/sessions/{session_id}/rename")
async def rename_session(
    session_id: str,
    new_name: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Rename a session for easier identification."""
    from sqlalchemy import update
    from core.domain.models import Session
    
    # Verify ownership
    result = await db.execute(
        update(Session)
        .where(
            Session.id == session_id,
            Session.user_id == current_user.id
        )
        .values(device_name=new_name[:255])  # Limit length
    )
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {"message": "Session renamed successfully"}