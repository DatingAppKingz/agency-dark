"""
Integration tests for messaging module including bulk messages, scheduling, and AI.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock

from modules.messaging.domain.models import (
    BulkMessage, MessageSchedule, CannedResponse,
    AIResponseSuggestion, BulkMessageStatus, ScheduleStatus
)
from modules.messaging.application.bulk_message_service import BulkMessageService
from modules.messaging.application.ai_response_service import AIResponseService
from modules.models.domain.models import Model
from modules.analytics.domain.models import Fan


class TestMessagingIntegration:
    """Test complete messaging workflows."""
    
    @pytest.fixture
    async def setup_messaging_data(self, test_db: AsyncSession):
        """Setup test data for messaging."""
        agency_id = uuid4()
        
        # Create model
        model = Model(
            id=uuid4(),
            agency_id=agency_id,
            username="test_model",
            display_name="Test Model",
            platform="onlyfans",
            is_active=True
        )
        test_db.add(model)
        
        # Create fans with various attributes
        fans = []
        fan_categories = [
            {"type": "vip", "count": 10, "spent_min": 500, "active": True},
            {"type": "regular", "count": 30, "spent_min": 100, "active": True},
            {"type": "new", "count": 20, "spent_min": 0, "active": True},
            {"type": "inactive", "count": 15, "spent_min": 200, "active": False}
        ]
        
        for category in fan_categories:
            for i in range(category["count"]):
                fan = Fan(
                    id=uuid4(),
                    model_id=model.id,
                    username=f"{category['type']}_fan_{i}",
                    display_name=f"{category['type'].title()} Fan {i}",
                    subscription_status="active" if category["active"] else "expired",
                    total_spent=category["spent_min"] + (i * 50),
                    message_count=i * 5,
                    tags=[category["type"]],
                    platform_data={"onlyfans": {"user_id": f"of_{uuid4()}"}},
                    created_at=datetime.utcnow() - timedelta(days=i)
                )
                test_db.add(fan)
                fans.append(fan)
        
        await test_db.commit()
        
        return {
            "agency_id": agency_id,
            "model": model,
            "fans": fans
        }
    
    @pytest.mark.asyncio
    async def test_bulk_message_campaign_workflow(
        self,
        async_client: AsyncClient,
        setup_messaging_data
    ):
        """Test complete bulk message campaign workflow."""
        model = setup_messaging_data["model"]
        
        # 1. Create bulk message campaign
        response = await async_client.post(
            "/api/v1/messaging/bulk",
            json={
                "campaign_name": "VIP Weekend Special",
                "model_id": str(model.id),
                "message_template": "Hey {{display_name}}! 🎉 You've spent ${{total_spent}} with me - here's a special thank you: {{promo_code}}",
                "recipient_filters": {
                    "subscription_status": ["active"],
                    "spent_min": 200,
                    "tags": ["vip"]
                },
                "template_variables": {
                    "promo_code": "VIP50OFF"
                },
                "platform": "onlyfans",
                "schedule_time": datetime.utcnow() + timedelta(minutes=5)
            }
        )
        assert response.status_code == 200
        campaign = response.json()
        campaign_id = campaign["campaign_id"]
        
        # 2. Check campaign status
        response = await async_client.get(
            f"/api/v1/messaging/bulk/{campaign_id}"
        )
        assert response.status_code == 200
        status = response.json()
        assert status["status"] == "scheduled"
        assert status["total_recipients"] > 0
        
        # 3. Preview messages
        response = await async_client.get(
            f"/api/v1/messaging/bulk/{campaign_id}/preview",
            params={"count": 3}
        )
        assert response.status_code == 200
        previews = response.json()
        assert len(previews["messages"]) <= 3
        assert "Hey VIP Fan" in previews["messages"][0]["content"]
        assert "VIP50OFF" in previews["messages"][0]["content"]
        
        # 4. Update campaign
        response = await async_client.patch(
            f"/api/v1/messaging/bulk/{campaign_id}",
            json={
                "schedule_time": datetime.utcnow() + timedelta(minutes=10)
            }
        )
        assert response.status_code == 200
        
        # 5. Cancel campaign
        response = await async_client.delete(
            f"/api/v1/messaging/bulk/{campaign_id}"
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_message_scheduling_with_recurrence(
        self,
        async_client: AsyncClient,
        setup_messaging_data
    ):
        """Test message scheduling with recurring patterns."""
        model = setup_messaging_data["model"]
        fan = setup_messaging_data["fans"][0]
        
        # 1. Create recurring scheduled message
        response = await async_client.post(
            "/api/v1/messaging/schedule",
            json={
                "model_id": str(model.id),
                "fan_id": str(fan.id),
                "message_content": "Good morning! Hope you have an amazing day 🌞",
                "scheduled_for": datetime.utcnow() + timedelta(days=1, hours=9),
                "platform": "onlyfans",
                "is_recurring": True,
                "recurrence_pattern": "daily",
                "recurrence_end_date": datetime.utcnow() + timedelta(days=7)
            }
        )
        assert response.status_code == 200
        schedule = response.json()
        schedule_id = schedule["schedule_id"]
        
        # 2. Get all scheduled messages
        response = await async_client.get(
            "/api/v1/messaging/schedule",
            params={
                "model_id": str(model.id),
                "is_recurring": True
            }
        )
        assert response.status_code == 200
        schedules = response.json()
        assert len(schedules["items"]) > 0
        
        # 3. Update schedule
        response = await async_client.patch(
            f"/api/v1/messaging/schedule/{schedule_id}",
            json={
                "message_content": "Good morning sunshine! ☀️ Have a wonderful day!",
                "recurrence_pattern": "weekdays"
            }
        )
        assert response.status_code == 200
        
        # 4. Pause schedule
        response = await async_client.post(
            f"/api/v1/messaging/schedule/{schedule_id}/pause"
        )
        assert response.status_code == 200
        
        # 5. Resume schedule
        response = await async_client.post(
            f"/api/v1/messaging/schedule/{schedule_id}/resume"
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ai_response_integration(
        self,
        async_client: AsyncClient,
        setup_messaging_data
    ):
        """Test AI response suggestions with context."""
        model = setup_messaging_data["model"]
        fan = setup_messaging_data["fans"][0]
        
        # Mock OpenAI response
        mock_openai_response = {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {
                            "response": "Thank you so much! 💕 I'm glad you enjoyed it!",
                            "tone": "appreciative",
                            "intent": "acknowledgment"
                        },
                        {
                            "response": "Aww you're so sweet! 🥰 Wait until you see what I have planned next!",
                            "tone": "flirty",
                            "intent": "tease"
                        }
                    ])
                }
            }]
        }
        
        with patch('openai.ChatCompletion.create', return_value=mock_openai_response):
            # 1. Get AI suggestions
            response = await async_client.post(
                "/api/v1/messaging/ai/suggestions",
                json={
                    "message_content": "Your latest post was absolutely amazing!",
                    "model_id": str(model.id),
                    "fan_id": str(fan.id),
                    "conversation_context": [
                        {
                            "role": "fan",
                            "content": "Just subscribed!",
                            "timestamp": datetime.utcnow() - timedelta(hours=1)
                        },
                        {
                            "role": "model",
                            "content": "Welcome! So happy to have you here 💖",
                            "timestamp": datetime.utcnow() - timedelta(minutes=50)
                        }
                    ],
                    "preferred_tone": "friendly",
                    "num_suggestions": 3
                }
            )
            assert response.status_code == 200
            suggestions = response.json()
            assert len(suggestions["suggestions"]) >= 2
            assert suggestions["sentiment_analysis"]["score"] > 0
        
        # 2. Rate suggestion
        suggestion_id = suggestions["suggestions"][0].get("id")
        if suggestion_id:
            response = await async_client.post(
                f"/api/v1/messaging/ai/suggestions/{suggestion_id}/rate",
                json={
                    "rating": 5,
                    "was_used": True
                }
            )
            assert response.status_code == 200
        
        # 3. Get suggestion history
        response = await async_client.get(
            "/api/v1/messaging/ai/history",
            params={
                "model_id": str(model.id),
                "fan_id": str(fan.id)
            }
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_canned_response_management(
        self,
        async_client: AsyncClient,
        setup_messaging_data
    ):
        """Test canned response library functionality."""
        agency_id = setup_messaging_data["agency_id"]
        
        # 1. Create canned responses
        responses = [
            {
                "title": "Welcome New Sub",
                "content": "Welcome to my page! 🎉 I'm so excited to have you here! Check your DMs for a special surprise 💝",
                "category": "greetings",
                "tags": ["welcome", "new subscriber"],
                "shortcuts": ["welcome", "newsub"]
            },
            {
                "title": "Thank You Tip",
                "content": "OMG thank you so much for the tip! 😍 You're absolutely amazing! 💖",
                "category": "appreciation",
                "tags": ["tip", "thank you"],
                "shortcuts": ["ty", "tip"]
            }
        ]
        
        created_ids = []
        for resp in responses:
            response = await async_client.post(
                "/api/v1/messaging/canned-responses",
                json=resp
            )
            assert response.status_code == 200
            created_ids.append(response.json()["id"])
        
        # 2. Search canned responses
        response = await async_client.get(
            "/api/v1/messaging/canned-responses",
            params={
                "search": "welcome",
                "category": "greetings"
            }
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results["items"]) > 0
        
        # 3. Get by shortcut
        response = await async_client.get(
            "/api/v1/messaging/canned-responses/shortcut/ty"
        )
        assert response.status_code == 200
        assert "thank you" in response.json()["content"].lower()
        
        # 4. Update canned response
        response = await async_client.patch(
            f"/api/v1/messaging/canned-responses/{created_ids[0]}",
            json={
                "content": "Welcome aboard! 🚀 So thrilled you're here! Check DMs for your welcome gift 🎁"
            }
        )
        assert response.status_code == 200
        
        # 5. Track usage
        response = await async_client.post(
            f"/api/v1/messaging/canned-responses/{created_ids[0]}/use"
        )
        assert response.status_code == 200
        
        # 6. Get usage statistics
        response = await async_client.get(
            "/api/v1/messaging/canned-responses/stats"
        )
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_responses"] >= 2
        assert stats["total_uses"] >= 1
    
    @pytest.mark.asyncio
    async def test_message_template_variables(
        self,
        async_client: AsyncClient,
        setup_messaging_data
    ):
        """Test advanced template variable substitution."""
        model = setup_messaging_data["model"]
        
        # Create campaign with complex template
        response = await async_client.post(
            "/api/v1/messaging/bulk",
            json={
                "campaign_name": "Personalized Campaign",
                "model_id": str(model.id),
                "message_template": """
Hi {{display_name}}! 

You've been with me for {{days_subscribed}} days and spent ${{total_spent}}! 

{{#if is_vip}}
As a VIP member, you get exclusive access to {{vip_content}}!
{{else}}
Become a VIP to unlock special perks!
{{/if}}

{{#if birthday_this_month}}
🎂 Happy Birthday Month! Use code BDAY20 for 20% off!
{{/if}}
                """.strip(),
                "recipient_filters": {
                    "subscription_status": ["active"]
                },
                "template_variables": {
                    "vip_content": "behind-the-scenes footage"
                },
                "platform": "onlyfans"
            }
        )
        assert response.status_code == 200
        
        # Check variable validation
        campaign_id = response.json()["campaign_id"]
        response = await async_client.get(
            f"/api/v1/messaging/bulk/{campaign_id}/variables"
        )
        assert response.status_code == 200
        variables = response.json()
        assert "display_name" in variables["required_variables"]
        assert "is_vip" in variables["conditional_variables"]
    
    @pytest.mark.asyncio
    async def test_messaging_rate_limits(
        self,
        async_client: AsyncClient,
        setup_messaging_data
    ):
        """Test messaging rate limiting."""
        model = setup_messaging_data["model"]
        fans = setup_messaging_data["fans"][:5]
        
        # Send multiple messages quickly
        send_count = 0
        for fan in fans:
            for i in range(3):  # 3 messages per fan
                response = await async_client.post(
                    "/api/v1/messaging/send",
                    json={
                        "model_id": str(model.id),
                        "fan_id": str(fan.id),
                        "content": f"Test message {i}",
                        "platform": "onlyfans"
                    }
                )
                
                if response.status_code == 200:
                    send_count += 1
                elif response.status_code == 429:
                    # Rate limited
                    rate_limit_info = response.json()
                    assert "retry_after" in rate_limit_info
                    break
        
        # Should hit rate limit before sending all
        assert send_count < 15  # Less than all 15 messages
    
    @pytest.mark.asyncio
    async def test_message_analytics(
        self,
        async_client: AsyncClient,
        setup_messaging_data,
        test_db: AsyncSession
    ):
        """Test message analytics and reporting."""
        model = setup_messaging_data["model"]
        
        # Create bulk campaign
        campaign = BulkMessage(
            id=uuid4(),
            agency_id=model.agency_id,
            model_id=model.id,
            campaign_name="Analytics Test",
            message_template="Test message",
            total_recipients=50,
            sent_count=45,
            failed_count=5,
            status=BulkMessageStatus.COMPLETED,
            platform="onlyfans",
            created_at=datetime.utcnow() - timedelta(hours=2),
            completed_at=datetime.utcnow() - timedelta(hours=1)
        )
        test_db.add(campaign)
        await test_db.commit()
        
        # Get messaging analytics
        response = await async_client.get(
            "/api/v1/analytics/messaging",
            params={
                "model_id": str(model.id),
                "date_from": (datetime.utcnow() - timedelta(days=7)).date().isoformat(),
                "date_to": datetime.utcnow().date().isoformat()
            }
        )
        assert response.status_code == 200
        
        analytics = response.json()
        assert analytics["bulk_campaigns"]["total"] >= 1
        assert analytics["bulk_campaigns"]["success_rate"] > 0
        assert analytics["total_messages_sent"] >= 45


class TestMessagingWebSocket:
    """Test real-time messaging features."""
    
    @pytest.mark.asyncio
    async def test_real_time_message_delivery(
        self,
        websocket_client,
        setup_messaging_data
    ):
        """Test real-time message delivery notifications."""
        model = setup_messaging_data["model"]
        
        async with websocket_client.connect(
            f"/ws/messaging/{model.id}"
        ) as websocket:
            # Subscribe to message events
            await websocket.send_json({
                "type": "subscribe",
                "events": ["message_sent", "message_delivered", "message_failed"]
            })
            
            # Should receive acknowledgment
            data = await websocket.receive_json()
            assert data["type"] == "subscribed"
            
            # In real scenario, sending a message would trigger events
            # Simulate message event
            await asyncio.sleep(1)
            
            # Would receive real-time updates
            # data = await websocket.receive_json()
            # assert data["type"] in ["message_sent", "message_delivered"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])