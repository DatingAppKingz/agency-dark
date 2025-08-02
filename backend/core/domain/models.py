"""
Domain models compatibility layer.
Maps the existing models to the expected domain model structure.
"""

# Re-export all models from their actual locations
from models.user import User, UserRole, Session
from models.agency import Agency
from models.model import Model, ModelStatus, Platform
from models.chat import Conversation, Message, MessageType, MessageStatus
from models.financial import Transaction, TransactionType, TransactionStatus, Payout, PayoutStatus
from models.content import Content, ContentType, ContentStatus, ContentCategory
from models.subscriber import Subscriber, SubscriptionStatus
from models.model_settings import ModelSettings, ModelSchedule
from models.audit import AuditLog
from models.api_key import APIKey
from models.notification import Notification, NotificationType, NotificationStatus, NotificationPriority
from models.fan_claim import FanClaim

# ModelProfile is actually Model
ModelProfile = Model

# Fan is actually Subscriber
Fan = Subscriber

# Subscription is part of Subscriber
Subscription = Subscriber

# Export all models
__all__ = [
    # User models
    "User", "UserRole", "Session",
    # Agency models
    "Agency",
    # Model models
    "Model", "ModelStatus", "Platform", "ModelProfile",
    # Chat models
    "Conversation", "Message", "MessageType", "MessageStatus",
    # Financial models
    "Transaction", "TransactionType", "TransactionStatus", "Payout", "PayoutStatus",
    # Content models
    "Content", "ContentType", "ContentStatus", "ContentCategory",
    # Subscriber models
    "Subscriber", "SubscriptionStatus", "Fan", "FanClaim", "Subscription",
    # Settings models
    "ModelSettings", "ModelSchedule",
    # Audit models
    "AuditLog",
    # API Key models
    "APIKey",
    # Notification models
    "Notification", "NotificationType", "NotificationStatus", "NotificationPriority"
]