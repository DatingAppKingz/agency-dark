"""
Model Registry - Single source of truth for all model imports.
This ensures models are loaded in the correct order to avoid circular dependencies.
"""

# Import Base first
from core.database import Base
from models.base import BaseModel

# Import enums and basic types first
from models.user import UserRole
from models.model import ModelStatus, Platform
from models.subscriber import SubscriptionTier, SubscriptionStatus
from models.chat import ConversationStatus, MessageType, MessageStatus
from models.financial import TransactionType, TransactionStatus, PayoutStatus, PaymentMethod
from models.content import ContentType, ContentStatus, ContentCategory
from models.webhook import WebhookEvent, WebhookStatus
from models.api_key import APIKeyProvider, APIKeyStatus
from models.notification import NotificationType, NotificationStatus, NotificationPriority

# Import core models in dependency order
# 1. Models with no foreign key dependencies
from models.agency import Agency
from models.translation import Translation

# 2. User model (depends on Agency)
from models.user import User, Session

# 3. Models that depend on User and/or Agency
from models.model import Model
from models.audit_log import AuditLog
from models.scheduled_task import ScheduledTask
from models.task_result import TaskResult
from models.saved_search import SavedSearch

# 4. Models that depend on Model
from models.model_settings import ModelSettings, ModelSchedule
from models.subscriber import Subscriber
from models.external_api import ExternalAPICredential

# 5. Chat/Message models
from models.chat import Conversation, Message, ChatTemplate

# 6. Financial models
from models.financial import Transaction, Earning, Payout, Invoice

# 7. Content models
from models.content import Content, ContentTemplate, ContentAnalytics, Vault, VaultItem

# 8. Analytics models
from models.analytics import ModelAnalytics, ConversationAnalytics, ChatterPerformance, AgencyMetrics

# 9. API Key and Webhook models
from models.api_key import APIKey
from models.api_key_audit import APIKeyAudit
from models.webhook import Webhook, WebhookDelivery

# 10. Notification models (depends on User, Agency)
from models.notification import (
    Notification, NotificationTemplate, NotificationEvent, 
    NotificationPreference
)

# 11. Media models
from models.media import Media, MediaFolder, MediaShare

# 12. Mobile models
from models.mobile_device import MobileDevice
from models.mobile_session import MobileSession

# 13. Sync and logging models
from models.sync_log import SyncLog
from models.sync_conflict_log import SyncConflictLog
from models.sync_error_log import SyncErrorLog

# 14. Other models
from models.fan_claim import FanClaim
from models.temp_file import TempFile

# Export all models
__all__ = [
    # Base
    "Base", "BaseModel",
    
    # Enums
    "UserRole", "ModelStatus", "Platform", "SubscriptionTier", "SubscriptionStatus",
    "ConversationStatus", "MessageType", "MessageStatus", "TransactionType", 
    "TransactionStatus", "PayoutStatus", "PaymentMethod", "ContentType", 
    "ContentStatus", "ContentCategory", "WebhookEvent", "WebhookStatus",
    "APIKeyProvider", "APIKeyStatus", "NotificationType", "NotificationStatus", 
    "NotificationPriority",
    
    # Core models
    "Agency", "User", "Session", "Model", "Subscriber",
    
    # Settings and configuration
    "ModelSettings", "ModelSchedule", "ExternalAPICredential",
    
    # Chat
    "Conversation", "Message", "ChatTemplate",
    
    # Financial
    "Transaction", "Earning", "Payout", "Invoice",
    
    # Content
    "Content", "ContentTemplate", "ContentAnalytics", "Vault", "VaultItem",
    
    # Analytics
    "ModelAnalytics", "ConversationAnalytics", "ChatterPerformance", "AgencyMetrics",
    
    # API and webhooks
    "APIKey", "APIKeyAudit", "Webhook", "WebhookDelivery",
    
    # Notifications
    "Notification", "NotificationTemplate", "NotificationEvent", 
    "NotificationPreference",
    
    # Media
    "Media", "MediaFolder", "MediaShare",
    
    # Mobile
    "MobileDevice", "MobileSession",
    
    # Sync and logging
    "SyncLog", "SyncConflictLog", "SyncErrorLog", "AuditLog",
    
    # Other
    "FanClaim", "TempFile", "Translation", "ScheduledTask", "TaskResult", "SavedSearch",
]


def init_models():
    """Initialize all models in the correct order."""
    # This function ensures all models are imported when called
    # Useful for database migrations and initialization
    return __all__