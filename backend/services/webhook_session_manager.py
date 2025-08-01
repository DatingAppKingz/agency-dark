"""Database session manager for webhook processor."""

from typing import AsyncIterator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database import engine
from core.logger import get_logger

logger = get_logger(__name__)


class WebhookSessionManager:
    """Manages database sessions for webhook processor."""
    
    def __init__(self):
        """Initialize session manager."""
        self.session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """
        Get a database session.
        
        This creates a new session for each webhook delivery
        to ensure proper isolation and cleanup.
        """
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def create_session(self) -> AsyncSession:
        """
        Create a new database session.
        
        Used for long-running background tasks.
        """
        return self.session_factory()


# Global instance
_session_manager: Optional[WebhookSessionManager] = None


def get_webhook_session_manager() -> WebhookSessionManager:
    """Get or create webhook session manager."""
    global _session_manager
    
    if not _session_manager:
        _session_manager = WebhookSessionManager()
    
    return _session_manager