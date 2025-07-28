"""
Inflow API domain interfaces.

These interfaces define the contract for interacting with Inflow API.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from .schemas import (
    InflowUser,
    InflowContent,
    InflowMessage,
    InflowSubscription,
    InflowTransaction,
    InflowAnalytics,
    InflowWebhookEvent
)


class IInflowClient(ABC):
    """Interface for Inflow API client."""
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with Inflow API."""
        pass
    
    @abstractmethod
    async def get_current_user(self) -> InflowUser:
        """Get the authenticated user's information."""
        pass
    
    @abstractmethod
    async def get_user(self, user_id: str) -> InflowUser:
        """Get a specific user by ID."""
        pass
    
    @abstractmethod
    async def list_subscribers(
        self,
        creator_id: str,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True
    ) -> List[InflowSubscription]:
        """List subscribers for a creator."""
        pass
    
    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> InflowSubscription:
        """Get a specific subscription by ID."""
        pass
    
    @abstractmethod
    async def list_content(
        self,
        creator_id: str,
        limit: int = 100,
        offset: int = 0,
        content_type: Optional[str] = None
    ) -> List[InflowContent]:
        """List content for a creator."""
        pass
    
    @abstractmethod
    async def create_content(
        self,
        title: str,
        content_type: str,
        file_path: str,
        description: Optional[str] = None,
        price: Optional[float] = None,
        is_ppv: bool = False
    ) -> InflowContent:
        """Create new content."""
        pass
    
    @abstractmethod
    async def delete_content(self, content_id: str) -> bool:
        """Delete content by ID."""
        pass
    
    @abstractmethod
    async def upload_media(
        self,
        file: Any,  # BinaryIO
        media_type: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload media file for messages or content."""
        pass
    
    @abstractmethod
    async def list_messages(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InflowMessage]:
        """List messages in a conversation or with a specific user."""
        pass
    
    @abstractmethod
    async def send_message(
        self,
        recipient_id: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        price: Optional[float] = None
    ) -> InflowMessage:
        """Send a message to a user."""
        pass
    
    @abstractmethod
    async def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read."""
        pass
    
    @abstractmethod
    async def list_transactions(
        self,
        user_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InflowTransaction]:
        """List financial transactions."""
        pass
    
    @abstractmethod
    async def get_analytics(
        self,
        creator_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> InflowAnalytics:
        """Get analytics for a creator within a date range."""
        pass
    
    @abstractmethod
    async def register_webhook(
        self,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a webhook endpoint."""
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """Verify webhook signature."""
        pass


class IInflowRepository(ABC):
    """Interface for storing Inflow-related data locally."""
    
    @abstractmethod
    async def store_user(self, user: InflowUser) -> None:
        """Store or update user information."""
        pass
    
    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[InflowUser]:
        """Retrieve stored user information."""
        pass
    
    @abstractmethod
    async def store_content(self, content: InflowContent) -> None:
        """Store or update content information."""
        pass
    
    @abstractmethod
    async def get_content(self, content_id: str) -> Optional[InflowContent]:
        """Retrieve stored content information."""
        pass
    
    @abstractmethod
    async def store_message(self, message: InflowMessage) -> None:
        """Store or update message."""
        pass
    
    @abstractmethod
    async def get_messages(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[InflowMessage]:
        """Retrieve stored messages."""
        pass
    
    @abstractmethod
    async def store_analytics(
        self,
        creator_id: str,
        analytics: InflowAnalytics
    ) -> None:
        """Store analytics data."""
        pass
    
    @abstractmethod
    async def get_latest_analytics(
        self,
        creator_id: str
    ) -> Optional[InflowAnalytics]:
        """Get the most recent analytics for a creator."""
        pass