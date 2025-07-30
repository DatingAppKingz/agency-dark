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
from models.content import Content, ContentType, ContentStatus
from models.subscriber import Subscriber, SubscriptionStatus
from models.model_settings import ModelSettings, ModelSchedule
# APIKey is imported from webhook module

# Export all models
__all__ = [
    # User models
    "User", "UserRole", "Session",
    # Agency models
    "Agency",
    # Model models
    "Model", "ModelStatus", "Platform",
    # Chat models
    "Conversation", "Message", "MessageType", "MessageStatus",
    # Financial models
    "Transaction", "TransactionType", "TransactionStatus", "Payout", "PayoutStatus",
    # Content models
    "Content", "ContentType", "ContentStatus",
    # Subscriber models
    "Subscriber", "SubscriptionStatus",
    # Settings models
    "ModelSettings", "ModelSchedule",
    # API Key models
    "APIKey"
]