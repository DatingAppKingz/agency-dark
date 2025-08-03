"""
Unit tests for OnlyFans sync service.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from modules.onlyfans_wrapper.application.sync_service import OnlyFansSyncService
from modules.onlyfans_wrapper.domain.schemas import (
    OnlyFansFan,
    OnlyFansTransaction,
    OnlyFansPost,
    OnlyFansMessage,
    OnlyFansStatistics,
    OnlyFansProfile,
    OnlyFansMedia
)
from models.financial import TransactionType, TransactionStatus
from modules.financial.domain.models import FinancialTransaction, BillingCycle
from core.domain.models import ModelProfile, Fan, Subscription, Content


class TestOnlyFansSyncService:
    
    @pytest.fixture
    def model_profile(self):
        """Create test model profile."""
        return ModelProfile(
            id=uuid4(),
            agency_id=uuid4(),
            onlyfans_username="testmodel",
            onlyfans_user_id="of_123",
            onlyfans_api_key="test_api_key",
            subscriber_count=0,
            paying_subscriber_count=0,
            total_earnings=Decimal("0")
        )
    
    @pytest.fixture
    def of_service_mock(self):
        """Create mock OnlyFans service."""
        mock = MagicMock()
        mock.get_client = AsyncMock()
        mock.sync_profile = AsyncMock()
        mock.sync_fans = AsyncMock(return_value=10)
        mock.get_transactions = AsyncMock(return_value=[])
        mock.get_messages = AsyncMock(return_value=[])
        mock.get_statistics = AsyncMock()
        return mock
    
    @pytest.mark.asyncio
    async def test_sync_all_data(self, db_session: AsyncSession, model_profile):
        """Test syncing all data from OnlyFans."""
        sync_service = OnlyFansSyncService(db_session)
        
        # Mock dependencies
        sync_service.sync_profile = AsyncMock()
        sync_service.sync_fans = AsyncMock(return_value=10)
        sync_service.sync_transactions = AsyncMock(return_value=20)
        sync_service.sync_posts = AsyncMock(return_value=5)
        sync_service.sync_recent_messages = AsyncMock(return_value=15)
        sync_service.update_statistics = AsyncMock()
        
        # Add model to db
        db_session.add(model_profile)
        await db_session.commit()
        
        # Sync all data
        results = await sync_service.sync_all_data(
            model_profile,
            sync_messages=True
        )
        
        assert results['profile'] == 1
        assert results['fans'] == 10
        assert results['transactions'] == 20
        assert results['posts'] == 5
        assert results['messages'] == 15
        
        # Verify methods were called
        sync_service.sync_profile.assert_called_once()
        sync_service.sync_fans.assert_called_once()
        sync_service.sync_transactions.assert_called_once()
        sync_service.sync_posts.assert_called_once()
        sync_service.sync_recent_messages.assert_called_once()
        sync_service.update_statistics.assert_called_once()
        
        # Verify last sync was updated
        await db_session.refresh(model_profile)
        assert model_profile.last_sync_at is not None
    
    @pytest.mark.asyncio
    async def test_sync_fans_with_subscriptions(self, db_session: AsyncSession, model_profile):
        """Test syncing fans with subscription records."""
        sync_service = OnlyFansSyncService(db_session)
        
        # Mock OnlyFans service
        with patch.object(sync_service, 'of_service') as mock_of:
            mock_of.sync_fans = AsyncMock(return_value=2)
            mock_client = AsyncMock()
            mock_of.get_client = AsyncMock(return_value=mock_client)
            
            # Mock fan data
            fans = [
                OnlyFansFan(
                    id="fan_1",
                    username="subscriber1",
                    name="Subscriber One",
                    is_subscriber=True,
                    subscription_price=Decimal("10.00"),
                    subscribed_at=datetime.utcnow() - timedelta(days=30),
                    renew_at=datetime.utcnow() + timedelta(days=30)
                ),
                OnlyFansFan(
                    id="fan_2",
                    username="subscriber2",
                    name="Subscriber Two",
                    is_subscriber=True,
                    subscription_price=Decimal("5.00"),
                    subscribed_at=datetime.utcnow() - timedelta(days=15),
                    expired_at=datetime.utcnow() - timedelta(days=1),
                    is_expired_subscriber=True
                )
            ]
            mock_client.get_fans = AsyncMock(return_value=fans)
            
            # Create fan records
            fan1 = Fan(
                id=uuid4(),
                model_id=model_profile.id,
                onlyfans_user_id="fan_1",
                username="subscriber1"
            )
            fan2 = Fan(
                id=uuid4(),
                model_id=model_profile.id,
                onlyfans_user_id="fan_2",
                username="subscriber2"
            )
            db_session.add(fan1)
            db_session.add(fan2)
            db_session.add(model_profile)
            await db_session.commit()
            
            # Sync fans
            count = await sync_service.sync_fans(model_profile)
            
            assert count == 2
            
            # Verify subscriptions were created
            from sqlalchemy import select
            result = await db_session.execute(
                select(Subscription).where(
                    Subscription.model_id == model_profile.id
                )
            )
            subscriptions = result.scalars().all()
            assert len(subscriptions) == 2
    
    @pytest.mark.asyncio
    async def test_sync_transactions(self, db_session: AsyncSession, model_profile):
        """Test syncing financial transactions."""
        sync_service = OnlyFansSyncService(db_session)
        
        # Create billing cycle
        cycle = BillingCycle(
            id=uuid4(),
            model_id=model_profile.id,
            start_date=datetime.utcnow().replace(day=1),
            end_date=datetime.utcnow(),
            cycle_number=f"{datetime.utcnow().year}-{datetime.utcnow().month:02d}"
        )
        db_session.add(cycle)
        db_session.add(model_profile)
        await db_session.commit()
        
        # Mock get_or_create_billing_cycle
        sync_service._get_or_create_billing_cycle = AsyncMock(return_value=cycle)
        
        # Mock OnlyFans service
        with patch.object(sync_service, 'of_service') as mock_of:
            # Mock transaction data
            of_user = OnlyFansFan(id="user_1", username="fan1")
            transactions = [
                OnlyFansTransaction(
                    id="tx_1",
                    type="subscription",
                    amount=Decimal("50.00"),
                    currency="USD",
                    from_user=of_user,
                    description="Subscription payment",
                    created_at=datetime.utcnow()
                ),
                OnlyFansTransaction(
                    id="tx_2",
                    type="tip",
                    amount=Decimal("20.00"),
                    currency="USD",
                    from_user=of_user,
                    description="Tip",
                    created_at=datetime.utcnow()
                )
            ]
            mock_of.get_transactions = AsyncMock(return_value=transactions)
            
            # Mock analytics sync
            sync_service.analytics_sync.sync_revenue_transactions = AsyncMock()
            
            # Sync transactions
            count = await sync_service.sync_transactions(
                model_profile,
                datetime.utcnow() - timedelta(days=7),
                datetime.utcnow()
            )
            
            assert count == 2
            
            # Verify transactions were created
            from sqlalchemy import select
            result = await db_session.execute(
                select(FinancialTransaction).where(
                    FinancialTransaction.model_id == model_profile.id
                )
            )
            created_txs = result.scalars().all()
            assert len(created_txs) == 2
    
    @pytest.mark.asyncio
    async def test_sync_posts_as_content(self, db_session: AsyncSession, model_profile):
        """Test syncing posts as content records."""
        sync_service = OnlyFansSyncService(db_session)
        
        db_session.add(model_profile)
        await db_session.commit()
        
        # Mock OnlyFans client
        with patch.object(sync_service, 'of_service') as mock_of:
            mock_client = AsyncMock()
            mock_of.get_client = AsyncMock(return_value=mock_client)
            
            # Mock post data
            posts = [
                OnlyFansPost(
                    id="post_1",
                    text="Check out this exclusive content!",
                    media=[
                        OnlyFansMedia(
                            id="media_1",
                            type="photo",
                            preview="https://example.com/preview1.jpg"
                        )
                    ],
                    price=Decimal("15.00"),
                    is_paid=True,
                    posted_at=datetime.utcnow(),
                    likes_count=50,
                    comments_count=10
                ),
                OnlyFansPost(
                    id="post_2",
                    text="Free post for my fans",
                    media=[],
                    is_paid=False,
                    posted_at=datetime.utcnow() - timedelta(days=1),
                    likes_count=100,
                    comments_count=20
                )
            ]
            mock_client.get_posts = AsyncMock(return_value=posts)
            
            # Sync posts
            count = await sync_service.sync_posts(model_profile)
            
            assert count == 2
            
            # Verify content was created
            from sqlalchemy import select
            result = await db_session.execute(
                select(Content).where(
                    Content.model_id == model_profile.id
                )
            )
            content_items = result.scalars().all()
            assert len(content_items) == 2
            
            # Check PPV content
            ppv_content = next(c for c in content_items if c.platform_content_id == "post_1")
            assert ppv_content.price == Decimal("15.00")
            assert ppv_content.is_ppv is True
            assert ppv_content.content_type == "photo"
    
    @pytest.mark.asyncio
    async def test_sync_ppv_messages(self, db_session: AsyncSession, model_profile):
        """Test syncing PPV messages as transactions."""
        sync_service = OnlyFansSyncService(db_session)
        
        # Create billing cycle
        cycle = BillingCycle(
            id=uuid4(),
            model_id=model_profile.id,
            start_date=datetime.utcnow().replace(day=1),
            end_date=datetime.utcnow(),
            cycle_number=f"{datetime.utcnow().year}-{datetime.utcnow().month:02d}"
        )
        db_session.add(cycle)
        db_session.add(model_profile)
        await db_session.commit()
        
        # Mock dependencies
        sync_service._get_or_create_billing_cycle = AsyncMock(return_value=cycle)
        sync_service._create_financial_transaction = AsyncMock()
        
        with patch.object(sync_service, 'of_service') as mock_of:
            # Mock PPV messages
            from_user = MagicMock()
            from_user.id = "user_1"
            from_user.username = "fan1"
            
            messages = [
                OnlyFansMessage(
                    id="msg_1",
                    from_user=from_user,
                    text="Unlock this exclusive content!",
                    is_paid=True,
                    price=Decimal("25.00"),
                    created_at=datetime.utcnow()
                ),
                OnlyFansMessage(
                    id="msg_2",
                    from_user=from_user,
                    text="Regular message",
                    is_paid=False,
                    created_at=datetime.utcnow()
                )
            ]
            mock_of.get_messages = AsyncMock(return_value=messages)
            
            # Sync messages
            count = await sync_service.sync_recent_messages(
                model_profile,
                since=datetime.utcnow() - timedelta(hours=1)
            )
            
            assert count == 2
            
            # Verify PPV transaction was created
            sync_service._create_financial_transaction.assert_called_once()
            call_args = sync_service._create_financial_transaction.call_args
            assert call_args[0][1].type == "ppv_message"
            assert call_args[0][1].amount == Decimal("25.00")
    
    @pytest.mark.asyncio
    async def test_update_statistics(self, db_session: AsyncSession, model_profile):
        """Test updating statistics from OnlyFans."""
        sync_service = OnlyFansSyncService(db_session)
        
        db_session.add(model_profile)
        await db_session.commit()
        
        # Mock statistics
        with patch.object(sync_service, 'of_service') as mock_of:
            stats = OnlyFansStatistics(
                period_start=datetime.utcnow() - timedelta(days=30),
                period_end=datetime.utcnow(),
                total_earnings=Decimal("5000.00"),
                subscribers_count=150,
                new_subscribers=20,
                expired_subscribers=5,
                tips_sum=Decimal("500.00"),
                ppv_sum=Decimal("1000.00"),
                messages_sum=Decimal("200.00")
            )
            mock_of.get_statistics = AsyncMock(return_value=stats)
            
            # Update statistics
            await sync_service.update_statistics(
                model_profile,
                datetime.utcnow() - timedelta(days=30),
                datetime.utcnow()
            )
            
            # Verify earnings were updated
            await db_session.refresh(model_profile)
            assert model_profile.total_earnings == Decimal("5000.00")
    
    @pytest.mark.asyncio
    async def test_sync_error_handling(self, db_session: AsyncSession, model_profile):
        """Test error handling during sync."""
        sync_service = OnlyFansSyncService(db_session)
        
        # Mock a failure
        sync_service.sync_profile = AsyncMock(side_effect=Exception("API Error"))
        
        db_session.add(model_profile)
        await db_session.commit()
        
        # Sync should raise error
        with pytest.raises(Exception) as exc:
            await sync_service.sync_all_data(model_profile)
        
        assert "API Error" in str(exc.value)
        
        # Verify rollback (last_sync_at should not be updated)
        await db_session.refresh(model_profile)
        assert model_profile.last_sync_at is None