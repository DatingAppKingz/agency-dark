"""
Session Management Service

Comprehensive session management with device tracking, concurrent session limits,
and activity monitoring.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func
from user_agents import parse
import geoip2.database
import hashlib

from core.domain.models import Session, User
from core.config import settings
from core.redis import redis_client

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage user sessions with advanced features."""
    
    def __init__(self):
        self.max_sessions_per_user = 5  # Configurable
        self.session_timeout_minutes = 30  # Inactivity timeout
        self.cache_prefix = "session:"
        # In production, use a real GeoIP database
        self.geoip_reader = None  # geoip2.database.Reader('/path/to/GeoLite2-City.mmdb')
    
    async def create_session(
        self,
        user_id: str,
        refresh_token: str,
        user_agent: str,
        ip_address: str,
        fingerprint: str,
        db: AsyncSession
    ) -> Session:
        """Create a new session with device identification."""
        # Parse user agent for device info
        ua = parse(user_agent)
        device_name = self._get_device_name(ua)
        
        # Check concurrent session limit
        await self._enforce_session_limit(user_id, db)
        
        # Get location from IP (if GeoIP is available)
        location = self._get_location_from_ip(ip_address) if self.geoip_reader else None
        
        # Create session
        session = Session(
            user_id=user_id,
            refresh_token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
            fingerprint=fingerprint,
            device_name=device_name,
            location=location,
            is_active=True,
            last_activity=datetime.utcnow()
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        # Cache session info
        await self._cache_session(session)
        
        logger.info(f"Session created for user {user_id} on {device_name}")
        return session
    
    async def get_user_sessions(
        self,
        user_id: str,
        db: AsyncSession,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all sessions for a user with detailed information."""
        query = select(Session).where(Session.user_id == user_id)
        
        if not include_inactive:
            query = query.where(
                Session.is_active == True,
                Session.expires_at > datetime.utcnow()
            )
        
        query = query.order_by(Session.last_activity.desc())
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        session_list = []
        for session in sessions:
            ua = parse(session.user_agent)
            session_info = {
                "id": str(session.id),
                "device_name": session.device_name or self._get_device_name(ua),
                "browser": f"{ua.browser.family} {ua.browser.version_string}",
                "os": f"{ua.os.family} {ua.os.version_string}",
                "ip_address": session.ip_address,
                "location": session.location,
                "last_activity": session.last_activity.isoformat() if session.last_activity else None,
                "created_at": session.created_at.isoformat(),
                "is_active": session.is_active,
                "is_current": False  # Will be set by the caller if needed
            }
            session_list.append(session_info)
        
        return session_list
    
    async def update_session_activity(
        self,
        session_id: str,
        db: AsyncSession
    ) -> bool:
        """Update last activity timestamp for a session."""
        try:
            result = await db.execute(
                update(Session)
                .where(
                    Session.id == session_id,
                    Session.is_active == True
                )
                .values(last_activity=datetime.utcnow())
            )
            await db.commit()
            
            if result.rowcount > 0:
                # Update cache
                cache_key = f"{self.cache_prefix}{session_id}"
                await redis_client.expire(cache_key, self.session_timeout_minutes * 60)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update session activity: {e}")
            return False
    
    async def revoke_session(
        self,
        session_id: str,
        user_id: str,
        db: AsyncSession,
        reason: str = "Manual revocation"
    ) -> bool:
        """Revoke a specific session."""
        try:
            result = await db.execute(
                update(Session)
                .where(
                    Session.id == session_id,
                    Session.user_id == user_id
                )
                .values(
                    is_active=False,
                    revoked_at=datetime.utcnow(),
                    revocation_reason=reason
                )
            )
            await db.commit()
            
            if result.rowcount > 0:
                # Clear cache
                cache_key = f"{self.cache_prefix}{session_id}"
                await redis_client.delete(cache_key)
                
                logger.info(f"Session {session_id} revoked for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to revoke session: {e}")
            return False
    
    async def revoke_all_sessions(
        self,
        user_id: str,
        db: AsyncSession,
        except_current: Optional[str] = None,
        reason: str = "Logout all devices"
    ) -> int:
        """Revoke all sessions for a user, optionally keeping current."""
        try:
            query = update(Session).where(
                Session.user_id == user_id,
                Session.is_active == True
            )
            
            if except_current:
                query = query.where(Session.id != except_current)
            
            result = await db.execute(
                query.values(
                    is_active=False,
                    revoked_at=datetime.utcnow(),
                    revocation_reason=reason
                )
            )
            await db.commit()
            
            # Clear all cached sessions for user
            pattern = f"{self.cache_prefix}*"
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.delete(key)
            
            logger.info(f"Revoked {result.rowcount} sessions for user {user_id}")
            return result.rowcount
            
        except Exception as e:
            logger.error(f"Failed to revoke all sessions: {e}")
            return 0
    
    async def cleanup_expired_sessions(
        self,
        db: AsyncSession
    ) -> int:
        """Clean up expired sessions."""
        try:
            # Mark expired sessions as inactive
            result = await db.execute(
                update(Session)
                .where(
                    Session.expires_at < datetime.utcnow(),
                    Session.is_active == True
                )
                .values(is_active=False)
            )
            
            # Delete very old sessions (> 90 days)
            delete_result = await db.execute(
                delete(Session)
                .where(
                    Session.created_at < datetime.utcnow() - timedelta(days=90)
                )
            )
            
            await db.commit()
            
            total_cleaned = result.rowcount + delete_result.rowcount
            logger.info(f"Cleaned up {total_cleaned} sessions")
            return total_cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
            return 0
    
    async def get_session_stats(
        self,
        user_id: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Get session statistics."""
        try:
            base_query = select(Session).where(Session.is_active == True)
            
            if user_id:
                base_query = base_query.where(Session.user_id == user_id)
            
            # Total active sessions
            total_result = await db.execute(
                select(func.count()).select_from(base_query.subquery())
            )
            total_active = total_result.scalar()
            
            # Sessions by device type
            device_stats = {}
            sessions_result = await db.execute(base_query)
            sessions = sessions_result.scalars().all()
            
            for session in sessions:
                ua = parse(session.user_agent)
                device_type = self._get_device_type(ua)
                device_stats[device_type] = device_stats.get(device_type, 0) + 1
            
            # Recent activity
            recent_result = await db.execute(
                select(func.count()).select_from(
                    base_query.where(
                        Session.last_activity > datetime.utcnow() - timedelta(minutes=30)
                    ).subquery()
                )
            )
            recent_active = recent_result.scalar()
            
            return {
                "total_active_sessions": total_active,
                "recently_active": recent_active,
                "device_breakdown": device_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {
                "total_active_sessions": 0,
                "recently_active": 0,
                "device_breakdown": {},
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _enforce_session_limit(
        self,
        user_id: str,
        db: AsyncSession
    ):
        """Enforce maximum concurrent sessions per user."""
        # Count active sessions
        result = await db.execute(
            select(func.count()).select_from(Session).where(
                Session.user_id == user_id,
                Session.is_active == True,
                Session.expires_at > datetime.utcnow()
            )
        )
        session_count = result.scalar()
        
        if session_count >= self.max_sessions_per_user:
            # Revoke oldest session
            oldest_result = await db.execute(
                select(Session).where(
                    Session.user_id == user_id,
                    Session.is_active == True
                ).order_by(Session.created_at.asc()).limit(1)
            )
            oldest_session = oldest_result.scalar_one_or_none()
            
            if oldest_session:
                await self.revoke_session(
                    str(oldest_session.id),
                    user_id,
                    db,
                    reason="Session limit exceeded"
                )
    
    async def _cache_session(self, session: Session):
        """Cache session information."""
        cache_key = f"{self.cache_prefix}{session.id}"
        session_data = {
            "user_id": str(session.user_id),
            "fingerprint": session.fingerprint,
            "last_activity": session.last_activity.isoformat() if session.last_activity else None
        }
        
        await redis_client.setex(
            cache_key,
            self.session_timeout_minutes * 60,
            json.dumps(session_data)
        )
    
    def _get_device_name(self, ua) -> str:
        """Generate a user-friendly device name."""
        device_parts = []
        
        if ua.is_mobile:
            device_parts.append("Mobile")
        elif ua.is_tablet:
            device_parts.append("Tablet")
        else:
            device_parts.append("Desktop")
        
        if ua.browser.family != "Other":
            device_parts.append(ua.browser.family)
        
        if ua.os.family != "Other":
            device_parts.append(f"on {ua.os.family}")
        
        return " ".join(device_parts)
    
    def _get_device_type(self, ua) -> str:
        """Get device type category."""
        if ua.is_mobile:
            return "mobile"
        elif ua.is_tablet:
            return "tablet"
        else:
            return "desktop"
    
    def _get_location_from_ip(self, ip_address: str) -> Optional[str]:
        """Get location from IP address using GeoIP."""
        if not self.geoip_reader:
            return None
        
        try:
            response = self.geoip_reader.city(ip_address)
            location_parts = []
            
            if response.city.name:
                location_parts.append(response.city.name)
            if response.subdivisions.most_specific.name:
                location_parts.append(response.subdivisions.most_specific.name)
            if response.country.name:
                location_parts.append(response.country.name)
            
            return ", ".join(location_parts) if location_parts else None
            
        except Exception:
            return None


# Global instance
session_manager = SessionManager()


# Add additional columns to Session model
Session.location = Column(String(255))
Session.revoked_at = Column(DateTime)
Session.revocation_reason = Column(String(255))