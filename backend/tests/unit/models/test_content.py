"""Comprehensive tests for Content model."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from models.content import (
    Content, ContentType, ContentStatus, ContentVisibility,
    ContentCategory, ContentTag, ContentMetrics
)
from models.model import Model, Platform
from tests.factories import create_test_model, create_test_agency


class TestContentModel:
    """Test cases for Content model."""
    
    @pytest.mark.asyncio
    async def test_create_content_with_valid_data(self, db_session: AsyncSession):
        """Test creating content with all valid data."""
        model = await create_test_model()
        
        content = Content(
            model_id=model.id,
            type=ContentType.PHOTO_SET,
            title="Beach Photoshoot 🌊",
            description="Exclusive beach photos from my latest shoot!",
            status=ContentStatus.PUBLISHED,
            visibility=ContentVisibility.SUBSCRIBERS_ONLY,
            platform=Platform.ONLYFANS,
            media_urls=[
                "https://cdn.example.com/photo1.jpg",
                "https://cdn.example.com/photo2.jpg",
                "https://cdn.example.com/photo3.jpg",
                "https://cdn.example.com/photo4.jpg",
                "https://cdn.example.com/photo5.jpg"
            ],
            thumbnail_url="https://cdn.example.com/thumb.jpg",
            price=Decimal("0.00"),  # Included with subscription
            categories=[ContentCategory.GLAMOUR, ContentCategory.SWIMWEAR],
            tags=["beach", "summer", "exclusive", "photoset"],
            metadata={
                "location": "Malibu Beach",
                "photographer": "John Doe Photography",
                "equipment": "Canon R5",
                "editing_software": "Lightroom",
                "shoot_date": "2024-01-15"
            },
            scheduled_for=None,  # Publish immediately
            published_at=datetime.utcnow()
        )
        
        db_session.add(content)
        await db_session.commit()
        await db_session.refresh(content)
        
        assert content.id is not None
        assert content.title == "Beach Photoshoot 🌊"
        assert content.type == ContentType.PHOTO_SET
        assert len(content.media_urls) == 5
        assert ContentCategory.GLAMOUR in content.categories
        assert "beach" in content.tags
        assert content.metadata["location"] == "Malibu Beach"
    
    @pytest.mark.asyncio
    async def test_content_type_validation(self, db_session: AsyncSession):
        """Test content type specific validations."""
        model = await create_test_model()
        
        # Photo set - requires multiple images
        with pytest.raises(ValueError, match="Photo set requires at least 2 photos"):
            photo_set = Content(
                model_id=model.id,
                type=ContentType.PHOTO_SET,
                title="Invalid Photo Set",
                media_urls=["https://cdn.example.com/single.jpg"]  # Only 1 photo
            )
            photo_set.validate()
        
        # Video - requires duration metadata
        with pytest.raises(ValueError, match="Video content requires duration"):
            video = Content(
                model_id=model.id,
                type=ContentType.VIDEO,
                title="Video Content",
                media_urls=["https://cdn.example.com/video.mp4"],
                metadata={}  # Missing duration
            )
            video.validate()
        
        # Valid video
        valid_video = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="Valid Video",
            media_urls=["https://cdn.example.com/video.mp4"],
            metadata={"duration_seconds": 180, "resolution": "1080p"}
        )
        valid_video.validate()  # Should not raise
        
        # Live stream - requires stream URL
        with pytest.raises(ValueError, match="Live stream requires stream URL"):
            live = Content(
                model_id=model.id,
                type=ContentType.LIVE_STREAM,
                title="Live Show",
                metadata={}  # Missing stream_url
            )
            live.validate()
    
    @pytest.mark.asyncio
    async def test_content_status_workflow(self, db_session: AsyncSession):
        """Test content status transitions and workflow."""
        model = await create_test_model()
        
        # Create draft content
        content = Content(
            model_id=model.id,
            type=ContentType.PHOTO,
            title="Draft Photo",
            status=ContentStatus.DRAFT,
            media_urls=["https://cdn.example.com/draft.jpg"]
        )
        db_session.add(content)
        await db_session.commit()
        
        assert content.status == ContentStatus.DRAFT
        assert content.published_at is None
        
        # Submit for review
        content.submit_for_review()
        assert content.status == ContentStatus.PENDING_REVIEW
        assert content.submitted_at is not None
        
        # Approve and schedule
        scheduled_time = datetime.utcnow() + timedelta(hours=24)
        content.approve_and_schedule(
            approved_by="moderator123",
            scheduled_for=scheduled_time,
            notes="Content approved, scheduled for tomorrow"
        )
        assert content.status == ContentStatus.SCHEDULED
        assert content.scheduled_for == scheduled_time
        assert content.approved_by == "moderator123"
        
        # Publish scheduled content
        content.scheduled_for = datetime.utcnow() - timedelta(minutes=1)
        content.publish_scheduled()
        assert content.status == ContentStatus.PUBLISHED
        assert content.published_at is not None
        
        # Archive old content
        content.archive(reason="Seasonal content")
        assert content.status == ContentStatus.ARCHIVED
        assert content.archived_at is not None
        assert content.archive_reason == "Seasonal content"
    
    @pytest.mark.asyncio
    async def test_content_visibility_rules(self, db_session: AsyncSession):
        """Test content visibility and access rules."""
        model = await create_test_model()
        
        # Public content
        public_content = Content(
            model_id=model.id,
            type=ContentType.PHOTO,
            title="Public Preview",
            visibility=ContentVisibility.PUBLIC,
            media_urls=["https://cdn.example.com/public.jpg"]
        )
        
        # Subscribers only
        subscriber_content = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="Subscriber Exclusive",
            visibility=ContentVisibility.SUBSCRIBERS_ONLY,
            media_urls=["https://cdn.example.com/exclusive.mp4"],
            metadata={"duration_seconds": 300}
        )
        
        # Paid content
        paid_content = Content(
            model_id=model.id,
            type=ContentType.PHOTO_SET,
            title="Premium Set",
            visibility=ContentVisibility.PAID,
            price=Decimal("29.99"),
            media_urls=[
                "https://cdn.example.com/premium1.jpg",
                "https://cdn.example.com/premium2.jpg"
            ]
        )
        
        # Tiered content
        tiered_content = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="VIP Only",
            visibility=ContentVisibility.TIERED,
            required_tier="vip",
            media_urls=["https://cdn.example.com/vip.mp4"],
            metadata={"duration_seconds": 600}
        )
        
        db_session.add_all([public_content, subscriber_content, paid_content, tiered_content])
        await db_session.commit()
        
        # Test access rules
        assert public_content.can_access(is_subscriber=False) is True
        assert subscriber_content.can_access(is_subscriber=False) is False
        assert subscriber_content.can_access(is_subscriber=True) is True
        assert paid_content.can_access(is_subscriber=True, has_purchased=False) is False
        assert paid_content.can_access(is_subscriber=True, has_purchased=True) is True
        assert tiered_content.can_access(is_subscriber=True, user_tier="basic") is False
        assert tiered_content.can_access(is_subscriber=True, user_tier="vip") is True
    
    @pytest.mark.asyncio
    async def test_content_pricing_strategies(self, db_session: AsyncSession):
        """Test different content pricing strategies."""
        model = await create_test_model()
        
        # PPV content with standard pricing
        ppv_content = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="Exclusive PPV Video",
            visibility=ContentVisibility.PAID,
            price=Decimal("49.99"),
            currency="USD",
            metadata={"duration_seconds": 900}
        )
        
        # Bundle pricing
        bundle_content = Content(
            model_id=model.id,
            type=ContentType.PHOTO_SET,
            title="Photo Bundle",
            visibility=ContentVisibility.PAID,
            price=Decimal("19.99"),
            bundle_discount=Decimal("0.20"),  # 20% off when bundled
            metadata={"photo_count": 20}
        )
        
        # Promotional pricing
        promo_content = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="Limited Time Offer",
            visibility=ContentVisibility.PAID,
            price=Decimal("39.99"),
            promotional_price=Decimal("24.99"),
            promotion_ends_at=datetime.utcnow() + timedelta(days=3),
            metadata={"duration_seconds": 600}
        )
        
        db_session.add_all([ppv_content, bundle_content, promo_content])
        await db_session.commit()
        
        # Test pricing calculations
        assert ppv_content.get_current_price() == Decimal("49.99")
        
        # Bundle price when purchased with other content
        bundle_price = bundle_content.get_bundle_price()
        assert bundle_price == Decimal("15.99")  # 19.99 * 0.8
        
        # Promotional price (active)
        assert promo_content.get_current_price() == Decimal("24.99")
        assert promo_content.is_on_promotion() is True
        
        # Promotional price (expired)
        promo_content.promotion_ends_at = datetime.utcnow() - timedelta(days=1)
        assert promo_content.get_current_price() == Decimal("39.99")
        assert promo_content.is_on_promotion() is False
    
    @pytest.mark.asyncio
    async def test_content_metrics_tracking(self, db_session: AsyncSession):
        """Test content metrics and engagement tracking."""
        model = await create_test_model()
        
        content = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="Popular Video",
            status=ContentStatus.PUBLISHED,
            media_urls=["https://cdn.example.com/video.mp4"],
            metadata={"duration_seconds": 300},
            published_at=datetime.utcnow() - timedelta(days=7)
        )
        db_session.add(content)
        await db_session.commit()
        
        # Initialize metrics
        metrics = ContentMetrics(
            content_id=content.id,
            views=0,
            likes=0,
            comments=0,
            shares=0,
            saves=0,
            revenue=Decimal("0.00")
        )
        db_session.add(metrics)
        await db_session.commit()
        
        # Track engagement
        await metrics.increment_views(count=150)
        await metrics.increment_likes(count=45)
        await metrics.add_comment()
        await metrics.add_comment()
        await metrics.add_share()
        await metrics.add_save()
        
        # Track revenue
        await metrics.add_revenue(Decimal("299.95"), purchase_count=6)
        
        await db_session.commit()
        await db_session.refresh(metrics)
        
        assert metrics.views == 150
        assert metrics.likes == 45
        assert metrics.comments == 2
        assert metrics.shares == 1
        assert metrics.saves == 1
        assert metrics.revenue == Decimal("299.95")
        assert metrics.purchases == 6
        
        # Calculate engagement rate
        engagement_rate = metrics.calculate_engagement_rate()
        assert engagement_rate > 0
        assert engagement_rate == (45 + 2 + 1 + 1) / 150 * 100
        
        # Calculate average revenue per view
        rpv = metrics.calculate_revenue_per_view()
        assert rpv == Decimal("299.95") / 150
    
    @pytest.mark.asyncio
    async def test_content_categories_tags(self, db_session: AsyncSession):
        """Test content categorization and tagging system."""
        model = await create_test_model()
        
        # Create content with multiple categories and tags
        content = Content(
            model_id=model.id,
            type=ContentType.PHOTO_SET,
            title="Fitness Photoshoot",
            categories=[
                ContentCategory.FITNESS,
                ContentCategory.LIFESTYLE,
                ContentCategory.GLAMOUR
            ],
            tags=["workout", "gym", "fitness", "motivation", "exclusive"],
            media_urls=["https://cdn.example.com/fit1.jpg", "https://cdn.example.com/fit2.jpg"]
        )
        db_session.add(content)
        await db_session.commit()
        
        # Test category filtering
        fitness_content = await Content.find_by_category(
            db_session,
            model_id=model.id,
            category=ContentCategory.FITNESS
        )
        assert len(fitness_content) >= 1
        assert content.id in [c.id for c in fitness_content]
        
        # Test tag searching
        tagged_content = await Content.find_by_tags(
            db_session,
            model_id=model.id,
            tags=["fitness", "exclusive"],
            match_all=True
        )
        assert len(tagged_content) >= 1
        
        # Add trending tags
        await content.add_trending_tags(["trending", "viral"])
        assert "trending" in content.tags
        assert len(content.tags) == 7
        
        # Get popular tags for model
        popular_tags = await Content.get_popular_tags(
            db_session,
            model_id=model.id,
            limit=5
        )
        assert len(popular_tags) > 0
        assert "fitness" in [tag["name"] for tag in popular_tags]
    
    @pytest.mark.asyncio
    async def test_content_scheduling_queue(self, db_session: AsyncSession):
        """Test content scheduling and queue management."""
        model = await create_test_model()
        
        # Create multiple scheduled content items
        scheduled_times = [
            datetime.utcnow() + timedelta(hours=1),
            datetime.utcnow() + timedelta(hours=3),
            datetime.utcnow() + timedelta(hours=6),
            datetime.utcnow() + timedelta(days=1),
            datetime.utcnow() + timedelta(days=2)
        ]
        
        scheduled_content = []
        for i, scheduled_time in enumerate(scheduled_times):
            content = Content(
                model_id=model.id,
                type=ContentType.PHOTO,
                title=f"Scheduled Photo {i+1}",
                status=ContentStatus.SCHEDULED,
                scheduled_for=scheduled_time,
                media_urls=[f"https://cdn.example.com/scheduled{i+1}.jpg"]
            )
            scheduled_content.append(content)
            db_session.add(content)
        
        await db_session.commit()
        
        # Get upcoming scheduled content
        upcoming = await Content.get_scheduled_queue(
            db_session,
            model_id=model.id,
            hours_ahead=24
        )
        assert len(upcoming) == 4  # First 4 are within 24 hours
        
        # Check scheduling conflicts
        conflict_time = scheduled_times[0]
        has_conflict = await Content.check_schedule_conflict(
            db_session,
            model_id=model.id,
            scheduled_time=conflict_time,
            buffer_minutes=30
        )
        assert has_conflict is True
        
        # Auto-schedule content
        new_content = Content(
            model_id=model.id,
            type=ContentType.PHOTO,
            title="Auto-scheduled Photo",
            media_urls=["https://cdn.example.com/auto.jpg"]
        )
        
        best_time = await Content.find_best_schedule_time(
            db_session,
            model_id=model.id,
            preferred_hours=[14, 20],  # 2 PM or 8 PM
            avoid_conflicts=True
        )
        new_content.scheduled_for = best_time
        new_content.status = ContentStatus.SCHEDULED
        
        db_session.add(new_content)
        await db_session.commit()
        
        assert new_content.scheduled_for is not None
    
    @pytest.mark.asyncio
    async def test_content_moderation_workflow(self, db_session: AsyncSession):
        """Test content moderation and compliance workflow."""
        model = await create_test_model()
        
        # Create content that needs moderation
        content = Content(
            model_id=model.id,
            type=ContentType.VIDEO,
            title="New Video Content",
            status=ContentStatus.PENDING_REVIEW,
            media_urls=["https://cdn.example.com/review.mp4"],
            metadata={
                "duration_seconds": 600,
                "contains_nudity": True,
                "explicit_level": "high"
            }
        )
        db_session.add(content)
        await db_session.commit()
        
        # Perform automated checks
        auto_check_result = await content.run_automated_checks()
        assert "compliance_score" in auto_check_result
        assert "flags" in auto_check_result
        
        # Manual review process
        content.start_review(reviewer_id="mod123")
        assert content.review_started_at is not None
        assert content.reviewer_id == "mod123"
        
        # Add review notes
        content.add_review_note(
            "Content complies with platform guidelines",
            reviewer_id="mod123"
        )
        
        # Require changes
        content.require_changes(
            changes_required=["Add age restriction warning", "Blur faces in background"],
            reviewer_id="mod123"
        )
        assert content.status == ContentStatus.REQUIRES_CHANGES
        assert len(content.changes_required) == 2
        
        # Resubmit after changes
        content.resubmit_after_changes(
            changes_made=["Added 18+ warning", "Blurred all faces"]
        )
        assert content.status == ContentStatus.PENDING_REVIEW
        assert content.revision_count == 1
        
        # Final approval
        content.approve_content(
            approved_by="mod123",
            compliance_notes="All requirements met"
        )
        assert content.status == ContentStatus.APPROVED
        assert content.approved_at is not None
    
    @pytest.mark.asyncio
    async def test_content_cross_platform_sync(self, db_session: AsyncSession):
        """Test content synchronization across platforms."""
        model = await create_test_model()
        
        # Create content for multiple platforms
        content = Content(
            model_id=model.id,
            type=ContentType.PHOTO_SET,
            title="Multi-platform Release",
            platform=Platform.ONLYFANS,  # Primary platform
            media_urls=[
                "https://cdn.example.com/multi1.jpg",
                "https://cdn.example.com/multi2.jpg"
            ],
            cross_post_platforms=[Platform.FANSLY, Platform.INSTAGRAM],
            platform_specific_data={
                Platform.ONLYFANS: {
                    "post_id": "of_123",
                    "url": "https://onlyfans.com/post/123"
                },
                Platform.FANSLY: {
                    "post_id": "fs_456",
                    "url": "https://fansly.com/post/456",
                    "scheduled_for": datetime.utcnow() + timedelta(minutes=30)
                },
                Platform.INSTAGRAM: {
                    "scheduled_for": datetime.utcnow() + timedelta(hours=2),
                    "hashtags": ["#model", "#exclusive"]
                }
            }
        )
        db_session.add(content)
        await db_session.commit()
        
        # Update sync status
        await content.update_platform_sync_status(
            platform=Platform.FANSLY,
            status="published",
            post_id="fs_456",
            url="https://fansly.com/post/456"
        )
        
        # Check sync status
        sync_status = content.get_platform_sync_status()
        assert sync_status[Platform.ONLYFANS]["status"] == "published"
        assert sync_status[Platform.FANSLY]["status"] == "published"
        assert sync_status[Platform.INSTAGRAM]["status"] == "scheduled"
        
        # Handle sync errors
        await content.record_sync_error(
            platform=Platform.INSTAGRAM,
            error="API rate limit exceeded",
            retry_after=datetime.utcnow() + timedelta(minutes=15)
        )
        
        assert content.platform_sync_errors[Platform.INSTAGRAM] is not None
    
    @pytest.mark.asyncio
    async def test_content_analytics_reporting(self, db_session: AsyncSession):
        """Test content analytics and reporting features."""
        model = await create_test_model()
        
        # Create content with performance data
        content_items = []
        for i in range(5):
            content = Content(
                model_id=model.id,
                type=ContentType.PHOTO if i % 2 == 0 else ContentType.VIDEO,
                title=f"Content {i+1}",
                status=ContentStatus.PUBLISHED,
                published_at=datetime.utcnow() - timedelta(days=30-i*5),
                media_urls=[f"https://cdn.example.com/content{i+1}.jpg"]
            )
            content_items.append(content)
            db_session.add(content)
        
        await db_session.commit()
        
        # Add metrics
        for i, content in enumerate(content_items):
            metrics = ContentMetrics(
                content_id=content.id,
                views=1000 * (i + 1),
                likes=100 * (i + 1),
                revenue=Decimal(str(50 * (i + 1)))
            )
            db_session.add(metrics)
        
        await db_session.commit()
        
        # Generate performance report
        report = await Content.generate_performance_report(
            db_session,
            model_id=model.id,
            start_date=datetime.utcnow() - timedelta(days=31),
            end_date=datetime.utcnow()
        )
        
        assert report["total_content"] == 5
        assert report["total_views"] == 15000  # 1000 + 2000 + 3000 + 4000 + 5000
        assert report["total_revenue"] == Decimal("750")  # 50 + 100 + 150 + 200 + 250
        assert report["average_views_per_content"] == 3000
        assert report["best_performing_content"] is not None
        assert report["content_by_type"][ContentType.PHOTO] == 3
        assert report["content_by_type"][ContentType.VIDEO] == 2