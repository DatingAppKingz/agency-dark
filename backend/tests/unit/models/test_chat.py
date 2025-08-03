"""Comprehensive tests for Chat and Conversation models."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from models.conversation import Conversation, ConversationStatus, ConversationPriority
from models.message import Message, MessageType, MessageStatus, MessageDirection
from models.model import Model, Platform
from models.user import User, UserRole
from tests.factories import create_test_model, create_test_agency, create_test_user


class TestConversationModel:
    """Test cases for Conversation model."""
    
    @pytest.mark.asyncio
    async def test_create_conversation_with_valid_data(self, db_session: AsyncSession):
        """Test creating a conversation with all valid data."""
        model = await create_test_model()
        
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="of_conv_123",
            fan_username="superfan123",
            fan_display_name="Super Fan",
            fan_profile_image="https://example.com/fan.jpg",
            status=ConversationStatus.ACTIVE,
            priority=ConversationPriority.NORMAL,
            started_at=datetime.utcnow(),
            metadata={
                "subscription_price": 9.99,
                "total_tips": 150.00,
                "is_vip": True,
                "tags": ["high_spender", "regular"]
            }
        )
        
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        
        assert conversation.id is not None
        assert conversation.fan_username == "superfan123"
        assert conversation.status == ConversationStatus.ACTIVE
        assert conversation.priority == ConversationPriority.NORMAL
        assert conversation.metadata["is_vip"] is True
        assert conversation.unread_count == 0
    
    @pytest.mark.asyncio
    async def test_conversation_uniqueness_constraint(self, db_session: AsyncSession):
        """Test that platform conversation IDs must be unique per platform."""
        model = await create_test_model()
        
        conv1 = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="unique_123",
            fan_username="fan1"
        )
        db_session.add(conv1)
        await db_session.commit()
        
        # Try to create duplicate
        conv2 = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="unique_123",  # Same ID
            fan_username="fan2"
        )
        db_session.add(conv2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
        
        await db_session.rollback()
        
        # Different platform should work
        conv3 = Conversation(
            model_id=model.id,
            platform=Platform.FANSLY,
            platform_conversation_id="unique_123",  # Same ID but different platform
            fan_username="fan3"
        )
        db_session.add(conv3)
        await db_session.commit()  # Should succeed
    
    @pytest.mark.asyncio
    async def test_conversation_status_management(self, db_session: AsyncSession):
        """Test conversation status transitions and management."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="status_test",
            fan_username="testfan",
            status=ConversationStatus.ACTIVE
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Archive conversation
        conversation.archive()
        assert conversation.status == ConversationStatus.ARCHIVED
        assert conversation.archived_at is not None
        
        # Unarchive
        conversation.unarchive()
        assert conversation.status == ConversationStatus.ACTIVE
        assert conversation.archived_at is None
        
        # Mark as spam
        conversation.mark_as_spam(marked_by="moderator123")
        assert conversation.status == ConversationStatus.SPAM
        assert conversation.spam_marked_at is not None
        assert conversation.spam_marked_by == "moderator123"
        
        # Block fan
        conversation.block_fan(blocked_by="model123", reason="Harassment")
        assert conversation.status == ConversationStatus.BLOCKED
        assert conversation.blocked_at is not None
        assert conversation.block_reason == "Harassment"
    
    @pytest.mark.asyncio
    async def test_conversation_priority_system(self, db_session: AsyncSession):
        """Test conversation priority management."""
        model = await create_test_model()
        
        # Create conversations with different priorities
        high_priority = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="high_1",
            fan_username="vip_fan",
            priority=ConversationPriority.HIGH,
            metadata={"total_spent": 5000.00}
        )
        
        normal_priority = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="normal_1",
            fan_username="regular_fan",
            priority=ConversationPriority.NORMAL,
            metadata={"total_spent": 100.00}
        )
        
        low_priority = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="low_1",
            fan_username="new_fan",
            priority=ConversationPriority.LOW,
            metadata={"total_spent": 0.00}
        )
        
        db_session.add_all([high_priority, normal_priority, low_priority])
        await db_session.commit()
        
        # Auto-prioritize based on spending
        await normal_priority.auto_prioritize()
        assert normal_priority.priority == ConversationPriority.NORMAL
        
        # Update metadata and re-prioritize
        normal_priority.metadata["total_spent"] = 1000.00
        await normal_priority.auto_prioritize()
        assert normal_priority.priority == ConversationPriority.HIGH
        
        # Manual priority override
        low_priority.set_priority(
            ConversationPriority.URGENT,
            reason="Time-sensitive request"
        )
        assert low_priority.priority == ConversationPriority.URGENT
        assert low_priority.priority_override_reason == "Time-sensitive request"
    
    @pytest.mark.asyncio
    async def test_conversation_unread_tracking(self, db_session: AsyncSession):
        """Test unread message tracking in conversations."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="unread_test",
            fan_username="chatty_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Add messages
        for i in range(5):
            message = Message(
                conversation_id=conversation.id,
                platform_message_id=f"msg_{i}",
                type=MessageType.TEXT,
                direction=MessageDirection.INCOMING,
                sender_type="fan",
                content=f"Message {i}",
                sent_at=datetime.utcnow() - timedelta(minutes=5-i)
            )
            db_session.add(message)
        
        await db_session.commit()
        
        # Update unread count
        await conversation.update_unread_count(db_session)
        assert conversation.unread_count == 5
        
        # Mark messages as read
        messages = await conversation.get_messages(db_session, limit=3)
        for msg in messages:
            msg.mark_as_read()
        await db_session.commit()
        
        await conversation.update_unread_count(db_session)
        assert conversation.unread_count == 2
        
        # Mark all as read
        await conversation.mark_all_as_read(db_session)
        assert conversation.unread_count == 0
    
    @pytest.mark.asyncio
    async def test_conversation_metadata_tracking(self, db_session: AsyncSession):
        """Test conversation metadata and analytics tracking."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="metadata_test",
            fan_username="analytics_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Track fan spending
        await conversation.track_spending(
            amount=Decimal("50.00"),
            type="tip",
            reference="tip_123"
        )
        assert conversation.metadata["total_spent"] == 50.00
        assert conversation.metadata["last_tip_amount"] == 50.00
        
        await conversation.track_spending(
            amount=Decimal("100.00"),
            type="ppv",
            reference="ppv_456"
        )
        assert conversation.metadata["total_spent"] == 150.00
        assert conversation.metadata["ppv_purchases"] == 1
        
        # Track engagement metrics
        await conversation.update_engagement_metrics(
            messages_sent=10,
            messages_received=15,
            response_time_avg_minutes=5.5
        )
        assert conversation.metadata["total_messages"] == 25
        assert conversation.metadata["response_time_avg"] == 5.5
        
        # Calculate fan value score
        fan_score = conversation.calculate_fan_value_score()
        assert fan_score > 0
        assert fan_score <= 100
    
    @pytest.mark.asyncio
    async def test_conversation_assignment(self, db_session: AsyncSession):
        """Test conversation assignment to chatters."""
        agency = await create_test_agency()
        model = await create_test_model(agency=agency)
        chatter = await create_test_user(role=UserRole.CHATTER, agency_id=agency.id)
        
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="assign_test",
            fan_username="assigned_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Assign to chatter
        await conversation.assign_to_chatter(
            chatter_id=chatter.id,
            assigned_by="manager123",
            notes="VIP fan, handle with care"
        )
        
        assert conversation.assigned_chatter_id == chatter.id
        assert conversation.assigned_at is not None
        assert conversation.assignment_notes == "VIP fan, handle with care"
        
        # Track chatter performance
        await conversation.track_chatter_performance(
            messages_sent=20,
            response_time_minutes=3,
            revenue_generated=Decimal("200.00")
        )
        
        performance = conversation.get_chatter_performance()
        assert performance["messages_sent"] == 20
        assert performance["average_response_time"] == 3
        assert performance["revenue_generated"] == 200.00
        
        # Reassign to different chatter
        chatter2 = await create_test_user(
            role=UserRole.CHATTER,
            agency_id=agency.id,
            username="chatter2"
        )
        
        await conversation.reassign_chatter(
            new_chatter_id=chatter2.id,
            reassigned_by="manager123",
            reason="Shift change"
        )
        
        assert conversation.assigned_chatter_id == chatter2.id
        assert conversation.previous_chatter_id == chatter.id


class TestMessageModel:
    """Test cases for Message model."""
    
    @pytest.mark.asyncio
    async def test_create_message_with_valid_data(self, db_session: AsyncSession):
        """Test creating a message with all valid data."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="msg_test",
            fan_username="message_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        message = Message(
            conversation_id=conversation.id,
            platform_message_id="of_msg_123",
            type=MessageType.TEXT,
            direction=MessageDirection.OUTGOING,
            sender_type="model",
            content="Thanks for your support! 💕",
            status=MessageStatus.SENT,
            sent_at=datetime.utcnow(),
            metadata={
                "char_count": 28,
                "has_emoji": True,
                "language": "en"
            }
        )
        
        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)
        
        assert message.id is not None
        assert message.content == "Thanks for your support! 💕"
        assert message.type == MessageType.TEXT
        assert message.direction == MessageDirection.OUTGOING
        assert message.metadata["has_emoji"] is True
    
    @pytest.mark.asyncio
    async def test_message_type_handling(self, db_session: AsyncSession):
        """Test different message types and their metadata."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="types_test",
            fan_username="media_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Text message
        text_msg = Message(
            conversation_id=conversation.id,
            platform_message_id="text_1",
            type=MessageType.TEXT,
            content="Hello there!",
            direction=MessageDirection.INCOMING
        )
        
        # Image message
        image_msg = Message(
            conversation_id=conversation.id,
            platform_message_id="img_1",
            type=MessageType.IMAGE,
            media_urls=["https://cdn.example.com/image1.jpg"],
            content="Check out this pic!",
            direction=MessageDirection.OUTGOING,
            metadata={
                "width": 1920,
                "height": 1080,
                "size_bytes": 2048000
            }
        )
        
        # Video message
        video_msg = Message(
            conversation_id=conversation.id,
            platform_message_id="vid_1",
            type=MessageType.VIDEO,
            media_urls=["https://cdn.example.com/video1.mp4"],
            direction=MessageDirection.OUTGOING,
            metadata={
                "duration_seconds": 120,
                "resolution": "1080p",
                "size_bytes": 50000000
            }
        )
        
        # Audio message
        audio_msg = Message(
            conversation_id=conversation.id,
            platform_message_id="audio_1",
            type=MessageType.AUDIO,
            media_urls=["https://cdn.example.com/audio1.mp3"],
            direction=MessageDirection.INCOMING,
            metadata={
                "duration_seconds": 30,
                "format": "mp3"
            }
        )
        
        # Tip message
        tip_msg = Message(
            conversation_id=conversation.id,
            platform_message_id="tip_1",
            type=MessageType.TIP,
            content="Thanks for the content!",
            direction=MessageDirection.INCOMING,
            metadata={
                "amount": 25.00,
                "currency": "USD",
                "tip_id": "tip_abc123"
            }
        )
        
        db_session.add_all([text_msg, image_msg, video_msg, audio_msg, tip_msg])
        await db_session.commit()
        
        # Verify type-specific handling
        assert image_msg.has_media() is True
        assert len(image_msg.media_urls) == 1
        assert video_msg.metadata["duration_seconds"] == 120
        assert tip_msg.metadata["amount"] == 25.00
        assert audio_msg.type == MessageType.AUDIO
    
    @pytest.mark.asyncio
    async def test_message_status_tracking(self, db_session: AsyncSession):
        """Test message status updates and delivery tracking."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="status_track",
            fan_username="tracking_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        message = Message(
            conversation_id=conversation.id,
            platform_message_id="track_1",
            type=MessageType.TEXT,
            content="Test message",
            direction=MessageDirection.OUTGOING,
            status=MessageStatus.PENDING
        )
        db_session.add(message)
        await db_session.commit()
        
        # Update status flow
        message.mark_as_sent()
        assert message.status == MessageStatus.SENT
        assert message.sent_at is not None
        
        message.mark_as_delivered()
        assert message.status == MessageStatus.DELIVERED
        assert message.delivered_at is not None
        
        message.mark_as_read()
        assert message.status == MessageStatus.READ
        assert message.read_at is not None
        
        # Failed message
        failed_msg = Message(
            conversation_id=conversation.id,
            platform_message_id="fail_1",
            type=MessageType.TEXT,
            content="Failed message",
            direction=MessageDirection.OUTGOING,
            status=MessageStatus.PENDING
        )
        db_session.add(failed_msg)
        await db_session.commit()
        
        failed_msg.mark_as_failed(error="Network timeout")
        assert failed_msg.status == MessageStatus.FAILED
        assert failed_msg.error_message == "Network timeout"
        assert failed_msg.failed_at is not None
    
    @pytest.mark.asyncio
    async def test_message_pricing_ppv(self, db_session: AsyncSession):
        """Test pay-per-view message pricing and tracking."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="ppv_test",
            fan_username="ppv_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Create PPV message
        ppv_message = Message(
            conversation_id=conversation.id,
            platform_message_id="ppv_1",
            type=MessageType.PAID_MESSAGE,
            content="Unlock to see exclusive content! 🔥",
            media_urls=[
                "https://cdn.example.com/preview.jpg",
                "https://cdn.example.com/locked_content.mp4"
            ],
            direction=MessageDirection.OUTGOING,
            price=Decimal("49.99"),
            currency="USD",
            metadata={
                "content_type": "video",
                "duration": 300,
                "preview_available": True,
                "unlock_count": 0
            }
        )
        db_session.add(ppv_message)
        await db_session.commit()
        
        assert ppv_message.is_paid_content() is True
        assert ppv_message.price == Decimal("49.99")
        
        # Track unlock
        await ppv_message.track_unlock(
            unlocked_by="ppv_fan",
            amount_paid=Decimal("49.99"),
            transaction_id="trans_123"
        )
        
        assert ppv_message.metadata["unlock_count"] == 1
        assert ppv_message.metadata["total_revenue"] == 49.99
        assert "trans_123" in ppv_message.metadata["unlock_transactions"]
        
        # Track multiple unlocks (mass PPV)
        for i in range(5):
            await ppv_message.track_unlock(
                unlocked_by=f"fan_{i}",
                amount_paid=Decimal("49.99"),
                transaction_id=f"trans_{i}"
            )
        
        assert ppv_message.metadata["unlock_count"] == 6
        assert ppv_message.metadata["total_revenue"] == 299.94  # 49.99 * 6
    
    @pytest.mark.asyncio
    async def test_message_templates(self, db_session: AsyncSession):
        """Test message template system."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="template_test",
            fan_username="template_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Create message from template
        template = {
            "name": "welcome_message",
            "content": "Hi {fan_name}! Welcome to my page! 💕",
            "variables": ["fan_name"],
            "media_urls": ["https://cdn.example.com/welcome.jpg"]
        }
        
        message = Message.create_from_template(
            conversation_id=conversation.id,
            template=template,
            variables={"fan_name": "John"},
            sender_type="model"
        )
        
        assert message.content == "Hi John! Welcome to my page! 💕"
        assert len(message.media_urls) == 1
        assert message.metadata["from_template"] == "welcome_message"
        
        db_session.add(message)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_message_moderation(self, db_session: AsyncSession):
        """Test message moderation and filtering."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="mod_test",
            fan_username="mod_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Create potentially problematic message
        message = Message(
            conversation_id=conversation.id,
            platform_message_id="mod_1",
            type=MessageType.TEXT,
            content="Send me your personal number: 555-1234",
            direction=MessageDirection.INCOMING
        )
        
        db_session.add(message)
        await db_session.commit()
        
        # Run moderation check
        moderation_result = await message.moderate_content()
        
        assert moderation_result["requires_review"] is True
        assert "personal_info" in moderation_result["flags"]
        assert moderation_result["confidence"] > 0.8
        
        # Flag message
        message.flag_for_review(
            reason="Contains personal information",
            flagged_by="auto_moderator"
        )
        
        assert message.is_flagged is True
        assert message.flag_reason == "Contains personal information"
        assert message.flagged_at is not None
        
        # Approve after review
        message.approve_after_review(
            reviewed_by="moderator123",
            notes="Number was business related"
        )
        
        assert message.is_flagged is False
        assert message.reviewed_by == "moderator123"
    
    @pytest.mark.asyncio
    async def test_message_analytics(self, db_session: AsyncSession):
        """Test message analytics and reporting."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="analytics_test",
            fan_username="analytics_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Create various messages
        messages_data = [
            (MessageType.TEXT, MessageDirection.INCOMING, None, "Hi there!"),
            (MessageType.TEXT, MessageDirection.OUTGOING, None, "Hello! How are you?"),
            (MessageType.TIP, MessageDirection.INCOMING, Decimal("20.00"), "Thanks!"),
            (MessageType.IMAGE, MessageDirection.OUTGOING, None, "Check this out"),
            (MessageType.PAID_MESSAGE, MessageDirection.OUTGOING, Decimal("30.00"), "Exclusive content"),
            (MessageType.TEXT, MessageDirection.INCOMING, None, "Awesome!"),
            (MessageType.TIP, MessageDirection.INCOMING, Decimal("50.00"), "You're amazing!"),
        ]
        
        for msg_type, direction, price, content in messages_data:
            message = Message(
                conversation_id=conversation.id,
                platform_message_id=f"msg_{len(messages_data)}",
                type=msg_type,
                direction=direction,
                content=content,
                price=price,
                sent_at=datetime.utcnow() - timedelta(hours=len(messages_data))
            )
            db_session.add(message)
        
        await db_session.commit()
        
        # Calculate conversation analytics
        analytics = await conversation.calculate_analytics(db_session)
        
        assert analytics["total_messages"] == 7
        assert analytics["messages_sent"] == 3
        assert analytics["messages_received"] == 4
        assert analytics["total_tips"] == 2
        assert analytics["tips_amount"] == Decimal("70.00")
        assert analytics["ppv_messages"] == 1
        assert analytics["ppv_potential"] == Decimal("30.00")
        assert analytics["response_rate"] > 0
    
    @pytest.mark.asyncio
    async def test_message_scheduling(self, db_session: AsyncSession):
        """Test message scheduling functionality."""
        model = await create_test_model()
        conversation = Conversation(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_conversation_id="schedule_test",
            fan_username="schedule_fan"
        )
        db_session.add(conversation)
        await db_session.commit()
        
        # Schedule a message
        scheduled_time = datetime.utcnow() + timedelta(hours=2)
        message = Message(
            conversation_id=conversation.id,
            platform_message_id="sched_1",
            type=MessageType.TEXT,
            content="Good morning! Hope you have a great day!",
            direction=MessageDirection.OUTGOING,
            status=MessageStatus.SCHEDULED,
            scheduled_for=scheduled_time,
            metadata={
                "scheduler": "model123",
                "repeat": "daily",
                "timezone": "America/New_York"
            }
        )
        
        db_session.add(message)
        await db_session.commit()
        
        assert message.is_scheduled() is True
        assert message.scheduled_for == scheduled_time
        
        # Get pending scheduled messages
        pending = await Message.get_pending_scheduled(
            db_session,
            model_id=model.id,
            cutoff_time=datetime.utcnow() + timedelta(hours=3)
        )
        
        assert len(pending) == 1
        assert pending[0].id == message.id
        
        # Send scheduled message
        await message.send_scheduled()
        assert message.status == MessageStatus.SENT
        assert message.sent_at is not None
        assert message.scheduled_for is None