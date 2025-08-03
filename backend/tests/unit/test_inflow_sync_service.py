"""
Unit tests for Inflow sync service.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from modules.inflow_wrapper.application.sync_service import InflowSyncService
from modules.inflow_wrapper.domain.schemas import (
    InflowUser,
    InflowSubscription,
    InflowTransaction,
    InflowContent,
    InflowMessage,
    InflowAnalytics
)
from models.financial import TransactionType, TransactionStatus
from modules.financial.domain.models import FinancialTransaction, BillingCycle
from core.domain.models import ModelProfile, Fan, Subscription, Content


class TestInflowSyncService:
    
    @pytest.fixture
    def model_profile(self):
        """Create test model profile."""
        return ModelProfile(
            id=uuid4(),
            agency_id=uuid4(),
            onlyfans_username="testmodel",
            onlyfans_user_id="of_123",
            inflow_api_key="test_api_key",
            subscriber_count=0,
            paying_subscriber_count=0
        )
    
    @pytest.fixture
    def inflow_service_mock(self):
        """Create mock Inflow service."""
        mock = MagicMock()
        mock.get_client = AsyncMock()
        mock.sync_subscribers = AsyncMock(return_value=10)
        mock.list_content = AsyncMock(return_value=[])
        mock.sync_messages = AsyncMock(return_value=5)
        mock.get_analytics = AsyncMock()
        return mock
    
    @pytest.mark.asyncio
    async def test_sync_all_data(self, db_session: AsyncSession, model_profile):
        """Test syncing all data from Inflow."""
        sync_service = InflowSyncService(db_session)
        
        # Mock dependencies
        sync_service.sync_subscribers = AsyncMock(return_value=10)
        sync_service.sync_content = AsyncMock(return_value=5)
        sync_service.sync_transactions = AsyncMock(return_value=20)
        sync_service.sync_messages = AsyncMock(return_value=15)
        sync_service.update_analytics = AsyncMock()
        
        # Add model to db
        db_session.add(model_profile)
        await db_session.commit()
        
        # Sync all data
        results = await sync_service.sync_all_data(model_profile)
        
        assert results['subscribers'] == 10
        assert results['content'] == 5
        assert results['transactions'] == 20
        assert results['messages'] == 15
        
        # Verify methods were called
        sync_service.sync_subscribers.assert_called_once()
        sync_service.sync_content.assert_called_once()
        sync_service.sync_transactions.assert_called_once()
        sync_service.sync_messages.assert_called_once()
        sync_service.update_analytics.assert_called_once()
        
        # Verify last sync was updated
        await db_session.refresh(model_profile)
        assert model_profile.last_sync_at is not None
    
    @pytest.mark.asyncio
    async def test_sync_subscribers(self, db_session: AsyncSession, model_profile):
        """Test syncing subscribers from Inflow."""
        sync_service = InflowSyncService(db_session)
        
        # Mock Inflow service
        with patch.object(sync_service, 'inflow_service') as mock_inflow:
            mock_inflow.sync_subscribers = AsyncMock(return_value=5)
            mock_client = AsyncMock()
            mock_inflow.get_client = AsyncMock(return_value=mock_client)
            
            # Mock subscriber data
            subscribers = [
                InflowSubscription(
                    id="sub_1",
                    subscriber_id="user_1",
                    creator_id="of_123",
                    price=10.0,
                    is_active=True,
                    started_at=datetime.utcnow(),
                    auto_renew=True
                ),
                InflowSubscription(
                    id="sub_2",
                    subscriber_id="user_2",
                    creator_id="of_123",
                    price=0.0,
                    is_active=True,
                    started_at=datetime.utcnow(),
                    auto_renew=False
                )
            ]
            mock_client.list_subscribers = AsyncMock(return_value=subscribers)
            
            # Mock user info
            mock_client.get_user = AsyncMock(side_effect=[
                InflowUser(
                    id="user_1",
                    username="fan1",
                    display_name="Fan One",
                    created_at=datetime.utcnow()
                ),
                InflowUser(
                    id="user_2",
                    username="fan2",
                    display_name="Fan Two",
                    created_at=datetime.utcnow()
                )
            ])
            
            # Add model to db
            db_session.add(model_profile)
            await db_session.commit()
            
            # Sync subscribers
            count = await sync_service.sync_subscribers(model_profile)
            
            assert count == 5  # From mock
            mock_inflow.sync_subscribers.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sync_transactions(self, db_session: AsyncSession, model_profile):
        """Test syncing financial transactions."""
        sync_service = InflowSyncService(db_session)
        
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
        
        # Mock Inflow client
        with patch.object(sync_service, 'inflow_service') as mock_inflow:
            mock_client = AsyncMock()
            mock_inflow.get_client = AsyncMock(return_value=mock_client)
            
            # Mock transaction data
            transactions = [
                InflowTransaction(
                    id="tx_1",
                    type="subscription",
                    amount=50.0,
                    currency="USD",
                    from_user_id="user_1",
                    to_user_id="of_123",
                    status="completed",
                    created_at=datetime.utcnow()
                ),
                InflowTransaction(
                    id="tx_2",
                    type="tip",
                    amount=20.0,
                    currency="USD",
                    from_user_id="user_2",
                    to_user_id="of_123",
                    status="completed",
                    created_at=datetime.utcnow()
                )
            ]
            mock_client.list_transactions = AsyncMock(return_value=transactions)
            
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
    async def test_sync_messages_with_ppv(self, db_session: AsyncSession, model_profile):
        """Test syncing messages including PPV transactions."""
        sync_service = InflowSyncService(db_session)
        
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
        
        with patch.object(sync_service, 'inflow_service') as mock_inflow:
            mock_inflow.sync_messages = AsyncMock(return_value=10)
            mock_client = AsyncMock()
            mock_inflow.get_client = AsyncMock(return_value=mock_client)
            
            # Mock PPV messages
            messages = [
                InflowMessage(
                    id="msg_1",
                    conversation_id="conv_1",
                    sender_id="of_123",
                    recipient_id="user_1",
                    content="Check out this exclusive content!",
                    is_ppv=True,
                    price=25.0,
                    created_at=datetime.utcnow()
                ),
                InflowMessage(
                    id="msg_2",
                    conversation_id="conv_2",
                    sender_id="of_123",
                    recipient_id="user_2",
                    content="Regular message",
                    is_ppv=False,
                    created_at=datetime.utcnow()
                )
            ]
            mock_client.list_messages = AsyncMock(return_value=messages)
            
            # Sync messages
            count = await sync_service.sync_messages(
                model_profile,
                datetime.utcnow() - timedelta(hours=1)
            )
            
            assert count == 10  # From mock
            
            # Verify PPV transaction was created
            sync_service._create_financial_transaction.assert_called_once()
            call_args = sync_service._create_financial_transaction.call_args
            assert call_args[0][1].type == "ppv_message"
            assert call_args[0][1].amount == 25.0
    
    @pytest.mark.asyncio
    async def test_create_or_update_content(self, db_session: AsyncSession, model_profile):
        """Test creating or updating content records."""
        sync_service = InflowSyncService(db_session)
        
        db_session.add(model_profile)
        await db_session.commit()
        
        # Create Inflow content
        inflow_content = InflowContent(
            id="content_1",
            creator_id="of_123",
            title="Exclusive Photo Set",
            description="Behind the scenes photos",
            content_type="image",
            url="https://example.com/content/1",
            thumbnail_url="https://example.com/thumb/1",
            price=15.0,
            is_ppv=True,
            is_locked=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Create content
        await sync_service._create_or_update_content(model_profile, inflow_content)
        await db_session.commit()
        
        # Verify content was created
        from sqlalchemy import select
        result = await db_session.execute(
            select(Content).where(
                Content.model_id == model_profile.id
            )
        )
        content = result.scalar_one()
        
        assert content.platform_content_id == "content_1"
        assert content.title == "Exclusive Photo Set"
        assert content.price == Decimal("15.0")
        assert content.is_ppv is True
        
        # Update content
        inflow_content.title = "Updated Photo Set"
        inflow_content.price = 20.0
        
        await sync_service._create_or_update_content(model_profile, inflow_content)
        await db_session.commit()
        
        # Verify update
        await db_session.refresh(content)
        assert content.title == "Updated Photo Set"
        assert content.price == Decimal("20.0")
    
    @pytest.mark.asyncio
    async def test_sync_error_handling(self, db_session: AsyncSession, model_profile):
        """Test error handling during sync."""
        sync_service = InflowSyncService(db_session)
        
        # Mock a failure
        sync_service.sync_subscribers = AsyncMock(side_effect=Exception("API Error"))
        
        db_session.add(model_profile)
        await db_session.commit()
        
        # Sync should raise error
        with pytest.raises(Exception) as exc:
            await sync_service.sync_all_data(model_profile)
        
        assert "API Error" in str(exc.value)
        
        # Verify rollback (last_sync_at should not be updated)
        await db_session.refresh(model_profile)
        assert model_profile.last_sync_at is None