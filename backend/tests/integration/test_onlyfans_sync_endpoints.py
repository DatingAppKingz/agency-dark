"""
Integration tests for OnlyFans sync endpoints.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.models import ModelProfile, Fan, Content
from modules.financial.domain.models import FinancialTransaction, BillingCycle
from modules.analytics.domain.models import RevenueTransaction
from modules.onlyfans_wrapper.domain.schemas import (
    OnlyFansProfile,
    OnlyFansFan,
    OnlyFansTransaction,
    OnlyFansPost,
    OnlyFansStatistics,
    OnlyFansMedia
)


class TestOnlyFansSyncEndpoints:
    
    @pytest.mark.asyncio
    async def test_sync_all_data_success(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test successful full sync of OnlyFans data."""
        # Add API key to model
        test_model_profile.onlyfans_api_key = "test_api_key"
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Mock OnlyFans service
        with patch('modules.onlyfans_wrapper.application.sync_service.OnlyFansService') as mock_of:
            # Mock client
            mock_client = AsyncMock()
            mock_of.return_value.get_client = AsyncMock(return_value=mock_client)
            
            # Mock profile sync
            mock_profile = OnlyFansProfile(
                id="of_123",
                username="testmodel",
                name="Test Model",
                subscribers_count=100
            )
            mock_of.return_value.sync_profile = AsyncMock(return_value=mock_profile)
            
            # Mock fans sync
            mock_of.return_value.sync_fans = AsyncMock(return_value=5)
            mock_client.get_fans = AsyncMock(return_value=[
                OnlyFansFan(
                    id="fan_1",
                    username="subscriber1",
                    is_subscriber=True,
                    subscription_price=Decimal("10.00")
                )
            ])
            
            # Mock transactions
            mock_of.return_value.get_transactions = AsyncMock(return_value=[
                OnlyFansTransaction(
                    id="tx_1",
                    type="subscription",
                    amount=Decimal("50.00"),
                    currency="USD",
                    from_user=OnlyFansFan(id="fan_1", username="subscriber1"),
                    created_at=datetime.utcnow()
                )
            ])
            
            # Mock posts
            mock_client.get_posts = AsyncMock(return_value=[
                OnlyFansPost(
                    id="post_1",
                    text="Test post",
                    posted_at=datetime.utcnow(),
                    likes_count=10
                )
            ])
            
            # Mock messages
            mock_of.return_value.get_messages = AsyncMock(return_value=[])
            
            # Mock statistics
            mock_of.return_value.get_statistics = AsyncMock(return_value=OnlyFansStatistics(
                period_start=datetime.utcnow() - timedelta(days=30),
                period_end=datetime.utcnow(),
                total_earnings=Decimal("1000.00"),
                subscribers_count=100,
                new_subscribers=20,
                expired_subscribers=5,
                tips_sum=Decimal("100.00"),
                ppv_sum=Decimal("200.00"),
                messages_sum=Decimal("50.00")
            ))
            
            # Perform sync
            response = await authenticated_client.post(
                f"/api/v1/onlyfans/sync/{test_model_profile.id}/all",
                params={
                    "sync_messages": True,
                    "force": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["sync_results"]["profile"] == 1
            assert data["sync_results"]["fans"] == 5
            assert data["sync_results"]["transactions"] == 1
            assert data["sync_results"]["posts"] == 1
    
    @pytest.mark.asyncio
    async def test_sync_all_data_no_api_key(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test sync fails when no API key configured."""
        # Ensure no API key
        test_model_profile.onlyfans_api_key = None
        db_session.add(test_model_profile)
        await db_session.commit()
        
        response = await authenticated_client.post(
            f"/api/v1/onlyfans/sync/{test_model_profile.id}/all"
        )
        
        assert response.status_code == 400
        assert "API key not configured" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_sync_all_data_rate_limit(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test sync rate limiting."""
        # Add API key and recent sync
        test_model_profile.onlyfans_api_key = "test_api_key"
        test_model_profile.last_sync_at = datetime.utcnow() - timedelta(seconds=60)
        db_session.add(test_model_profile)
        await db_session.commit()
        
        response = await authenticated_client.post(
            f"/api/v1/onlyfans/sync/{test_model_profile.id}/all",
            params={"force": False}
        )
        
        assert response.status_code == 429
        assert "synced 60 seconds ago" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_sync_transactions_creates_financial_records(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test transaction sync creates proper financial records."""
        # Add API key
        test_model_profile.onlyfans_api_key = "test_api_key"
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Mock OnlyFans service
        with patch('modules.onlyfans_wrapper.application.sync_service.OnlyFansService') as mock_of:
            # Mock transactions
            of_fan = OnlyFansFan(id="fan_1", username="subscriber1")
            mock_transactions = [
                OnlyFansTransaction(
                    id="tx_1",
                    type="subscription",
                    amount=Decimal("50.00"),
                    currency="USD",
                    from_user=of_fan,
                    created_at=datetime.utcnow()
                ),
                OnlyFansTransaction(
                    id="tx_2",
                    type="tip",
                    amount=Decimal("20.00"),
                    currency="USD",
                    from_user=of_fan,
                    created_at=datetime.utcnow()
                )
            ]
            mock_of.return_value.get_transactions = AsyncMock(return_value=mock_transactions)
            
            # Mock analytics sync
            with patch('modules.onlyfans_wrapper.application.sync_service.AnalyticsDataSyncService') as mock_analytics:
                mock_analytics.return_value.sync_revenue_transactions = AsyncMock()
                
                # Perform transaction sync
                start_date = datetime.utcnow().date() - timedelta(days=7)
                end_date = datetime.utcnow().date()
                
                response = await authenticated_client.post(
                    f"/api/v1/onlyfans/sync/{test_model_profile.id}/transactions",
                    params={
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["synced_count"] == 2
                
                # Verify financial transactions were created
                from sqlalchemy import select
                result = await db_session.execute(
                    select(FinancialTransaction).where(
                        FinancialTransaction.model_id == test_model_profile.id
                    )
                )
                transactions = result.scalars().all()
                assert len(transactions) == 2
                
                # Verify transaction details
                tx1 = next(t for t in transactions if t.external_reference == "tx_1")
                assert tx1.amount == Decimal("50.00")
                assert tx1.type == "revenue"
                assert "subscription" in tx1.description.lower()
    
    @pytest.mark.asyncio
    async def test_sync_fans_with_subscriptions(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test fan sync creates subscription records."""
        # Add API key
        test_model_profile.onlyfans_api_key = "test_api_key"
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Mock OnlyFans service
        with patch('modules.onlyfans_wrapper.application.sync_service.OnlyFansService') as mock_of:
            # Mock client
            mock_client = AsyncMock()
            mock_of.return_value.get_client = AsyncMock(return_value=mock_client)
            
            # Mock fans data
            mock_fans = [
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
                    is_subscriber=False,
                    is_expired_subscriber=True,
                    subscription_price=Decimal("5.00"),
                    expired_at=datetime.utcnow() - timedelta(days=1)
                )
            ]
            
            # Mock sync_fans to return count
            mock_of.return_value.sync_fans = AsyncMock(return_value=2)
            
            # Mock get_fans for active subscribers
            mock_client.get_fans = AsyncMock(return_value=[mock_fans[0]])
            
            # Perform fan sync
            response = await authenticated_client.post(
                f"/api/v1/onlyfans/sync/{test_model_profile.id}/fans"
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["synced_fans"] == 2
    
    @pytest.mark.asyncio
    async def test_sync_status_endpoint(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test sync status endpoint."""
        # Add API key and sync info
        test_model_profile.onlyfans_api_key = "test_api_key"
        test_model_profile.last_sync_at = datetime.utcnow() - timedelta(minutes=30)
        test_model_profile.subscriber_count = 150
        test_model_profile.total_earnings = Decimal("5000.00")
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Mock statistics
        with patch('modules.onlyfans_wrapper.application.service.OnlyFansService') as mock_of:
            mock_stats = OnlyFansStatistics(
                period_start=datetime.utcnow() - timedelta(days=30),
                period_end=datetime.utcnow(),
                total_earnings=Decimal("5500.00"),
                subscribers_count=155,
                new_subscribers=25,
                expired_subscribers=20,
                tips_sum=Decimal("300.00"),
                ppv_sum=Decimal("800.00"),
                messages_sum=Decimal("150.00")
            )
            mock_of.return_value.get_statistics = AsyncMock(return_value=mock_stats)
            
            response = await authenticated_client.get(
                f"/api/v1/onlyfans/sync/{test_model_profile.id}/status"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["has_api_key"] is True
            assert data["last_sync"] is not None
            assert data["sync_age_seconds"] == pytest.approx(1800, rel=10)  # ~30 minutes
            assert data["is_fresh"] is True  # Less than 1 hour
            assert data["subscriber_count"] == 150
            assert data["total_earnings"] == 5000.0
            assert data["recent_stats"]["total_earnings"] == 5500.0
            assert data["recent_stats"]["new_subscribers"] == 25
    
    @pytest.mark.asyncio
    async def test_sync_posts_creates_content_records(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test post sync creates content records."""
        # Add API key
        test_model_profile.onlyfans_api_key = "test_api_key"
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Mock OnlyFans service
        with patch('modules.onlyfans_wrapper.application.sync_service.OnlyFansService') as mock_of:
            mock_client = AsyncMock()
            mock_of.return_value.get_client = AsyncMock(return_value=mock_client)
            
            # Mock posts
            mock_posts = [
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
            mock_client.get_posts = AsyncMock(return_value=mock_posts)
            
            # Mock other required methods
            mock_of.return_value.sync_profile = AsyncMock()
            mock_of.return_value.sync_fans = AsyncMock(return_value=0)
            mock_of.return_value.get_transactions = AsyncMock(return_value=[])
            mock_of.return_value.get_messages = AsyncMock(return_value=[])
            mock_of.return_value.get_statistics = AsyncMock()
            
            # Perform full sync
            response = await authenticated_client.post(
                f"/api/v1/onlyfans/sync/{test_model_profile.id}/all",
                params={"sync_messages": False}
            )
            
            assert response.status_code == 200
            
            # Verify content records were created
            from sqlalchemy import select
            result = await db_session.execute(
                select(Content).where(
                    Content.model_id == test_model_profile.id
                )
            )
            content_items = result.scalars().all()
            assert len(content_items) == 2
            
            # Verify PPV content
            ppv_content = next(c for c in content_items if c.platform_content_id == "post_1")
            assert ppv_content.price == Decimal("15.00")
            assert ppv_content.is_ppv is True
            assert ppv_content.content_type == "photo"
    
    @pytest.mark.asyncio
    async def test_sync_permission_checks(
        self,
        authenticated_client: AsyncClient,
        test_chatter,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test permission checks for sync endpoints."""
        # Add API key
        test_model_profile.onlyfans_api_key = "test_api_key"
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Try to sync as chatter (should fail)
        response = await authenticated_client.post(
            f"/api/v1/onlyfans/sync/{test_model_profile.id}/all",
            headers={"Authorization": f"Bearer {test_chatter.id}"}
        )
        
        assert response.status_code == 403
        assert "Not authorized to sync data" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_sync_error_handling(
        self,
        authenticated_client: AsyncClient,
        test_agency_owner,
        test_model_profile,
        db_session: AsyncSession
    ):
        """Test error handling during sync."""
        # Add API key
        test_model_profile.onlyfans_api_key = "test_api_key"
        db_session.add(test_model_profile)
        await db_session.commit()
        
        # Mock OnlyFans service to raise error
        with patch('modules.onlyfans_wrapper.application.sync_service.OnlyFansService') as mock_of:
            mock_of.return_value.sync_profile = AsyncMock(
                side_effect=Exception("OnlyFans API error")
            )
            
            response = await authenticated_client.post(
                f"/api/v1/onlyfans/sync/{test_model_profile.id}/all"
            )
            
            assert response.status_code == 500
            assert "Failed to sync data" in response.json()["detail"]