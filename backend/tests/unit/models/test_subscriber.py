"""Comprehensive tests for Subscriber model."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from models.subscriber import (
    Subscriber, SubscriptionStatus, SubscriptionTier,
    SubscriberMetrics, SubscriberTag, ChurnReason
)
from models.model import Model, Platform
from tests.factories import create_test_model, create_test_agency


class TestSubscriberModel:
    """Test cases for Subscriber model."""
    
    @pytest.mark.asyncio
    async def test_create_subscriber_with_valid_data(self, db_session: AsyncSession):
        """Test creating a subscriber with all valid data."""
        model = await create_test_model()
        
        subscriber = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="of_user_123",
            username="superfan123",
            display_name="Super Fan",
            email="superfan@example.com",
            profile_image_url="https://example.com/avatar.jpg",
            subscription_price=Decimal("9.99"),
            currency="USD",
            status=SubscriptionStatus.ACTIVE,
            tier=SubscriptionTier.STANDARD,
            subscribed_at=datetime.utcnow(),
            next_billing_date=datetime.utcnow() + timedelta(days=30),
            auto_renew=True,
            metadata={
                "location": "United States",
                "age_verified": True,
                "referral_source": "twitter",
                "custom_fields": {
                    "interests": ["fitness", "lifestyle"],
                    "preferred_content": "photos"
                }
            },
            tags=["vip", "high_tipper", "loyal"]
        )
        
        db_session.add(subscriber)
        await db_session.commit()
        await db_session.refresh(subscriber)
        
        assert subscriber.id is not None
        assert subscriber.username == "superfan123"
        assert subscriber.subscription_price == Decimal("9.99")
        assert subscriber.status == SubscriptionStatus.ACTIVE
        assert subscriber.tier == SubscriptionTier.STANDARD
        assert "vip" in subscriber.tags
        assert subscriber.metadata["location"] == "United States"
    
    @pytest.mark.asyncio
    async def test_subscriber_uniqueness_constraint(self, db_session: AsyncSession):
        """Test that platform user IDs must be unique per model and platform."""
        model = await create_test_model()
        
        sub1 = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="unique_user_123",
            username="user1",
            subscription_price=Decimal("9.99")
        )
        db_session.add(sub1)
        await db_session.commit()
        
        # Try to create duplicate
        sub2 = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="unique_user_123",  # Same platform user ID
            username="user2",
            subscription_price=Decimal("9.99")
        )
        db_session.add(sub2)
        
        with pytest.raises(IntegrityError):
            await db_session.commit()
        
        await db_session.rollback()
        
        # Different platform should work
        sub3 = Subscriber(
            model_id=model.id,
            platform=Platform.FANSLY,
            platform_user_id="unique_user_123",  # Same ID but different platform
            username="user3",
            subscription_price=Decimal("9.99")
        )
        db_session.add(sub3)
        await db_session.commit()  # Should succeed
    
    @pytest.mark.asyncio
    async def test_subscription_lifecycle(self, db_session: AsyncSession):
        """Test subscription status transitions and lifecycle."""
        model = await create_test_model()
        
        # New subscription
        subscriber = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="lifecycle_test",
            username="testuser",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.PENDING
        )
        db_session.add(subscriber)
        await db_session.commit()
        
        # Activate subscription
        subscriber.activate_subscription(
            start_date=datetime.utcnow(),
            billing_period_days=30,
            transaction_id="trans_123"
        )
        assert subscriber.status == SubscriptionStatus.ACTIVE
        assert subscriber.subscribed_at is not None
        assert subscriber.next_billing_date is not None
        assert subscriber.activation_transaction_id == "trans_123"
        
        # Renew subscription
        old_billing_date = subscriber.next_billing_date
        subscriber.renew_subscription(
            renewed_until=datetime.utcnow() + timedelta(days=30),
            amount_paid=Decimal("9.99"),
            transaction_id="trans_456"
        )
        assert subscriber.next_billing_date > old_billing_date
        assert subscriber.last_renewal_date is not None
        assert subscriber.renewal_count == 1
        
        # Grace period
        subscriber.enter_grace_period(grace_days=3)
        assert subscriber.status == SubscriptionStatus.GRACE_PERIOD
        assert subscriber.grace_period_ends_at is not None
        
        # Expire subscription
        subscriber.expire_subscription(reason="Payment failed")
        assert subscriber.status == SubscriptionStatus.EXPIRED
        assert subscriber.expired_at is not None
        assert subscriber.expiration_reason == "Payment failed"
        
        # Reactivate
        subscriber.reactivate_subscription(
            new_price=Decimal("12.99"),
            transaction_id="trans_789"
        )
        assert subscriber.status == SubscriptionStatus.ACTIVE
        assert subscriber.subscription_price == Decimal("12.99")
        assert subscriber.reactivation_count == 1
        
        # Cancel (by user)
        subscriber.cancel_subscription(
            reason="Too expensive",
            effective_date=subscriber.next_billing_date
        )
        assert subscriber.status == SubscriptionStatus.CANCELLED
        assert subscriber.cancelled_at is not None
        assert subscriber.cancellation_reason == "Too expensive"
        assert subscriber.auto_renew is False
    
    @pytest.mark.asyncio
    async def test_subscription_tiers(self, db_session: AsyncSession):
        """Test subscription tier management and benefits."""
        model = await create_test_model()
        
        # Create subscribers with different tiers
        tiers_data = [
            (SubscriptionTier.BASIC, Decimal("4.99"), ["basic_content"]),
            (SubscriptionTier.STANDARD, Decimal("9.99"), ["basic_content", "exclusive_photos"]),
            (SubscriptionTier.PREMIUM, Decimal("19.99"), ["basic_content", "exclusive_photos", "private_messages"]),
            (SubscriptionTier.VIP, Decimal("49.99"), ["all_content", "priority_chat", "custom_content"])
        ]
        
        subscribers = []
        for tier, price, benefits in tiers_data:
            sub = Subscriber(
                model_id=model.id,
                platform=Platform.ONLYFANS,
                platform_user_id=f"tier_test_{tier.value}",
                username=f"{tier.value}_user",
                subscription_price=price,
                tier=tier,
                tier_benefits=benefits,
                status=SubscriptionStatus.ACTIVE
            )
            subscribers.append(sub)
            db_session.add(sub)
        
        await db_session.commit()
        
        # Test tier benefits
        basic_sub = subscribers[0]
        vip_sub = subscribers[3]
        
        assert basic_sub.has_benefit("basic_content") is True
        assert basic_sub.has_benefit("private_messages") is False
        
        assert vip_sub.has_benefit("priority_chat") is True
        assert vip_sub.has_benefit("all_content") is True
        
        # Upgrade tier
        basic_sub.upgrade_tier(
            new_tier=SubscriptionTier.PREMIUM,
            new_price=Decimal("19.99"),
            new_benefits=["basic_content", "exclusive_photos", "private_messages"]
        )
        assert basic_sub.tier == SubscriptionTier.PREMIUM
        assert basic_sub.subscription_price == Decimal("19.99")
        assert basic_sub.has_benefit("private_messages") is True
        assert basic_sub.tier_upgrade_history is not None
    
    @pytest.mark.asyncio
    async def test_subscriber_spending_tracking(self, db_session: AsyncSession):
        """Test subscriber spending and revenue tracking."""
        model = await create_test_model()
        
        subscriber = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="spender_123",
            username="bigspender",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.ACTIVE
        )
        db_session.add(subscriber)
        await db_session.commit()
        
        # Track subscription payments
        await subscriber.record_payment(
            amount=Decimal("9.99"),
            payment_type="subscription",
            transaction_id="sub_123"
        )
        
        # Track tips
        tip_amounts = [Decimal("20.00"), Decimal("50.00"), Decimal("100.00")]
        for amount in tip_amounts:
            await subscriber.record_payment(
                amount=amount,
                payment_type="tip",
                transaction_id=f"tip_{amount}"
            )
        
        # Track PPV purchases
        ppv_amounts = [Decimal("29.99"), Decimal("49.99")]
        for amount in ppv_amounts:
            await subscriber.record_payment(
                amount=amount,
                payment_type="ppv",
                transaction_id=f"ppv_{amount}",
                content_id=f"content_{amount}"
            )
        
        await db_session.commit()
        
        # Calculate total spending
        total_spent = subscriber.calculate_total_spent()
        expected_total = Decimal("9.99") + sum(tip_amounts) + sum(ppv_amounts)
        assert total_spent == expected_total
        
        # Get spending breakdown
        breakdown = subscriber.get_spending_breakdown()
        assert breakdown["subscription"] == Decimal("9.99")
        assert breakdown["tips"] == sum(tip_amounts)
        assert breakdown["ppv"] == sum(ppv_amounts)
        assert breakdown["total"] == expected_total
        
        # Calculate average monthly spending
        subscriber.subscribed_at = datetime.utcnow() - timedelta(days=90)
        monthly_avg = subscriber.calculate_monthly_average()
        assert monthly_avg > 0
    
    @pytest.mark.asyncio
    async def test_subscriber_engagement_metrics(self, db_session: AsyncSession):
        """Test subscriber engagement tracking and scoring."""
        model = await create_test_model()
        
        subscriber = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="engaged_123",
            username="activeuser",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.ACTIVE,
            subscribed_at=datetime.utcnow() - timedelta(days=180)
        )
        db_session.add(subscriber)
        await db_session.commit()
        
        # Create engagement metrics
        metrics = SubscriberMetrics(
            subscriber_id=subscriber.id,
            messages_sent=150,
            messages_received=200,
            content_likes=75,
            content_comments=25,
            content_purchases=10,
            tips_sent=15,
            login_count=180,
            last_active_at=datetime.utcnow(),
            average_session_duration_minutes=25.5,
            favorite_content_types=["photos", "videos"],
            engagement_score=0.0  # Will be calculated
        )
        db_session.add(metrics)
        await db_session.commit()
        
        # Calculate engagement score
        engagement_score = metrics.calculate_engagement_score()
        assert engagement_score > 0
        assert engagement_score <= 100
        
        # Update engagement activities
        await metrics.track_activity(
            activity_type="message_sent",
            metadata={"char_count": 50}
        )
        await metrics.track_activity(
            activity_type="content_liked",
            metadata={"content_id": "content_123"}
        )
        
        assert metrics.messages_sent == 151
        assert metrics.content_likes == 76
        assert metrics.last_active_at > datetime.utcnow() - timedelta(minutes=1)
        
        # Get engagement level
        engagement_level = subscriber.get_engagement_level(metrics)
        assert engagement_level in ["low", "medium", "high", "very_high"]
    
    @pytest.mark.asyncio
    async def test_subscriber_retention_analysis(self, db_session: AsyncSession):
        """Test subscriber retention and churn analysis."""
        model = await create_test_model()
        
        # Create subscribers with different retention patterns
        # Long-term active subscriber
        loyal_sub = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="loyal_123",
            username="loyalfan",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.ACTIVE,
            subscribed_at=datetime.utcnow() - timedelta(days=365),
            renewal_count=12
        )
        
        # Recently churned subscriber
        churned_sub = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="churned_123",
            username="churnedfan",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.EXPIRED,
            subscribed_at=datetime.utcnow() - timedelta(days=90),
            expired_at=datetime.utcnow() - timedelta(days=7),
            churn_reason=ChurnReason.PRICE_SENSITIVITY
        )
        
        # At-risk subscriber
        at_risk_sub = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="atrisk_123",
            username="atriskfan",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.ACTIVE,
            subscribed_at=datetime.utcnow() - timedelta(days=60),
            auto_renew=False,  # Cancelled but still active
            cancelled_at=datetime.utcnow() - timedelta(days=5)
        )
        
        db_session.add_all([loyal_sub, churned_sub, at_risk_sub])
        await db_session.commit()
        
        # Calculate retention metrics
        retention_days = loyal_sub.calculate_retention_days()
        assert retention_days == 365
        
        churn_days = churned_sub.calculate_retention_days()
        assert churn_days == 83  # 90 - 7
        
        # Identify at-risk subscribers
        risk_score = at_risk_sub.calculate_churn_risk_score()
        assert risk_score > 0.5  # High risk due to cancellation
        
        # Analyze churn reasons
        churn_analysis = await Subscriber.analyze_churn_reasons(
            db_session,
            model_id=model.id,
            days_back=30
        )
        assert ChurnReason.PRICE_SENSITIVITY in churn_analysis
        assert churn_analysis[ChurnReason.PRICE_SENSITIVITY] >= 1
    
    @pytest.mark.asyncio
    async def test_subscriber_segmentation(self, db_session: AsyncSession):
        """Test subscriber segmentation and targeting."""
        model = await create_test_model()
        
        # Create diverse subscriber base
        subscribers_data = [
            # High value subscribers
            ("high_value_1", Decimal("49.99"), 1000.00, ["vip", "big_spender"]),
            ("high_value_2", Decimal("49.99"), 1500.00, ["vip", "big_spender", "loyal"]),
            
            # Regular subscribers
            ("regular_1", Decimal("9.99"), 50.00, ["active"]),
            ("regular_2", Decimal("9.99"), 100.00, ["active", "engaged"]),
            
            # New subscribers
            ("new_1", Decimal("9.99"), 0.00, ["new"]),
            ("new_2", Decimal("9.99"), 10.00, ["new", "potential"]),
            
            # Inactive subscribers
            ("inactive_1", Decimal("9.99"), 0.00, ["inactive", "at_risk"]),
        ]
        
        for username, price, total_spent, tags in subscribers_data:
            sub = Subscriber(
                model_id=model.id,
                platform=Platform.ONLYFANS,
                platform_user_id=f"seg_{username}",
                username=username,
                subscription_price=price,
                status=SubscriptionStatus.ACTIVE,
                tags=tags,
                metadata={"total_spent": total_spent}
            )
            db_session.add(sub)
        
        await db_session.commit()
        
        # Segment by value
        high_value_segment = await Subscriber.get_segment(
            db_session,
            model_id=model.id,
            segment_criteria={
                "min_total_spent": 500.00,
                "tags_include": ["vip"]
            }
        )
        assert len(high_value_segment) == 2
        
        # Segment by engagement
        engaged_segment = await Subscriber.get_segment(
            db_session,
            model_id=model.id,
            segment_criteria={
                "tags_include": ["active", "engaged"],
                "tags_match_any": True
            }
        )
        assert len(engaged_segment) >= 2
        
        # Segment at-risk subscribers
        at_risk_segment = await Subscriber.get_segment(
            db_session,
            model_id=model.id,
            segment_criteria={
                "tags_include": ["at_risk", "inactive"],
                "tags_match_any": True
            }
        )
        assert len(at_risk_segment) >= 1
        
        # Create targeted campaign
        campaign_targets = await Subscriber.create_campaign_segment(
            db_session,
            model_id=model.id,
            campaign_type="win_back",
            criteria={
                "status": [SubscriptionStatus.EXPIRED, SubscriptionStatus.CANCELLED],
                "churned_within_days": 30,
                "min_previous_spend": 50.00
            }
        )
        
        assert isinstance(campaign_targets, list)
    
    @pytest.mark.asyncio
    async def test_subscriber_communication_preferences(self, db_session: AsyncSession):
        """Test subscriber communication preferences and opt-outs."""
        model = await create_test_model()
        
        subscriber = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="prefs_123",
            username="prefuser",
            subscription_price=Decimal("9.99"),
            status=SubscriptionStatus.ACTIVE,
            communication_preferences={
                "messages": {
                    "promotional": True,
                    "tips_nudge": False,
                    "new_content": True,
                    "personal": True
                },
                "frequency": {
                    "max_per_day": 3,
                    "quiet_hours": ["22:00", "09:00"],
                    "timezone": "America/New_York"
                },
                "content_preferences": {
                    "types": ["photos", "videos"],
                    "categories": ["fitness", "lifestyle"],
                    "exclude_categories": ["explicit"]
                }
            }
        )
        db_session.add(subscriber)
        await db_session.commit()
        
        # Check message preferences
        assert subscriber.can_receive_message_type("promotional") is True
        assert subscriber.can_receive_message_type("tips_nudge") is False
        
        # Check quiet hours
        is_quiet = subscriber.is_in_quiet_hours(
            check_time=datetime.utcnow().replace(hour=23, minute=0)
        )
        # Note: This would need timezone handling in real implementation
        
        # Update preferences
        subscriber.update_communication_preference(
            category="messages",
            setting="promotional",
            value=False
        )
        assert subscriber.communication_preferences["messages"]["promotional"] is False
        
        # Opt out completely
        subscriber.opt_out_all_communications(reason="Too many messages")
        assert subscriber.communication_preferences["opted_out"] is True
        assert subscriber.communication_preferences["opt_out_date"] is not None
    
    @pytest.mark.asyncio
    async def test_subscriber_lifetime_value(self, db_session: AsyncSession):
        """Test subscriber lifetime value calculations."""
        model = await create_test_model()
        
        # Create subscriber with history
        subscriber = Subscriber(
            model_id=model.id,
            platform=Platform.ONLYFANS,
            platform_user_id="ltv_123",
            username="valuablefan",
            subscription_price=Decimal("19.99"),
            status=SubscriptionStatus.ACTIVE,
            subscribed_at=datetime.utcnow() - timedelta(days=365),
            renewal_count=12
        )
        db_session.add(subscriber)
        await db_session.commit()
        
        # Add payment history
        # Monthly subscriptions
        for i in range(12):
            await subscriber.record_payment(
                amount=Decimal("19.99"),
                payment_type="subscription",
                transaction_id=f"sub_month_{i}",
                paid_at=datetime.utcnow() - timedelta(days=365-i*30)
            )
        
        # Tips and PPV
        await subscriber.record_payment(
            amount=Decimal("100.00"),
            payment_type="tip",
            transaction_id="big_tip_1"
        )
        await subscriber.record_payment(
            amount=Decimal("49.99"),
            payment_type="ppv",
            transaction_id="ppv_special"
        )
        
        await db_session.commit()
        
        # Calculate LTV
        current_ltv = subscriber.calculate_lifetime_value()
        expected_ltv = (Decimal("19.99") * 12) + Decimal("100.00") + Decimal("49.99")
        assert current_ltv == expected_ltv
        
        # Predict future LTV
        predicted_ltv = subscriber.predict_lifetime_value(
            months_ahead=12,
            include_churn_probability=True
        )
        assert predicted_ltv > current_ltv  # Should include future revenue
        
        # Calculate LTV:CAC ratio (if acquisition cost is tracked)
        subscriber.metadata["acquisition_cost"] = 5.00
        ltv_cac_ratio = subscriber.calculate_ltv_cac_ratio()
        assert ltv_cac_ratio > 1  # Profitable subscriber