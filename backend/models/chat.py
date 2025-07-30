from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Text, Numeric, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from models.base import Base, BaseModel


class ConversationStatus(str, enum.Enum):
    """Conversation status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"
    PENDING = "pending"


class MessageType(str, enum.Enum):
    """Message type enumeration."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TIP = "tip"
    PPV = "ppv"  # Pay-per-view
    SYSTEM = "system"


class MessageStatus(str, enum.Enum):
    """Message status enumeration."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Conversation(BaseModel):
    """Conversation between a model and a fan."""
    __tablename__ = "conversations"
    
    # Participants
    model_id = Column(Integer, ForeignKey("models.id", ondelete="CASCADE"), nullable=False)
    fan_id = Column(String(255), nullable=False, index=True)  # External fan ID
    fan_username = Column(String(255), nullable=False)
    fan_display_name = Column(String(255), nullable=True)
    
    # Assignment
    assigned_chatter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(String(30), nullable=True)
    
    # Status
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher = more important
    
    # Fan information
    fan_avatar_url = Column(String(500), nullable=True)
    fan_location = Column(String(255), nullable=True)
    fan_timezone = Column(String(50), nullable=True)
    fan_language = Column(String(10), default="en", nullable=False)
    
    # Financial
    total_spent = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_tips = Column(Numeric(12, 2), default=0.00, nullable=False)
    ppv_purchased = Column(Integer, default=0, nullable=False)
    
    # Activity
    last_message_at = Column(String(30), nullable=True)
    last_fan_message_at = Column(String(30), nullable=True)
    unread_count = Column(Integer, default=0, nullable=False)
    
    # Tags and notes
    tags = Column(JSON, default=list, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Metadata
    conversation_metadata = Column("metadata", JSON, default=dict, nullable=False)
    platform_data = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    model = relationship("Model", back_populates="conversations")
    assigned_chatter = relationship("User", back_populates="assigned_conversations", foreign_keys=[assigned_chatter_id])
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    analytics = relationship("ConversationAnalytics", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Conversation {self.id} - Model: {self.model_id}, Fan: {self.fan_username}>"
    
    @property
    def is_active(self):
        """Check if conversation is active."""
        return self.status == ConversationStatus.ACTIVE
    
    @property
    def is_assigned(self):
        """Check if conversation is assigned to a chatter."""
        return self.assigned_chatter_id is not None


class Message(BaseModel):
    """Individual message in a conversation."""
    __tablename__ = "messages"
    
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Sender information
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # NULL = fan
    sender_type = Column(String(20), nullable=False)  # 'model', 'chatter', 'fan', 'system'
    
    # Message content
    type = Column(SQLEnum(MessageType), default=MessageType.TEXT, nullable=False)
    content = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    
    # Status
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.SENT, nullable=False)
    delivered_at = Column(String(30), nullable=True)
    read_at = Column(String(30), nullable=True)
    
    # Financial (for tips and PPV)
    amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=True)
    is_paid = Column(Boolean, default=False, nullable=False)
    
    # Platform information
    platform_message_id = Column(String(255), unique=True, nullable=True)
    platform_data = Column(JSON, default=dict, nullable=False)
    
    # Moderation
    is_flagged = Column(Boolean, default=False, nullable=False)
    flagged_reason = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    
    def __repr__(self):
        return f"<Message {self.id} in Conversation {self.conversation_id}>"
    
    @property
    def is_from_fan(self):
        """Check if message is from fan."""
        return self.sender_type == 'fan'
    
    @property
    def is_tip(self):
        """Check if message is a tip."""
        return self.type == MessageType.TIP
    
    @property
    def is_ppv(self):
        """Check if message is pay-per-view content."""
        return self.type == MessageType.PPV


class ChatTemplate(BaseModel):
    """Pre-written message templates for quick responses."""
    __tablename__ = "chat_templates"
    
    agency_id = Column(Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False)
    
    # Template information
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    
    # Content
    content = Column(Text, nullable=False)
    variables = Column(JSON, default=list, nullable=False)  # List of variable names
    
    # Usage
    usage_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Targeting
    tags = Column(JSON, default=list, nullable=False)
    languages = Column(JSON, default=["en"], nullable=False)
    
    # Relationships
    agency = relationship("Agency", back_populates="chat_templates")
    
    def __repr__(self):
        return f"<ChatTemplate {self.name}>"
    
    def render(self, **kwargs):
        """Render template with variables."""
        content = self.content
        for var in self.variables:
            if var in kwargs:
                content = content.replace(f"{{{var}}}", str(kwargs[var]))
        return content