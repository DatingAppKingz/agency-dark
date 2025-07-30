"""Session management service."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from datetime import datetime, timedelta
import secrets
import json

from models.user import Session
from core.redis import redis_manager
from core.exceptions import NotFoundError, ValidationError


class SessionService:
    """Service for managing user sessions."""
    
    SESSION_TTL = 86400 * 7  # 7 days in seconds
    
    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: int,
        ip_address: str,
        user_agent: str,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Session:
        """Create a new session."""
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        
        # Create session in database
        session = Session(
            user_id=user_id,
            token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_info.get('type') if device_info else None,
            device_name=device_info.get('name') if device_info else None,
            location=device_info.get('location') if device_info else None,
            last_activity_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        # Store session in Redis for fast lookup
        session_data = {
            "id": session.id,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat()
        }
        
        await redis_manager.set(
            f"session:{session_token}",
            json.dumps(session_data),
            expire=SessionService.SESSION_TTL
        )
        
        return session
    
    @staticmethod
    async def list_user_sessions(
        db: AsyncSession,
        user_id: int,
        include_expired: bool = False
    ) -> List[Session]:
        """List all sessions for a user."""
        stmt = select(Session).where(Session.user_id == user_id)
        
        if not include_expired:
            stmt = stmt.where(
                Session.expires_at > datetime.utcnow()
            )
        
        stmt = stmt.order_by(Session.last_activity_at.desc())
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    @staticmethod
    async def get_current_session(
        db: AsyncSession,
        session_token: str
    ) -> Optional[Session]:
        """Get current session details."""
        # First check Redis
        cached = await redis_manager.get(f"session:{session_token}")
        
        if cached:
            session_data = json.loads(cached)
            # Get full session from database
            stmt = select(Session).where(
                Session.id == session_data["id"]
            )
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()
            
            if session and session.expires_at > datetime.utcnow():
                # Update last activity
                session.last_activity_at = datetime.utcnow()
                await db.commit()
                return session
        
        # Fallback to database lookup
        stmt = select(Session).where(
            and_(
                Session.token == session_token,
                Session.expires_at > datetime.utcnow()
            )
        )
        
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            # Update last activity
            session.last_activity_at = datetime.utcnow()
            await db.commit()
            
            # Update Redis cache
            session_data = {
                "id": session.id,
                "user_id": session.user_id,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "created_at": session.created_at.isoformat(),
                "last_activity_at": session.last_activity_at.isoformat()
            }
            
            await redis_manager.set(
                f"session:{session_token}",
                json.dumps(session_data),
                expire=SessionService.SESSION_TTL
            )
        
        return session
    
    @staticmethod
    async def revoke_session(
        db: AsyncSession,
        session_id: int,
        user_id: int
    ) -> bool:
        """Revoke a specific session."""
        stmt = select(Session).where(
            and_(
                Session.id == session_id,
                Session.user_id == user_id
            )
        )
        
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            raise NotFoundError("Session not found")
        
        # Remove from Redis
        await redis_manager.delete(f"session:{session.token}")
        
        # Delete from database
        await db.delete(session)
        await db.commit()
        
        return True
    
    @staticmethod
    async def revoke_all_sessions(
        db: AsyncSession,
        user_id: int,
        except_current: Optional[str] = None
    ) -> int:
        """Revoke all sessions for a user."""
        # Get all sessions
        stmt = select(Session).where(Session.user_id == user_id)
        
        if except_current:
            stmt = stmt.where(Session.token != except_current)
        
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        
        # Remove from Redis
        for session in sessions:
            await redis_manager.delete(f"session:{session.token}")
        
        # Delete from database
        stmt = delete(Session).where(Session.user_id == user_id)
        
        if except_current:
            stmt = stmt.where(Session.token != except_current)
        
        result = await db.execute(stmt)
        await db.commit()
        
        return result.rowcount
    
    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """Clean up expired sessions."""
        # Get expired sessions
        stmt = select(Session).where(
            Session.expires_at < datetime.utcnow()
        )
        
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        
        # Remove from Redis
        for session in sessions:
            await redis_manager.delete(f"session:{session.token}")
        
        # Delete from database
        stmt = delete(Session).where(
            Session.expires_at < datetime.utcnow()
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        return result.rowcount
    
    @staticmethod
    async def update_session_activity(
        db: AsyncSession,
        session_token: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Update session last activity."""
        session = await SessionService.get_current_session(db, session_token)
        
        if not session:
            return False
        
        session.last_activity_at = datetime.utcnow()
        
        if ip_address and ip_address != session.ip_address:
            # Log IP change for security
            session.ip_address = ip_address
        
        await db.commit()
        
        # Update Redis
        session_data = {
            "id": session.id,
            "user_id": session.user_id,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat()
        }
        
        await redis_manager.set(
            f"session:{session_token}",
            json.dumps(session_data),
            expire=SessionService.SESSION_TTL
        )
        
        return True