"""
Session management and token rotation
"""
import secrets
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import jwt
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete, text

from core.database import Base
from core.config import settings
from core.logging import logger
from core.redis import redis_client
from core.security.audit_logging import AuditLogger, AuditEventType


class UserSession(Base):
    """User session tracking"""
    __tablename__ = "user_sessions"
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False)
    
    # Session tokens
    session_token = Column(String, unique=True, nullable=False)
    refresh_token = Column(String, unique=True, nullable=False)
    
    # Device/client info
    device_id = Column(String)
    device_type = Column(String)  # web, mobile, api
    device_name = Column(String)
    user_agent = Column(String)
    ip_address = Column(String)
    
    # Session metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    refresh_expires_at = Column(DateTime, nullable=False)
    
    # Security
    is_active = Column(Boolean, default=True)
    revoked_at = Column(DateTime)
    revoke_reason = Column(String)
    
    # Token rotation tracking
    token_version = Column(Integer, default=1)
    last_rotation = Column(DateTime, default=datetime.utcnow)
    rotation_count = Column(Integer, default=0)
    
    # Additional security context
    security_context = Column(JSON, default={})  # MFA status, risk score, etc.


class SessionManager:
    """Enhanced session management with token rotation"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.access_token_ttl = getattr(settings, 'ACCESS_TOKEN_TTL', 900)  # 15 minutes
        self.refresh_token_ttl = getattr(settings, 'REFRESH_TOKEN_TTL', 2592000)  # 30 days
        self.rotation_interval = getattr(settings, 'TOKEN_ROTATION_INTERVAL', 3600)  # 1 hour
        self.max_sessions_per_user = getattr(settings, 'MAX_SESSIONS_PER_USER', 5)
        self.jwt_secret = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
        self.jwt_algorithm = "HS256"
    
    async def create_session(
        self,
        user_id: str,
        device_info: Optional[Dict[str, str]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        security_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new session with tokens"""
        # Clean up old sessions if limit exceeded
        await self._cleanup_old_sessions(user_id)
        
        # Generate tokens
        session_token = self._generate_session_token()
        access_token = self._generate_access_token(user_id, session_token)
        refresh_token = self._generate_refresh_token()
        
        # Create session record
        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            refresh_token=refresh_token,
            device_id=device_info.get('device_id') if device_info else None,
            device_type=device_info.get('device_type', 'web') if device_info else 'web',
            device_name=device_info.get('device_name') if device_info else None,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.utcnow() + timedelta(seconds=self.access_token_ttl),
            refresh_expires_at=datetime.utcnow() + timedelta(seconds=self.refresh_token_ttl),
            security_context=security_context or {}
        )
        
        self.db.add(session)
        await self.db.commit()
        
        # Cache session data
        await self._cache_session(session)
        
        # Audit log
        audit_logger = AuditLogger(self.db)
        await audit_logger.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_name="Session created",
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                "device_type": session.device_type,
                "session_id": str(session.id)
            }
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.access_token_ttl,
            "session_id": str(session.id)
        }
    
    async def refresh_session(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Refresh session and rotate tokens if needed"""
        # Find session by refresh token
        result = await self.db.execute(
            select(UserSession).where(
                and_(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active == True,
                    UserSession.refresh_expires_at > datetime.utcnow()
                )
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            logger.warning(f"Invalid refresh token attempt from {ip_address}")
            return None
        
        # Update last activity
        session.last_activity = datetime.utcnow()
        
        # Check if token rotation is needed
        should_rotate = (
            datetime.utcnow() - session.last_rotation
        ).total_seconds() > self.rotation_interval
        
        if should_rotate:
            # Generate new tokens
            new_session_token = self._generate_session_token()
            new_refresh_token = self._generate_refresh_token()
            
            # Update session
            session.session_token = new_session_token
            session.refresh_token = new_refresh_token
            session.token_version += 1
            session.last_rotation = datetime.utcnow()
            session.rotation_count += 1
            session.expires_at = datetime.utcnow() + timedelta(seconds=self.access_token_ttl)
            
            # Invalidate old tokens in cache
            await self._invalidate_cached_tokens(str(session.id))
        else:
            # Just extend expiry
            session.expires_at = datetime.utcnow() + timedelta(seconds=self.access_token_ttl)
        
        await self.db.commit()
        
        # Generate new access token
        access_token = self._generate_access_token(
            str(session.user_id),
            session.session_token
        )
        
        # Update cache
        await self._cache_session(session)
        
        return {
            "access_token": access_token,
            "refresh_token": session.refresh_token,
            "token_type": "Bearer",
            "expires_in": self.access_token_ttl,
            "session_id": str(session.id),
            "rotated": should_rotate
        }
    
    async def validate_session(
        self,
        access_token: str,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate access token and return session info"""
        try:
            # Decode JWT
            payload = jwt.decode(
                access_token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            user_id = payload.get("sub")
            session_token = payload.get("session_token")
            
            if not user_id or not session_token:
                return None
            
            # Check cache first
            cached_session = await self._get_cached_session(session_token)
            if cached_session:
                return cached_session
            
            # Query database
            result = await self.db.execute(
                select(UserSession).where(
                    and_(
                        UserSession.session_token == session_token,
                        UserSession.user_id == user_id,
                        UserSession.is_active == True,
                        UserSession.expires_at > datetime.utcnow()
                    )
                )
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return None
            
            # Update last activity
            session.last_activity = datetime.utcnow()
            await self.db.commit()
            
            # Cache session
            await self._cache_session(session)
            
            return {
                "user_id": str(session.user_id),
                "session_id": str(session.id),
                "device_type": session.device_type,
                "security_context": session.security_context
            }
            
        except jwt.ExpiredSignatureError:
            logger.debug("Expired access token")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    async def revoke_session(
        self,
        session_id: str,
        reason: str = "User logout",
        user_id: Optional[str] = None
    ) -> bool:
        """Revoke a specific session"""
        conditions = [UserSession.id == session_id]
        if user_id:
            conditions.append(UserSession.user_id == user_id)
        
        result = await self.db.execute(
            select(UserSession).where(and_(*conditions))
        )
        session = result.scalar_one_or_none()
        
        if session:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            session.revoke_reason = reason
            await self.db.commit()
            
            # Clear cache
            await self._invalidate_cached_tokens(str(session.id))
            
            # Audit log
            audit_logger = AuditLogger(self.db)
            await audit_logger.log_event(
                event_type=AuditEventType.LOGOUT,
                event_name="Session revoked",
                user_id=str(session.user_id),
                metadata={
                    "session_id": str(session.id),
                    "reason": reason
                }
            )
            
            return True
        
        return False
    
    async def revoke_all_sessions(
        self,
        user_id: str,
        except_current: Optional[str] = None,
        reason: str = "Security reset"
    ) -> int:
        """Revoke all sessions for a user"""
        conditions = [
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ]
        
        if except_current:
            conditions.append(UserSession.id != except_current)
        
        # Get sessions to revoke
        result = await self.db.execute(
            select(UserSession).where(and_(*conditions))
        )
        sessions = result.scalars().all()
        
        # Revoke them
        for session in sessions:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            session.revoke_reason = reason
            
            # Clear cache
            await self._invalidate_cached_tokens(str(session.id))
        
        await self.db.commit()
        
        logger.info(f"Revoked {len(sessions)} sessions for user {user_id}")
        return len(sessions)
    
    async def get_active_sessions(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        result = await self.db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.refresh_expires_at > datetime.utcnow()
                )
            ).order_by(UserSession.last_activity.desc())
        )
        sessions = result.scalars().all()
        
        return [
            {
                "session_id": str(session.id),
                "device_type": session.device_type,
                "device_name": session.device_name,
                "ip_address": session.ip_address,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "expires_at": session.expires_at.isoformat()
            }
            for session in sessions
        ]
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        result = await self.db.execute(
            delete(UserSession).where(
                or_(
                    and_(
                        UserSession.is_active == True,
                        UserSession.refresh_expires_at < datetime.utcnow()
                    ),
                    and_(
                        UserSession.is_active == False,
                        UserSession.revoked_at < datetime.utcnow() - timedelta(days=30)
                    )
                )
            )
        )
        
        await self.db.commit()
        
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        
        return count
    
    # Private methods
    def _generate_session_token(self) -> str:
        """Generate unique session token"""
        return secrets.token_urlsafe(32)
    
    def _generate_refresh_token(self) -> str:
        """Generate refresh token"""
        return secrets.token_urlsafe(48)
    
    def _generate_access_token(self, user_id: str, session_token: str) -> str:
        """Generate JWT access token"""
        payload = {
            "sub": user_id,
            "session_token": session_token,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=self.access_token_ttl)
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    async def _cache_session(self, session: UserSession):
        """Cache session data in Redis"""
        cache_key = f"session:{session.session_token}"
        cache_data = {
            "user_id": str(session.user_id),
            "session_id": str(session.id),
            "device_type": session.device_type,
            "security_context": session.security_context,
            "expires_at": session.expires_at.isoformat()
        }
        
        ttl = (session.expires_at - datetime.utcnow()).total_seconds()
        if ttl > 0:
            await redis_client.setex(
                cache_key,
                int(ttl),
                json.dumps(cache_data)
            )
    
    async def _get_cached_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get session from cache"""
        cache_key = f"session:{session_token}"
        cached = await redis_client.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        return None
    
    async def _invalidate_cached_tokens(self, session_id: str):
        """Invalidate cached tokens for a session"""
        # Add to blacklist with TTL
        blacklist_key = f"blacklist:{session_id}"
        await redis_client.setex(
            blacklist_key,
            self.refresh_token_ttl,
            "1"
        )
    
    async def _cleanup_old_sessions(self, user_id: str):
        """Clean up old sessions if limit exceeded"""
        # Count active sessions
        result = await self.db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            ).order_by(UserSession.last_activity.desc())
        )
        sessions = result.scalars().all()
        
        # Revoke oldest sessions if over limit
        if len(sessions) >= self.max_sessions_per_user:
            for session in sessions[self.max_sessions_per_user - 1:]:
                await self.revoke_session(
                    str(session.id),
                    reason="Session limit exceeded"
                )


# Session middleware
class SessionMiddleware:
    """Middleware for session validation"""
    
    def __init__(self):
        pass
    
    async def __call__(self, request, call_next):
        """Validate session for authenticated requests"""
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
            # Get database session
            from core.database import get_db
            async for db in get_db():
                session_manager = SessionManager(db)
                session_info = await session_manager.validate_session(
                    token,
                    request.client.host if request.client else None
                )
                
                if session_info:
                    # Add session info to request state
                    request.state.session_info = session_info
                    request.state.user_id = session_info["user_id"]
                
                break
        
        response = await call_next(request)
        return response