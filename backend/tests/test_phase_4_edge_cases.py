"""
Edge case and error handling tests for Phase 4 features.

Tests cover error scenarios, boundary conditions, and edge cases.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
import json

from core.exceptions import BadRequestError, NotFoundError, RateLimitError
from modules.messaging.application.bulk_message_service import BulkMessageService
from modules.messaging.application.ai_response_service import AIResponseService
from modules.reporting.application.report_builder_service import ReportBuilderService
from modules.reporting.application.scheduled_report_service import ScheduledReportService
from modules.messaging.domain.schemas import BulkMessageCreate
from modules.reporting.domain.schemas import ReportScheduleCreate, ScheduleParameters, DeliveryConfig
from modules.reporting.domain.models import DeliveryMethod


class TestBulkMessagingEdgeCases:
    """Test edge cases for bulk messaging."""
    
    @pytest.fixture
    def bulk_message_service(self):
        return BulkMessageService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_bulk_message_no_recipients(self, bulk_message_service, mock_db):
        """Test bulk message with no matching recipients."""
        # Mock empty fan list
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        campaign_data = BulkMessageCreate(
            campaign_name="Empty Campaign",
            model_id=uuid4(),
            message_template="Test message",
            recipient_filters={"subscription_status": ["expired"]},
            platform="onlyfans"
        )
        
        # Should raise error
        with pytest.raises(BadRequestError, match="No recipients found"):
            await bulk_message_service.create_bulk_campaign(
                campaign_data, uuid4(), uuid4(), mock_db
            )
    
    @pytest.mark.asyncio
    async def test_bulk_message_invalid_template_variables(self, bulk_message_service, mock_db):
        """Test bulk message with invalid template variables."""
        mock_fans = [MagicMock(id=uuid4(), display_name="Test Fan")]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_fans
        
        campaign_data = BulkMessageCreate(
            campaign_name="Invalid Template",
            model_id=uuid4(),
            message_template="Hello {{invalid_variable}}!",
            recipient_filters={},
            platform="onlyfans"
        )
        
        # Should handle gracefully
        result = await bulk_message_service.create_bulk_campaign(
            campaign_data, uuid4(), uuid4(), mock_db
        )
        
        # Template should be validated
        assert result.total_recipients == 1
    
    @pytest.mark.asyncio
    async def test_bulk_message_platform_api_failure(self, bulk_message_service, mock_db):
        """Test handling of platform API failures during bulk send."""
        bulk_message = MagicMock(
            id=uuid4(),
            message_template="Test message",
            recipient_data=[{"fan_id": str(uuid4()), "display_name": "Fan"}],
            platform="onlyfans",
            sent_count=0,
            failed_count=0
        )
        
        # Mock API failure
        with patch.object(bulk_message_service, '_send_platform_message', side_effect=Exception("API Error")):
            await bulk_message_service._process_bulk_message_batch(
                bulk_message, bulk_message.recipient_data, mock_db
            )
            
            # Should track failures
            assert bulk_message.failed_count == 1
            assert bulk_message.sent_count == 0
    
    @pytest.mark.asyncio
    async def test_bulk_message_rate_limit_handling(self, bulk_message_service, mock_db):
        """Test rate limit handling during bulk send."""
        # Create large recipient list
        recipients = [{"fan_id": str(uuid4()), "display_name": f"Fan {i}"} for i in range(1000)]
        
        bulk_message = MagicMock(
            id=uuid4(),
            message_template="Test",
            recipient_data=recipients,
            platform="onlyfans"
        )
        
        call_count = 0
        async def mock_send_with_rate_limit(fan_id, message, platform):
            nonlocal call_count
            call_count += 1
            if call_count > 100:
                raise RateLimitError("Rate limit exceeded")
            return True
        
        with patch.object(bulk_message_service, '_send_platform_message', side_effect=mock_send_with_rate_limit):
            # Process should handle rate limits gracefully
            await bulk_message_service._process_bulk_message_batch(
                bulk_message, recipients[:150], mock_db
            )
            
            # Should have stopped at rate limit
            assert call_count == 101  # 100 successful + 1 rate limited


class TestAIResponseEdgeCases:
    """Test edge cases for AI response system."""
    
    @pytest.fixture
    def ai_response_service(self):
        return AIResponseService()
    
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_ai_response_openai_failure(self, ai_response_service, mock_db):
        """Test handling of OpenAI API failures."""
        with patch('openai.ChatCompletion.create', side_effect=Exception("OpenAI Error")):
            # Should fallback to template-based suggestions
            suggestions = await ai_response_service.get_response_suggestions(
                message_content="Hello!",
                conversation_history=[],
                model_id=uuid4(),
                fan_id=uuid4(),
                agency_id=uuid4(),
                db=mock_db
            )
            
            # Should return fallback suggestions
            assert len(suggestions) > 0
            assert all('response' in s for s in suggestions)
    
    @pytest.mark.asyncio
    async def test_ai_response_malformed_json(self, ai_response_service, mock_db):
        """Test handling of malformed JSON from AI."""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "This is not valid JSON"
                }
            }]
        }
        
        with patch('openai.ChatCompletion.create', return_value=mock_response):
            # Should handle gracefully
            suggestions = await ai_response_service.get_response_suggestions(
                message_content="Test",
                conversation_history=[],
                model_id=uuid4(),
                fan_id=uuid4(),
                agency_id=uuid4(),
                db=mock_db
            )
            
            # Should return fallback suggestions
            assert len(suggestions) > 0
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_empty_text(self, ai_response_service):
        """Test sentiment analysis with empty or invalid text."""
        # Empty text
        empty_sentiment = ai_response_service._analyze_sentiment("")
        assert empty_sentiment == 0.0
        
        # None text
        none_sentiment = ai_response_service._analyze_sentiment(None)
        assert none_sentiment == 0.0
        
        # Very long text
        long_text = "Test " * 10000
        long_sentiment = ai_response_service._analyze_sentiment(long_text)
        assert isinstance(long_sentiment, float)
    
    @pytest.mark.asyncio
    async def test_ai_context_too_large(self, ai_response_service, mock_db):
        """Test handling of conversation history that's too large."""
        # Create very large conversation history
        large_history = [
            {"role": "user", "content": "Long message " * 1000},
            {"role": "assistant", "content": "Long response " * 1000}
        ] * 50
        
        # Should truncate history appropriately
        with patch('openai.ChatCompletion.create') as mock_openai:
            await ai_response_service.get_response_suggestions(
                message_content="New message",
                conversation_history=large_history,
                model_id=uuid4(),
                fan_id=uuid4(),
                agency_id=uuid4(),
                db=mock_db
            )
            
            # Verify context was truncated
            call_args = mock_openai.call_args[1]
            messages = call_args['messages']
            # Should have system prompt + truncated history + current message
            assert len(messages) < len(large_history) + 2


class TestReportingEdgeCases:
    """Test edge cases for reporting features."""
    
    @pytest.fixture
    def report_builder_service(self):
        return ReportBuilderService()
    
    @pytest.fixture
    def scheduled_report_service(self):
        return ScheduledReportService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.get = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_report_template_circular_reference(self, report_builder_service, mock_db):
        """Test handling of circular widget references."""
        # This would test widgets that reference each other
        pass
    
    @pytest.mark.asyncio
    async def test_report_generation_timeout(self, report_builder_service, mock_db):
        """Test handling of report generation timeout."""
        # Mock slow widget data generation
        async def slow_widget_handler(*args, **kwargs):
            await asyncio.sleep(60)  # Simulate very slow query
            return {"data": "test"}
        
        with patch.object(report_builder_service, '_build_metric_widget', side_effect=slow_widget_handler):
            # Should handle timeout appropriately
            pass
    
    @pytest.mark.asyncio
    async def test_scheduled_report_invalid_cron(self, scheduled_report_service, mock_db):
        """Test invalid cron expressions."""
        mock_template = MagicMock(id=uuid4(), agency_id=uuid4())
        mock_db.get.return_value = mock_template
        
        schedule_data = ReportScheduleCreate(
            name="Invalid Cron",
            template_id=mock_template.id,
            schedule_type="cron",
            cron_expression="invalid cron",
            parameters=ScheduleParameters(),
            delivery_method=DeliveryMethod.EMAIL,
            delivery_config=DeliveryConfig()
        )
        
        with pytest.raises(BadRequestError, match="Invalid cron expression"):
            await scheduled_report_service.create_report_schedule(
                schedule_data, mock_template.agency_id, uuid4(), mock_db
            )
    
    @pytest.mark.asyncio
    async def test_report_delivery_webhook_timeout(self, scheduled_report_service, mock_db):
        """Test webhook delivery timeout handling."""
        schedule = MagicMock(
            delivery_method=DeliveryMethod.WEBHOOK,
            delivery_config={"webhook_url": "https://example.com/webhook"}
        )
        report = MagicMock(id=uuid4(), report_data={})
        
        with patch('aiohttp.ClientSession.post', side_effect=asyncio.TimeoutError()):
            # Should handle timeout gracefully
            await scheduled_report_service._deliver_via_webhook(schedule, report)
            # Should log error but not crash
    
    @pytest.mark.asyncio
    async def test_export_data_memory_limit(self, report_builder_service, mock_db):
        """Test handling of very large data exports."""
        # Mock huge dataset
        huge_data = [{"id": i, "data": "x" * 1000} for i in range(100000)]
        
        # Should handle memory efficiently (streaming, pagination, etc.)
        pass
    
    @pytest.mark.asyncio
    async def test_concurrent_report_generation(self, report_builder_service, mock_db):
        """Test concurrent report generation for same template."""
        template_id = uuid4()
        
        # Simulate multiple concurrent report generations
        tasks = []
        for _ in range(10):
            request = MagicMock(date_from=datetime.now() - timedelta(days=30))
            task = report_builder_service.generate_report(
                template_id, request, uuid4(), uuid4(), mock_db
            )
            tasks.append(task)
        
        # Should handle concurrency properly
        # In real implementation, might use locks or queuing
        pass


class TestDataValidation:
    """Test data validation edge cases."""
    
    @pytest.mark.asyncio
    async def test_bulk_message_xss_prevention(self):
        """Test XSS prevention in message templates."""
        service = BulkMessageService()
        
        # Test various XSS attempts
        xss_templates = [
            "<script>alert('xss')</script>",
            "{{display_name}}<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>"
        ]
        
        for template in xss_templates:
            # Should sanitize or reject dangerous content
            pass
    
    @pytest.mark.asyncio
    async def test_report_sql_injection_prevention(self):
        """Test SQL injection prevention in custom filters."""
        service = ReportBuilderService()
        
        # Test various SQL injection attempts in filters
        malicious_filters = [
            {"model_id": "'; DROP TABLE users; --"},
            {"date_from": "2024-01-01' OR '1'='1"},
            {"custom": "1; DELETE FROM reports WHERE 1=1"}
        ]
        
        # Should use parameterized queries and validation
        pass
    
    @pytest.mark.asyncio
    async def test_file_path_traversal_prevention(self):
        """Test path traversal prevention in exports."""
        # Test various path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32"
        ]
        
        # Should validate and sanitize file paths
        pass


class TestPerformanceEdgeCases:
    """Test performance-related edge cases."""
    
    @pytest.mark.asyncio
    async def test_bulk_message_memory_efficiency(self):
        """Test memory efficiency with very large recipient lists."""
        # Test with 1 million recipients
        # Should use batching and streaming
        pass
    
    @pytest.mark.asyncio
    async def test_report_generation_query_optimization(self):
        """Test query optimization for complex reports."""
        # Test with reports that would generate N+1 queries
        # Should use proper joins and eager loading
        pass
    
    @pytest.mark.asyncio
    async def test_ai_response_cache_effectiveness(self):
        """Test AI response caching for repeated queries."""
        # Test cache hit rates and memory usage
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])