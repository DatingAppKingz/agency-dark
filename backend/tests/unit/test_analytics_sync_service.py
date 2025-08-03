"""
Unit tests for Analytics Data Sync Service.
"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from modules.analytics.application.data_sync_service import AnalyticsDataSyncService
from models.analytics import MetricSnapshot
from modules.analytics.domain.models import RevenueTransaction, ContentPerformance, FanSpendingHistory, CategoryPerformance
from models.financial import TransactionType, TransactionStatus
from modules.financial.domain.models import FinancialTransaction
from core.domain.models import ModelProfile, Fan, Subscription, Content, ContentCategory


class TestAnalyticsDataSyncService:
    
    @pytest.mark.asyncio
    async def test_sync_revenue_transactions(self, db_session: AsyncSession):
        """Test syncing financial transactions to revenue transactions."""
        # Create test data
        model_id = uuid4()
        model = ModelProfile(
            id=model_id,
            user_id=uuid4(),
            agency_id=uuid4(),
            username="testmodel"
        )
        db_session.add(model)
        
        # Create financial transactions
        transactions = []
        for i in range(5):
            tx = FinancialTransaction(
                id=uuid4(),
                model_id=model_id,
                amount=Decimal("100.00"),
                currency="USD",
                type=TransactionType.REVENUE,
                status=TransactionStatus.COMPLETED,
                transaction_date=datetime.utcnow() - timedelta(days=i),
                description=f"Subscription payment {i}",
                metadata={"type": "subscription", "fan_id": str(uuid4())}
            )
            transactions.append(tx)
            db_session.add(tx)
        
        await db_session.commit()
        
        # Sync transactions
        service = AnalyticsDataSyncService(db_session)
        await service.sync_revenue_transactions(str(model_id))
        
        # Verify revenue transactions were created
        result = await db_session.execute(
            select(RevenueTransaction).where(
                RevenueTransaction.model_id == str(model_id)
            )
        )
        revenue_txs = result.scalars().all()
        
        assert len(revenue_txs) == 5
        for rev_tx in revenue_txs:
            assert rev_tx.amount == Decimal("100.00")
            assert rev_tx.transaction_type == "subscription"
            assert rev_tx.platform == "onlyfans"
    
    @pytest.mark.asyncio
    async def test_sync_revenue_transactions_with_start_date(self, db_session: AsyncSession):
        """Test syncing transactions after a specific date."""
        model_id = uuid4()
        model = ModelProfile(id=model_id, user_id=uuid4(), username="testmodel")
        db_session.add(model)
        
        # Create transactions before and after cutoff
        cutoff_date = datetime.utcnow() - timedelta(days=3)
        
        # Old transaction
        old_tx = FinancialTransaction(
            id=uuid4(),
            model_id=model_id,
            amount=Decimal("50.00"),
            type=TransactionType.REVENUE,
            status=TransactionStatus.COMPLETED,
            transaction_date=cutoff_date - timedelta(days=2)
        )
        db_session.add(old_tx)
        
        # New transaction
        new_tx = FinancialTransaction(
            id=uuid4(),
            model_id=model_id,
            amount=Decimal("75.00"),
            type=TransactionType.REVENUE,
            status=TransactionStatus.COMPLETED,
            transaction_date=cutoff_date + timedelta(days=1)
        )
        db_session.add(new_tx)
        
        await db_session.commit()
        
        # Sync with start date
        service = AnalyticsDataSyncService(db_session)
        await service.sync_revenue_transactions(
            str(model_id),
            start_date=cutoff_date
        )
        
        # Verify only new transaction was synced
        result = await db_session.execute(
            select(RevenueTransaction).where(
                RevenueTransaction.model_id == str(model_id)
            )
        )
        revenue_txs = result.scalars().all()
        
        assert len(revenue_txs) == 1
        assert revenue_txs[0].amount == Decimal("75.00")
    
    @pytest.mark.asyncio
    async def test_create_daily_snapshot(self, db_session: AsyncSession):
        """Test creating daily metric snapshots."""
        model_id = uuid4()
        model = ModelProfile(id=model_id, user_id=uuid4(), username="testmodel")
        db_session.add(model)
        
        # Create test subscriptions
        for i in range(10):
            sub = Subscription(
                id=uuid4(),
                model_id=model_id,
                fan_id=uuid4(),
                is_active=i < 7,  # 7 active
                price=Decimal("10.00") if i < 5 else Decimal("0"),  # 5 paying
                created_at=datetime.utcnow() - timedelta(days=30)
            )
            db_session.add(sub)
        
        # Create revenue transactions for today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0)
        for i in range(3):
            rev_tx = RevenueTransaction(
                id=uuid4(),
                model_id=str(model_id),
                fan_id=str(uuid4()),
                transaction_id=f"tx_{i}",
                transaction_type="subscription",
                amount=Decimal("25.00"),
                currency="USD",
                transaction_date=today + timedelta(hours=i),
                platform="onlyfans"
            )
            db_session.add(rev_tx)
        
        await db_session.commit()
        
        # Create snapshot
        service = AnalyticsDataSyncService(db_session)
        await service._create_daily_snapshot(str(model_id), today)
        
        # Verify snapshot
        result = await db_session.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.model_id == str(model_id)
            )
        )
        snapshot = result.scalar_one()
        
        assert snapshot.total_subscribers == 10
        assert snapshot.paying_subscribers == 5
        assert snapshot.non_paying_fans == 2  # 7 active - 5 paying
        assert snapshot.total_revenue == Decimal("75.00")  # 3 * 25
        assert snapshot.conversion_rate == 50.0  # 5/10 * 100
    
    @pytest.mark.asyncio
    async def test_update_fan_spending_history(self, db_session: AsyncSession):
        """Test updating fan spending history."""
        model_id = uuid4()
        fan_id = str(uuid4())
        
        model = ModelProfile(id=model_id, user_id=uuid4(), username="testmodel")
        db_session.add(model)
        
        # Create revenue transactions
        for i in range(5):
            rev_tx = RevenueTransaction(
                id=uuid4(),
                model_id=str(model_id),
                fan_id=fan_id,
                transaction_id=f"tx_{i}",
                transaction_type="tip",
                amount=Decimal("20.00"),
                currency="USD",
                transaction_date=datetime.utcnow() - timedelta(days=i),
                platform="onlyfans"
            )
            db_session.add(rev_tx)
        
        await db_session.commit()
        
        # Update spending history
        service = AnalyticsDataSyncService(db_session)
        await service.update_fan_spending_history(str(model_id), lookback_days=7)
        
        # Verify history
        result = await db_session.execute(
            select(FanSpendingHistory).where(
                FanSpendingHistory.model_id == str(model_id)
            )
        )
        history = result.scalar_one()
        
        assert history.fan_id == fan_id
        assert history.total_spent == Decimal("100.00")  # 5 * 20
        assert history.transaction_count == 5
        assert history.avg_transaction_value == Decimal("20.00")
    
    @pytest.mark.asyncio
    async def test_sync_content_performance(self, db_session: AsyncSession):
        """Test syncing content performance data."""
        model_id = uuid4()
        model = ModelProfile(id=model_id, user_id=uuid4(), username="testmodel")
        db_session.add(model)
        
        # Create content with metadata
        content = Content(
            id=uuid4(),
            model_id=model_id,
            content_type="video",
            title="Test Video",
            created_at=datetime.utcnow() - timedelta(days=7),
            metadata={
                "views": 1000,
                "likes": 150,
                "comments": 25,
                "price": 15.00
            }
        )
        db_session.add(content)
        
        await db_session.commit()
        
        # Sync content performance
        service = AnalyticsDataSyncService(db_session)
        await service.sync_content_performance(str(model_id))
        
        # Verify performance record
        result = await db_session.execute(
            select(ContentPerformance).where(
                ContentPerformance.model_id == str(model_id)
            )
        )
        performance = result.scalar_one()
        
        assert performance.content_id == str(content.id)
        assert performance.views == 1000
        assert performance.likes == 150
        assert performance.comments == 25
        assert performance.total_revenue == Decimal("1500.00")  # 15 * 1000 * 0.1
    
    @pytest.mark.asyncio
    async def test_update_category_performance(self, db_session: AsyncSession):
        """Test updating category performance metrics."""
        model_id = uuid4()
        model = ModelProfile(id=model_id, user_id=uuid4(), username="testmodel")
        db_session.add(model)
        
        # Create categories
        cat1 = ContentCategory(id=uuid4(), name="Photos", slug="photos")
        cat2 = ContentCategory(id=uuid4(), name="Videos", slug="videos")
        db_session.add(cat1)
        db_session.add(cat2)
        
        # Create content with performance
        for i in range(3):
            content = Content(
                id=uuid4(),
                model_id=model_id,
                category_id=cat1.id if i < 2 else cat2.id,
                content_type="photo" if i < 2 else "video",
                created_at=datetime.utcnow() - timedelta(days=i)
            )
            db_session.add(content)
            
            perf = ContentPerformance(
                id=uuid4(),
                model_id=str(model_id),
                content_id=str(content.id),
                content_type=content.content_type,
                title=f"Content {i}",
                published_at=content.created_at,
                views=100 * (i + 1),
                likes=10 * (i + 1),
                comments=5 * (i + 1),
                total_revenue=Decimal(str(50 * (i + 1)))
            )
            db_session.add(perf)
        
        await db_session.commit()
        
        # Update category performance
        service = AnalyticsDataSyncService(db_session)
        await service.update_category_performance(str(model_id))
        
        # Verify performance records
        result = await db_session.execute(
            select(CategoryPerformance).where(
                CategoryPerformance.model_id == str(model_id)
            ).order_by(CategoryPerformance.category_name)
        )
        performances = result.scalars().all()
        
        assert len(performances) == 2
        
        # Check Photos category
        photos_perf = performances[0]
        assert photos_perf.category_name == "Photos"
        assert photos_perf.content_count == 2
        assert photos_perf.total_views == 300  # 100 + 200
        assert photos_perf.total_revenue == Decimal("150")  # 50 + 100
        
        # Check Videos category
        videos_perf = performances[1]
        assert videos_perf.category_name == "Videos"
        assert videos_perf.content_count == 1
        assert videos_perf.total_views == 300
        assert videos_perf.total_revenue == Decimal("150")
    
    @pytest.mark.asyncio
    async def test_sync_all_model_data(self, db_session: AsyncSession):
        """Test full model data sync."""
        model_id = uuid4()
        model = ModelProfile(id=model_id, user_id=uuid4(), username="testmodel")
        db_session.add(model)
        
        # Create some test data
        tx = FinancialTransaction(
            id=uuid4(),
            model_id=model_id,
            amount=Decimal("100.00"),
            type=TransactionType.REVENUE,
            status=TransactionStatus.COMPLETED,
            transaction_date=datetime.utcnow()
        )
        db_session.add(tx)
        
        await db_session.commit()
        
        # Mock the individual sync methods
        service = AnalyticsDataSyncService(db_session)
        service.sync_revenue_transactions = AsyncMock()
        service.update_metric_snapshots = AsyncMock()
        service.sync_content_performance = AsyncMock()
        service.update_fan_spending_history = AsyncMock()
        service.update_category_performance = AsyncMock()
        
        # Run full sync
        await service.sync_all_model_data(str(model_id))
        
        # Verify all methods were called
        service.sync_revenue_transactions.assert_called_once_with(str(model_id), False)
        service.update_metric_snapshots.assert_called_once_with(str(model_id))
        service.sync_content_performance.assert_called_once_with(str(model_id), False)
        service.update_fan_spending_history.assert_called_once_with(str(model_id))
        service.update_category_performance.assert_called_once_with(str(model_id))