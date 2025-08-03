"""Comprehensive tests for Model entity."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from models.model import Model, ModelStatus, ModelVerificationStatus, Platform
from models.agency import Agency
from models.user import User, UserRole
from tests.factories import create_test_model, create_test_agency, create_test_user


class TestModelEntity:
    """Test cases for Model entity."""
    
    @pytest.mark.asyncio
    async def test_create_model_with_valid_data(self, db_session: AsyncSession):
        """Test creating a model with all valid data."""
        agency = await create_test_agency()
        user = await create_test_user(role=UserRole.MODEL)
        
        model = Model(
            user_id=user.id,
            agency_id=agency.id,
            name="Jane Doe",
            stage_name="JaneDoe_Official",
            bio="Professional model and content creator",
            profile_image_url="https://example.com/profile.jpg",
            cover_image_url="https://example.com/cover.jpg",
            status=ModelStatus.ACTIVE,
            verification_status=ModelVerificationStatus.VERIFIED,
            platforms={
                Platform.ONLYFANS: {
                    "username": "janedoe_of",
                    "profile_url": "https://onlyfans.com/janedoe_of",
                    "is_active": True,
                    "subscriber_count": 1500
                },
                Platform.FANSLY: {
                    "username": "janedoe_fansly",
                    "profile_url": "https://fansly.com/janedoe_fansly",
                    "is_active": True,
                    "subscriber_count": 800
                }
            },
            custom_commission_rate=Decimal("0.15"),
            tags=["fitness", "lifestyle", "exclusive"],
            settings={
                "auto_welcome": True,
                "ppv_pricing": {
                    "min": 10,
                    "max": 200
                },
                "chat_response_time": "24_hours"
            }
        )
        
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)
        
        assert model.id is not None
        assert model.name == "Jane Doe"
        assert model.stage_name == "JaneDoe_Official"
        assert model.status == ModelStatus.ACTIVE
        assert model.verification_status == ModelVerificationStatus.VERIFIED
        assert model.custom_commission_rate == Decimal("0.15")
        assert "fitness" in model.tags
        assert model.platforms[Platform.ONLYFANS]["subscriber_count"] == 1500
    
    @pytest.mark.asyncio
    async def test_model_stage_name_uniqueness(self, db_session: AsyncSession):
        """Test that stage names must be unique."""
        agency = await create_test_agency()
        
        model1 = await create_test_model(
            agency=agency,
            stage_name="UniqueStage"
        )
        
        # Try to create another model with same stage name
        user2 = await create_test_user(role=UserRole.MODEL, username="model2")
        model2 = Model(
            user_id=user2.id,
            agency_id=agency.id,
            name="Different Name",
            stage_name="UniqueStage"  # Same stage name
        )
        db_session.add(model2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_model_status_transitions(self, db_session: AsyncSession):
        """Test valid model status transitions."""
        model = await create_test_model(status=ModelStatus.PENDING)
        
        # Pending -> Active (after verification)
        model.activate()
        assert model.status == ModelStatus.ACTIVE
        assert model.activated_at is not None
        
        # Active -> Paused
        model.pause(reason="Vacation", duration_days=14)
        assert model.status == ModelStatus.PAUSED
        assert model.paused_at is not None
        assert model.pause_reason == "Vacation"
        assert model.pause_ends_at is not None
        assert model.pause_ends_at > datetime.utcnow()
        
        # Check if pause expired
        model.paused_at = datetime.utcnow() - timedelta(days=15)
        model.pause_ends_at = datetime.utcnow() - timedelta(days=1)
        assert model.is_pause_expired() is True
        
        # Auto-reactivate after pause
        model.check_pause_status()
        assert model.status == ModelStatus.ACTIVE
        
        # Active -> Suspended
        model.suspend(reason="Policy violation", suspended_by="admin123")
        assert model.status == ModelStatus.SUSPENDED
        assert model.suspended_at is not None
        assert model.suspension_reason == "Policy violation"
        
        # Suspended -> Active (after resolution)
        model.unsuspend(unsuspended_by="admin123")
        assert model.status == ModelStatus.ACTIVE
        assert model.suspended_at is None
    
    @pytest.mark.asyncio
    async def test_model_verification_process(self, db_session: AsyncSession):
        """Test model verification workflow."""
        model = await create_test_model(
            verification_status=ModelVerificationStatus.PENDING
        )
        
        # Submit verification documents
        await model.submit_verification_document(
            document_type="government_id",
            document_url="https://storage.example.com/docs/id.jpg",
            metadata={"document_number": "XXXX1234"}
        )
        
        await model.submit_verification_document(
            document_type="selfie_with_id",
            document_url="https://storage.example.com/docs/selfie.jpg"
        )
        
        assert model.verification_status == ModelVerificationStatus.PENDING
        assert len(model.verification_documents) == 2
        
        # Start review
        model.start_verification_review(reviewer_id="verifier123")
        assert model.verification_status == ModelVerificationStatus.UNDER_REVIEW
        assert model.verification_reviewer == "verifier123"
        
        # Approve verification
        model.approve_verification(
            approved_by="verifier123",
            notes="All documents verified"
        )
        assert model.verification_status == ModelVerificationStatus.VERIFIED
        assert model.verified_at is not None
        assert model.verification_notes == "All documents verified"
        
        # Test rejection flow
        model2 = await create_test_model(
            verification_status=ModelVerificationStatus.UNDER_REVIEW
        )
        
        model2.reject_verification(
            rejected_by="verifier456",
            reason="ID document unclear",
            can_resubmit=True
        )
        assert model2.verification_status == ModelVerificationStatus.REJECTED
        assert model2.verification_rejection_reason == "ID document unclear"
        assert model2.can_resubmit_verification is True
    
    @pytest.mark.asyncio
    async def test_model_platform_management(self, db_session: AsyncSession):
        """Test model platform integration management."""
        model = await create_test_model()
        
        # Add platform
        await model.add_platform(
            platform=Platform.ONLYFANS,
            username="test_model_of",
            profile_url="https://onlyfans.com/test_model_of",
            credentials={
                "api_key": "encrypted_key",
                "api_secret": "encrypted_secret"
            }
        )
        
        assert Platform.ONLYFANS in model.platforms
        assert model.platforms[Platform.ONLYFANS]["username"] == "test_model_of"
        assert model.platforms[Platform.ONLYFANS]["is_active"] is True
        
        # Update platform info
        await model.update_platform(
            platform=Platform.ONLYFANS,
            data={
                "subscriber_count": 2500,
                "monthly_revenue": 15000.00,
                "last_synced": datetime.utcnow()
            }
        )
        
        assert model.platforms[Platform.ONLYFANS]["subscriber_count"] == 2500
        assert model.platforms[Platform.ONLYFANS]["monthly_revenue"] == 15000.00
        
        # Deactivate platform
        model.deactivate_platform(Platform.ONLYFANS)
        assert model.platforms[Platform.ONLYFANS]["is_active"] is False
        
        # Remove platform
        model.remove_platform(Platform.ONLYFANS)
        assert Platform.ONLYFANS not in model.platforms
    
    @pytest.mark.asyncio
    async def test_model_earnings_tracking(self, db_session: AsyncSession):
        """Test model earnings tracking and statistics."""
        model = await create_test_model()
        
        # Add earnings
        from models.financial import Earning, EarningType
        
        earnings_data = [
            (Decimal("500.00"), EarningType.SUBSCRIPTION, Platform.ONLYFANS),
            (Decimal("200.00"), EarningType.TIP, Platform.ONLYFANS),
            (Decimal("300.00"), EarningType.PPV, Platform.FANSLY),
            (Decimal("150.00"), EarningType.TIP, Platform.FANSLY),
        ]
        
        for amount, earning_type, platform in earnings_data:
            earning = Earning(
                model_id=model.id,
                agency_id=model.agency_id,
                amount=amount,
                type=earning_type,
                platform=platform.value,
                earned_at=datetime.utcnow() - timedelta(days=1)
            )
            db_session.add(earning)
        
        await db_session.commit()
        
        # Calculate earnings statistics
        stats = await model.get_earnings_statistics(
            db_session,
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow()
        )
        
        assert stats["total_earnings"] == Decimal("1150.00")
        assert stats["earnings_by_type"][EarningType.SUBSCRIPTION] == Decimal("500.00")
        assert stats["earnings_by_type"][EarningType.TIP] == Decimal("350.00")
        assert stats["earnings_by_type"][EarningType.PPV] == Decimal("300.00")
        assert stats["earnings_by_platform"][Platform.ONLYFANS] == Decimal("700.00")
        assert stats["earnings_by_platform"][Platform.FANSLY] == Decimal("450.00")
        assert stats["daily_average"] == Decimal("164.29")  # 1150 / 7 days
    
    @pytest.mark.asyncio
    async def test_model_subscriber_metrics(self, db_session: AsyncSession):
        """Test model subscriber tracking and analytics."""
        model = await create_test_model()
        
        # Add subscriber data
        from models.subscriber import Subscriber, SubscriptionStatus
        
        # Create active subscribers
        for i in range(50):
            subscriber = Subscriber(
                model_id=model.id,
                platform=Platform.ONLYFANS,
                platform_user_id=f"user_{i}",
                username=f"subscriber{i}",
                subscription_price=Decimal("9.99"),
                status=SubscriptionStatus.ACTIVE,
                subscribed_at=datetime.utcnow() - timedelta(days=30)
            )
            db_session.add(subscriber)
        
        # Create churned subscribers
        for i in range(20):
            subscriber = Subscriber(
                model_id=model.id,
                platform=Platform.ONLYFANS,
                platform_user_id=f"churned_{i}",
                username=f"churned{i}",
                subscription_price=Decimal("9.99"),
                status=SubscriptionStatus.EXPIRED,
                subscribed_at=datetime.utcnow() - timedelta(days=60),
                expired_at=datetime.utcnow() - timedelta(days=5)
            )
            db_session.add(subscriber)
        
        await db_session.commit()
        
        # Get subscriber metrics
        metrics = await model.get_subscriber_metrics(db_session)
        
        assert metrics["total_active"] == 50
        assert metrics["total_churned"] == 20
        assert metrics["churn_rate"] == 0.286  # 20/70
        assert metrics["retention_rate"] == 0.714  # 50/70
        assert metrics["monthly_recurring_revenue"] == Decimal("499.50")  # 50 * 9.99
        assert metrics["average_subscription_duration_days"] > 0
    
    @pytest.mark.asyncio
    async def test_model_content_statistics(self, db_session: AsyncSession):
        """Test model content creation and engagement statistics."""
        model = await create_test_model()
        
        # Add content data
        from models.content import Content, ContentType, ContentStatus
        
        content_items = []
        for i in range(10):
            content = Content(
                model_id=model.id,
                type=ContentType.PHOTO if i < 7 else ContentType.VIDEO,
                title=f"Content {i}",
                status=ContentStatus.PUBLISHED,
                platform=Platform.ONLYFANS,
                views=100 * (i + 1),
                likes=10 * (i + 1),
                comments=5 * (i + 1),
                published_at=datetime.utcnow() - timedelta(days=i)
            )
            content_items.append(content)
            db_session.add(content)
        
        await db_session.commit()
        
        # Get content statistics
        stats = await model.get_content_statistics(
            db_session,
            period_days=30
        )
        
        assert stats["total_content"] == 10
        assert stats["content_by_type"][ContentType.PHOTO] == 7
        assert stats["content_by_type"][ContentType.VIDEO] == 3
        assert stats["total_views"] == 5500  # Sum of 100+200+...+1000
        assert stats["total_likes"] == 550   # Sum of 10+20+...+100
        assert stats["average_engagement_rate"] > 0
        assert stats["posting_frequency"] > 0
    
    @pytest.mark.asyncio
    async def test_model_chat_performance(self, db_session: AsyncSession):
        """Test model chat performance metrics."""
        model = await create_test_model()
        
        # Add chat data
        from models.conversation import Conversation
        from models.message import Message, MessageType
        
        # Create conversations
        conversations = []
        for i in range(20):
            conv = Conversation(
                model_id=model.id,
                platform=Platform.ONLYFANS,
                platform_conversation_id=f"conv_{i}",
                fan_username=f"fan{i}",
                started_at=datetime.utcnow() - timedelta(days=5),
                last_message_at=datetime.utcnow() - timedelta(hours=i)
            )
            conversations.append(conv)
            db_session.add(conv)
        
        await db_session.commit()
        
        # Add messages
        for conv in conversations[:10]:  # First 10 conversations
            # Fan message
            fan_msg = Message(
                conversation_id=conv.id,
                type=MessageType.TEXT,
                sender_type="fan",
                content="Hi there!",
                sent_at=datetime.utcnow() - timedelta(hours=2)
            )
            db_session.add(fan_msg)
            
            # Model response
            model_msg = Message(
                conversation_id=conv.id,
                type=MessageType.TEXT,
                sender_type="model",
                content="Hello! Thanks for subscribing!",
                sent_at=datetime.utcnow() - timedelta(hours=1)
            )
            db_session.add(model_msg)
        
        await db_session.commit()
        
        # Get chat performance metrics
        metrics = await model.get_chat_performance_metrics(
            db_session,
            period_days=7
        )
        
        assert metrics["total_conversations"] == 20
        assert metrics["active_conversations"] == 10
        assert metrics["response_rate"] == 0.5  # 10/20
        assert metrics["average_response_time_hours"] <= 2
        assert metrics["messages_sent"] == 10
        assert metrics["messages_received"] == 10
    
    @pytest.mark.asyncio
    async def test_model_settings_preferences(self, db_session: AsyncSession):
        """Test model settings and preferences management."""
        model = await create_test_model()
        
        # Update chat settings
        chat_settings = {
            "auto_welcome": {
                "enabled": True,
                "message": "Welcome! Check out my exclusive content!",
                "delay_minutes": 5,
                "include_tip_menu": True
            },
            "response_templates": [
                {
                    "trigger": "price",
                    "response": "My content starts at $10. Check my tip menu!"
                },
                {
                    "trigger": "custom",
                    "response": "I offer custom content starting at $50"
                }
            ],
            "availability": {
                "timezone": "America/New_York",
                "hours": {
                    "monday": {"start": "10:00", "end": "22:00"},
                    "tuesday": {"start": "10:00", "end": "22:00"},
                    "wednesday": {"start": "10:00", "end": "22:00"},
                    "thursday": {"start": "10:00", "end": "22:00"},
                    "friday": {"start": "12:00", "end": "00:00"},
                    "saturday": {"start": "12:00", "end": "00:00"},
                    "sunday": {"start": "14:00", "end": "20:00"}
                }
            }
        }
        
        model.update_chat_settings(chat_settings)
        await db_session.commit()
        
        assert model.get_setting("chat.auto_welcome.enabled") is True
        assert model.get_setting("chat.auto_welcome.delay_minutes") == 5
        assert len(model.get_setting("chat.response_templates")) == 2
        
        # Update content settings
        content_settings = {
            "watermark": {
                "enabled": True,
                "text": "@{stage_name}",
                "position": "bottom_right",
                "opacity": 0.7
            },
            "pricing": {
                "photo_sets": {"min": 15, "max": 100},
                "videos": {"min": 25, "max": 200},
                "custom_content": {"min": 50, "max": 500}
            },
            "auto_schedule": {
                "enabled": True,
                "times": ["09:00", "18:00"],
                "randomize_minutes": 30
            }
        }
        
        model.update_content_settings(content_settings)
        await db_session.commit()
        
        assert model.get_setting("content.watermark.enabled") is True
        assert model.get_setting("content.pricing.videos.min") == 25
    
    @pytest.mark.asyncio
    async def test_model_performance_ranking(self, db_session: AsyncSession):
        """Test model performance ranking within agency."""
        agency = await create_test_agency()
        
        # Create multiple models with different performance
        models_data = [
            ("TopModel", Decimal("10000.00"), 500),
            ("MidModel1", Decimal("5000.00"), 300),
            ("MidModel2", Decimal("4500.00"), 280),
            ("NewModel", Decimal("1000.00"), 50),
        ]
        
        models = []
        for name, revenue, subscribers in models_data:
            model = await create_test_model(
                agency=agency,
                name=name,
                stage_name=f"{name}_stage"
            )
            model.cached_metrics = {
                "monthly_revenue": float(revenue),
                "total_subscribers": subscribers,
                "engagement_rate": subscribers / 10.0
            }
            models.append(model)
            db_session.add(model)
        
        await db_session.commit()
        
        # Get rankings
        rankings = await Model.get_agency_rankings(
            db_session,
            agency_id=agency.id,
            metric="monthly_revenue"
        )
        
        assert len(rankings) == 4
        assert rankings[0]["name"] == "TopModel"
        assert rankings[0]["rank"] == 1
        assert rankings[0]["value"] == 10000.00
        assert rankings[3]["name"] == "NewModel"
        assert rankings[3]["rank"] == 4
    
    @pytest.mark.asyncio
    async def test_model_tags_categories(self, db_session: AsyncSession):
        """Test model tags and category management."""
        model = await create_test_model()
        
        # Add tags
        tags = ["blonde", "fitness", "milf", "exclusive", "fetish-friendly"]
        model.add_tags(tags)
        await db_session.commit()
        
        assert len(model.tags) == 5
        assert "fitness" in model.tags
        assert "milf" in model.tags
        
        # Remove tag
        model.remove_tag("fetish-friendly")
        assert len(model.tags) == 4
        assert "fetish-friendly" not in model.tags
        
        # Set categories
        model.set_categories(["Adult", "Lifestyle", "Fitness"])
        assert len(model.categories) == 3
        
        # Search by tags
        models_with_fitness = await Model.find_by_tags(
            db_session,
            tags=["fitness"],
            agency_id=model.agency_id
        )
        assert len(models_with_fitness) >= 1
        assert model.id in [m.id for m in models_with_fitness]
    
    @pytest.mark.asyncio
    async def test_model_collaboration_features(self, db_session: AsyncSession):
        """Test model collaboration and referral features."""
        agency = await create_test_agency()
        model1 = await create_test_model(agency=agency, name="Model1")
        model2 = await create_test_model(agency=agency, name="Model2")
        
        # Create collaboration
        collaboration = await model1.create_collaboration(
            with_model=model2,
            type="content_share",
            terms={
                "revenue_split": {"model1": 0.6, "model2": 0.4},
                "content_types": ["photos", "videos"],
                "duration_days": 30
            }
        )
        
        assert collaboration.status == "active"
        assert collaboration.initiator_id == model1.id
        assert collaboration.collaborator_id == model2.id
        
        # Track collaboration revenue
        await collaboration.add_revenue(
            amount=Decimal("1000.00"),
            platform=Platform.ONLYFANS,
            content_id="content_123"
        )
        
        splits = collaboration.calculate_revenue_splits()
        assert splits[model1.id] == Decimal("600.00")
        assert splits[model2.id] == Decimal("400.00")
        
        # End collaboration
        await collaboration.end(ended_by=model1.id, reason="Contract completed")
        assert collaboration.status == "completed"
    
    @pytest.mark.asyncio
    async def test_model_analytics_access(self, db_session: AsyncSession):
        """Test model analytics access permissions."""
        model = await create_test_model()
        
        # Model can access own analytics
        analytics = await model.get_available_analytics()
        assert "earnings_overview" in analytics
        assert "subscriber_growth" in analytics
        assert "content_performance" in analytics
        assert "chat_metrics" in analytics
        
        # Check analytics time ranges
        time_ranges = model.get_analytics_time_ranges()
        assert "last_7_days" in time_ranges
        assert "last_30_days" in time_ranges
        assert "last_90_days" in time_ranges
        assert "custom" in time_ranges
        
        # Export analytics
        export = await model.export_analytics(
            metrics=["earnings", "subscribers"],
            time_range="last_30_days",
            format="csv"
        )
        
        assert export["status"] == "success"
        assert export["file_url"] is not None
        assert export["expires_at"] > datetime.utcnow()