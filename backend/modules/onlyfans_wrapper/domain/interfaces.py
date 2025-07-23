"""
OnlyFans API domain interfaces.

These interfaces define the contract for interacting with OnlyFansAPI.com.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, BinaryIO
from datetime import datetime
from decimal import Decimal

from .schemas import (
    OnlyFansProfile,
    OnlyFansFan,
    OnlyFansPost,
    OnlyFansMessage,
    OnlyFansTransaction,
    OnlyFansStatistics,
    OnlyFansMedia,
    OnlyFansVault,
    OnlyFansList,
    OnlyFansNotification
)


class IOnlyFansClient(ABC):
    """Interface for OnlyFans API client."""
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with OnlyFans API."""
        pass
    
    @abstractmethod
    async def get_profile(self, username: Optional[str] = None) -> OnlyFansProfile:
        """Get profile information."""
        pass
    
    @abstractmethod
    async def update_profile(
        self,
        name: Optional[str] = None,
        about: Optional[str] = None,
        subscription_price: Optional[Decimal] = None
    ) -> OnlyFansProfile:
        """Update profile information."""
        pass
    
    @abstractmethod
    async def get_fans(
        self,
        limit: int = 100,
        offset: int = 0,
        filter_type: Optional[str] = None  # active, expired, all
    ) -> List[OnlyFansFan]:
        """Get list of fans/subscribers."""
        pass
    
    @abstractmethod
    async def get_fan(self, fan_id: str) -> OnlyFansFan:
        """Get specific fan details."""
        pass
    
    @abstractmethod
    async def restrict_fan(self, fan_id: str) -> bool:
        """Restrict a fan from viewing content."""
        pass
    
    @abstractmethod
    async def unrestrict_fan(self, fan_id: str) -> bool:
        """Remove restriction from a fan."""
        pass
    
    @abstractmethod
    async def get_posts(
        self,
        limit: int = 100,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[OnlyFansPost]:
        """Get posts from timeline."""
        pass
    
    @abstractmethod
    async def create_post(
        self,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None,
        is_paid: bool = False
    ) -> OnlyFansPost:
        """Create a new post."""
        pass
    
    @abstractmethod
    async def delete_post(self, post_id: str) -> bool:
        """Delete a post."""
        pass
    
    @abstractmethod
    async def get_messages(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansMessage]:
        """Get messages/chats."""
        pass
    
    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None,
        is_paid: bool = False
    ) -> OnlyFansMessage:
        """Send a message to a user."""
        pass
    
    @abstractmethod
    async def send_mass_message(
        self,
        user_ids: List[str],
        text: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Send mass message to multiple users."""
        pass
    
    @abstractmethod
    async def get_transactions(
        self,
        type_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansTransaction]:
        """Get financial transactions."""
        pass
    
    @abstractmethod
    async def get_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> OnlyFansStatistics:
        """Get account statistics."""
        pass
    
    @abstractmethod
    async def upload_media(
        self,
        file: BinaryIO,
        media_type: str,  # photo, video, audio
        filename: Optional[str] = None
    ) -> OnlyFansMedia:
        """Upload media file."""
        pass
    
    @abstractmethod
    async def get_vault(
        self,
        limit: int = 100,
        offset: int = 0,
        media_type: Optional[str] = None
    ) -> List[OnlyFansVault]:
        """Get vault items."""
        pass
    
    @abstractmethod
    async def create_list(self, name: str) -> OnlyFansList:
        """Create a custom list."""
        pass
    
    @abstractmethod
    async def add_to_list(self, list_id: str, user_ids: List[str]) -> bool:
        """Add users to a custom list."""
        pass
    
    @abstractmethod
    async def get_notifications(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansNotification]:
        """Get notifications."""
        pass
    
    @abstractmethod
    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark notification as read."""
        pass


class IOnlyFansRepository(ABC):
    """Interface for storing OnlyFans-related data locally."""
    
    @abstractmethod
    async def store_profile(self, profile: OnlyFansProfile) -> None:
        """Store or update profile information."""
        pass
    
    @abstractmethod
    async def get_profile(self, profile_id: str) -> Optional[OnlyFansProfile]:
        """Retrieve stored profile information."""
        pass
    
    @abstractmethod
    async def store_fan(self, fan: OnlyFansFan) -> None:
        """Store or update fan information."""
        pass
    
    @abstractmethod
    async def get_fan(self, fan_id: str) -> Optional[OnlyFansFan]:
        """Retrieve stored fan information."""
        pass
    
    @abstractmethod
    async def store_post(self, post: OnlyFansPost) -> None:
        """Store or update post."""
        pass
    
    @abstractmethod
    async def get_posts(
        self,
        profile_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[OnlyFansPost]:
        """Retrieve stored posts."""
        pass
    
    @abstractmethod
    async def store_message(self, message: OnlyFansMessage) -> None:
        """Store or update message."""
        pass
    
    @abstractmethod
    async def get_messages(
        self,
        profile_id: str,
        user_id: Optional[str] = None
    ) -> List[OnlyFansMessage]:
        """Retrieve stored messages."""
        pass
    
    @abstractmethod
    async def store_statistics(
        self,
        profile_id: str,
        statistics: OnlyFansStatistics
    ) -> None:
        """Store statistics data."""
        pass
    
    @abstractmethod
    async def get_latest_statistics(
        self,
        profile_id: str
    ) -> Optional[OnlyFansStatistics]:
        """Get the most recent statistics."""
        pass