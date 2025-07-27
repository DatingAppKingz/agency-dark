"""
Tests for mass messaging service.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import uuid
import json

from modules.api_orchestration.application.mass_message_service import (
    MassMessageService,
    MessagePriority,
    MessageQueueItem
)
from modules.api_orchestration.domain.schemas import (
    DataSource,
    MassMessageRequest,
    MessageRequest,
    MassMessageStatus
)
from core.domain.models import ModelProfile, Fan, User


@pytest.fixture
def model_profile():
    """Create test model profile."""
    return ModelProfile(
        id="test-model-id",
        user_id="test-user-id",
        agency_id="test-agency-id",
        onlyfans_api_key="of_key",
        inflow_api_key="if_key",
        onlyfans_user_id="of_model_123"
    )


@pytest.fixture
def user():
    """Create test user."""
    return User(
        id="test-user-id",
        email="test@example.com",
        role="model"
    )


@pytest.fixture
def fans():
    """Create test fans."""
    return [
        Fan(
            id=f"fan-{i}",
            model_id="test-model-id",
            onlyfans_user_id=f"of_fan_{i}",
            username=f"fan{i}",
            total_spent=Decimal(str(i * 100)),
            message_count=i * 5,
            is_subscriber=i % 2 == 0,
            last_active_at=datetime.utcnow() - timedelta(days=i)
        )
        for i in range(1, 6)
    ]


@pytest.fixture
async def mass_message_service(db_session):
    """Create mass message service instance."""
    return MassMessageService(db_session)


class TestMassMessageService:
    """Tests for MassMessageService."""
    
    @pytest.mark.asyncio
    async def test_send_mass_message_basic(
        self, mass_message_service, model_profile, user, fans, db_session
    ):
        """Test basic mass message send."""
        # Mock fan query
        with patch.object(db_session, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = fans
            mock_execute.return_value = mock_result
            
            # Mock router
            with patch.object(
                mass_message_service.router,
                'determine_best_source',
                new_callable=AsyncMock
            ) as mock_route:
                mock_route.return_value = DataSource.ONLYFANS
                
                # Mock Redis
                with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
                    mock_redis.setex = AsyncMock()
                    
                    request = MassMessageRequest(
                        text="Test message",
                        recipient_criteria={"subscription_status": "active"}
                    )
                    
                    status = await mass_message_service.send_mass_message(
                        model_profile, request, user
                    )
                    
                    assert status.total_recipients == len(fans)
                    assert status.pending == len(fans)
                    assert status.sent == 0
                    assert status.failed == 0
                    assert status.status == "running"
                    assert status.campaign_id is not None
                    
    @pytest.mark.asyncio
    async def test_get_target_fans_with_criteria(
        self, mass_message_service, model_profile, fans, db_session
    ):
        """Test fan filtering with various criteria."""
        # Test subscription status filter
        with patch.object(db_session, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            active_fans = [f for f in fans if f.is_subscriber]
            mock_result.scalars.return_value.all.return_value = active_fans
            mock_execute.return_value = mock_result
            
            request = MassMessageRequest(
                text="Test",
                recipient_criteria={"subscription_status": "active"}
            )
            
            result = await mass_message_service._get_target_fans(
                model_profile, request
            )
            
            assert len(result) == len(active_fans)
            
    @pytest.mark.asyncio
    async def test_get_target_fans_spending_filter(
        self, mass_message_service, model_profile, fans, db_session
    ):
        """Test fan filtering by spending."""
        with patch.object(db_session, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_result = MagicMock()
            high_spenders = [f for f in fans if f.total_spent >= 300]
            mock_result.scalars.return_value.all.return_value = high_spenders
            mock_execute.return_value = mock_result
            
            request = MassMessageRequest(
                text="Test",
                recipient_criteria={"min_spent": 300}
            )
            
            result = await mass_message_service._get_target_fans(
                model_profile, request
            )
            
            assert all(f.total_spent >= 300 for f in result)
            
    def test_calculate_message_priority(self, mass_message_service):
        """Test message priority calculation."""
        # Whale fan
        whale = Fan(id="1", total_spent=Decimal("1500"), message_count=50)
        assert mass_message_service._calculate_message_priority(whale) == MessagePriority.HIGH
        
        # Engaged fan
        engaged = Fan(id="2", total_spent=Decimal("150"), message_count=25)
        assert mass_message_service._calculate_message_priority(engaged) == MessagePriority.HIGH
        
        # Regular subscriber
        regular = Fan(id="3", total_spent=Decimal("50"), message_count=5, is_subscriber=True)
        assert mass_message_service._calculate_message_priority(regular) == MessagePriority.NORMAL
        
        # Low value fan
        low = Fan(id="4", total_spent=Decimal("10"), message_count=2, is_subscriber=False)
        assert mass_message_service._calculate_message_priority(low) == MessagePriority.LOW
        
    @pytest.mark.asyncio
    async def test_message_worker_processing(
        self, mass_message_service, model_profile, user
    ):
        """Test message worker processes queue items."""
        campaign_id = str(uuid.uuid4())
        queue = asyncio.Queue()
        
        # Add test message
        item = MessageQueueItem(
            campaign_id=campaign_id,
            fan_id="test-fan",
            message_request=MessageRequest(
                fan_id="test-fan",
                text="Test message"
            )
        )
        await queue.put(item)
        
        mass_message_service._message_queues[campaign_id] = queue
        mass_message_service._active_campaigns[campaign_id] = MassMessageStatus(
            campaign_id=campaign_id,
            total_recipients=1,
            pending=1,
            sent=0,
            failed=0,
            status="running",
            created_at=datetime.utcnow()
        )
        
        # Mock orchestrator
        with patch.object(
            mass_message_service.orchestrator,
            'send_message_with_failover',
            new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"success": True, "source": "onlyfans"}
            
            # Mock Redis
            with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
                mock_redis.setex = AsyncMock()
                mock_redis.get = AsyncMock(return_value=None)
                
                # Run worker for a short time
                worker_task = asyncio.create_task(
                    mass_message_service._message_worker(
                        campaign_id, model_profile, user, 0
                    )
                )
                
                # Wait for processing
                await asyncio.sleep(0.5)
                
                # Cancel worker
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass
                    
                # Verify message was sent
                mock_send.assert_called_once()
                status = mass_message_service._active_campaigns[campaign_id]
                assert status.sent == 1
                assert status.pending == 0
                
    @pytest.mark.asyncio
    async def test_message_retry_on_failure(
        self, mass_message_service, model_profile, user
    ):
        """Test message retry logic on failure."""
        campaign_id = str(uuid.uuid4())
        queue = asyncio.Queue()
        
        item = MessageQueueItem(
            campaign_id=campaign_id,
            fan_id="test-fan",
            message_request=MessageRequest(
                fan_id="test-fan",
                text="Test message"
            ),
            retry_count=0
        )
        await queue.put(item)
        
        mass_message_service._message_queues[campaign_id] = queue
        mass_message_service._active_campaigns[campaign_id] = MassMessageStatus(
            campaign_id=campaign_id,
            total_recipients=1,
            pending=1,
            sent=0,
            failed=0,
            status="running",
            created_at=datetime.utcnow()
        )
        
        # Mock orchestrator to fail
        with patch.object(
            mass_message_service.orchestrator,
            'send_message_with_failover',
            new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = Exception("API Error")
            
            with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
                mock_redis.setex = AsyncMock()
                mock_redis.get = AsyncMock(return_value=None)
                
                # Process message (should fail and retry)
                success = await mass_message_service._send_single_message(
                    model_profile, item, user
                )
                
                assert success is False
                assert item.error == "API Error"
                
    @pytest.mark.asyncio
    async def test_calculate_send_delay(
        self, mass_message_service, model_profile
    ):
        """Test delay calculation based on rate limits."""
        with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
            # Low usage
            mock_redis.get = AsyncMock(return_value="20")
            delay = await mass_message_service._calculate_send_delay(model_profile)
            assert delay == 1.0
            
            # Medium usage
            mock_redis.get = AsyncMock(return_value="45")
            delay = await mass_message_service._calculate_send_delay(model_profile)
            assert delay == 1.5
            
            # High usage
            mock_redis.get = AsyncMock(return_value="55")
            delay = await mass_message_service._calculate_send_delay(model_profile)
            assert delay == 2.0
            
    @pytest.mark.asyncio
    async def test_campaign_completion(
        self, mass_message_service, db_session
    ):
        """Test campaign completion process."""
        campaign_id = str(uuid.uuid4())
        
        status = MassMessageStatus(
            campaign_id=campaign_id,
            total_recipients=10,
            sent=8,
            failed=2,
            pending=0,
            status="running",
            created_at=datetime.utcnow() - timedelta(minutes=5)
        )
        
        mass_message_service._active_campaigns[campaign_id] = status
        mass_message_service._message_queues[campaign_id] = asyncio.Queue()
        
        with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
            mock_redis.setex = AsyncMock()
            
            await mass_message_service._complete_campaign(campaign_id)
            
            assert status.status == "completed"
            assert status.completed_at is not None
            assert campaign_id not in mass_message_service._message_queues
            
    @pytest.mark.asyncio
    async def test_cancel_campaign(
        self, mass_message_service
    ):
        """Test campaign cancellation."""
        campaign_id = str(uuid.uuid4())
        queue = asyncio.Queue()
        
        # Add some pending messages
        for i in range(5):
            await queue.put(MessageQueueItem(
                campaign_id=campaign_id,
                fan_id=f"fan-{i}",
                message_request=MessageRequest(fan_id=f"fan-{i}", text="Test")
            ))
            
        status = MassMessageStatus(
            campaign_id=campaign_id,
            total_recipients=10,
            sent=3,
            failed=0,
            pending=7,
            status="running",
            created_at=datetime.utcnow()
        )
        
        mass_message_service._active_campaigns[campaign_id] = status
        mass_message_service._message_queues[campaign_id] = queue
        mass_message_service._worker_tasks[campaign_id] = []
        
        with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
            mock_redis.setex = AsyncMock()
            
            success = await mass_message_service.cancel_campaign(campaign_id)
            
            assert success is True
            assert status.status == "cancelled"
            assert status.completed_at is not None
            assert status.pending == 0
            assert status.failed == 2  # Original failed + remaining messages
            
    @pytest.mark.asyncio
    async def test_get_campaign_status(
        self, mass_message_service
    ):
        """Test retrieving campaign status."""
        campaign_id = str(uuid.uuid4())
        
        # Test active campaign
        active_status = MassMessageStatus(
            campaign_id=campaign_id,
            total_recipients=10,
            sent=5,
            failed=0,
            pending=5,
            status="running",
            created_at=datetime.utcnow()
        )
        
        mass_message_service._active_campaigns[campaign_id] = active_status
        
        status = await mass_message_service.get_campaign_status(campaign_id)
        assert status == active_status
        
        # Test completed campaign from Redis
        with patch('modules.api_orchestration.application.mass_message_service.redis_client') as mock_redis:
            completed_data = {
                "campaign_id": "old-campaign",
                "total_recipients": 20,
                "sent": 18,
                "failed": 2,
                "pending": 0,
                "status": "completed",
                "created_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat()
            }
            
            mock_redis.get = AsyncMock(return_value=json.dumps(completed_data))
            
            old_status = await mass_message_service.get_campaign_status("old-campaign")
            assert old_status is not None
            assert old_status.status == "completed"
            
    @pytest.mark.asyncio
    async def test_get_campaign_history(
        self, mass_message_service, model_profile, db_session
    ):
        """Test retrieving campaign history."""
        with patch.object(db_session, 'execute', new_callable=AsyncMock) as mock_execute:
            # Mock analytics events
            events = [
                MagicMock(
                    event_type="mass_message_started",
                    timestamp=datetime.utcnow(),
                    metadata={
                        "campaign_id": "camp1",
                        "model_id": str(model_profile.id),
                        "total_recipients": 100,
                        "has_price": False
                    }
                ),
                MagicMock(
                    event_type="mass_message_completed",
                    timestamp=datetime.utcnow() + timedelta(minutes=10),
                    metadata={
                        "campaign_id": "camp1",
                        "sent": 95,
                        "failed": 5,
                        "duration_seconds": 600
                    }
                )
            ]
            
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = events
            mock_execute.return_value = mock_result
            
            history = await mass_message_service.get_campaign_history(
                model_profile, limit=10
            )
            
            assert len(history) == 1
            assert history[0]["campaign_id"] == "camp1"
            assert history[0]["total_recipients"] == 100
            assert history[0]["sent"] == 95
            assert history[0]["status"] == "completed"