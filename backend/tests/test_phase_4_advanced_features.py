"""
Comprehensive tests for Phase 4: Advanced Features.

Tests cover:
- Bulk messaging system
- Message scheduling
- AI-powered automated responses
- Canned response library
- Analytics export functionality
- Custom report builder
- Scheduled report generation
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import json
import io
from unittest.mock import AsyncMock, patch, MagicMock
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.messaging.application.bulk_message_service import BulkMessageService
from modules.messaging.application.scheduling_service import MessageSchedulingService
from modules.messaging.application.ai_response_service import AIResponseService
from modules.messaging.application.canned_response_service import CannedResponseService
from modules.reporting.application.export_service import ExportService
from modules.reporting.application.report_builder_service import ReportBuilderService
from modules.reporting.application.scheduled_report_service import ScheduledReportService

from modules.messaging.domain.models import (
    BulkMessage, BulkMessageStatus, MessageSchedule, ScheduleStatus,
    CannedResponse, AIResponseSuggestion
)
from modules.reporting.domain.models import (
    ReportTemplate, ReportWidget, ReportSchedule, GeneratedReport,
    ReportStatus, DeliveryMethod
)
from modules.messaging.domain.schemas import (
    BulkMessageCreate, MessageScheduleCreate, CannedResponseCreate
)
from modules.reporting.domain.schemas import (
    ReportTemplateCreate, ReportScheduleCreate, ReportGenerateRequest,
    ReportWidgetConfig, ScheduleParameters, DeliveryConfig
)


class TestBulkMessagingSystem:
    """Test bulk messaging functionality."""
    
    @pytest.fixture
    def bulk_message_service(self):
        return BulkMessageService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_create_bulk_message_campaign(self, bulk_message_service, mock_db):
        """Test creating a bulk message campaign."""
        # Prepare test data
        agency_id = uuid4()
        model_id = uuid4()
        user_id = uuid4()
        
        campaign_data = BulkMessageCreate(
            campaign_name="Test Campaign",
            model_id=model_id,
            message_template="Hello {{display_name}}! Check out our new content.",
            recipient_filters={
                "subscription_status": ["active"],
                "spent_min": 50
            },
            platform="onlyfans",
            schedule_time=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Mock fan query
        mock_fans = [
            MagicMock(id=uuid4(), display_name="Fan 1", platform_data={"onlyfans": {"user_id": "123"}}),
            MagicMock(id=uuid4(), display_name="Fan 2", platform_data={"onlyfans": {"user_id": "456"}})
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_fans
        
        # Execute
        result = await bulk_message_service.create_bulk_campaign(
            campaign_data, agency_id, user_id, mock_db
        )
        
        # Verify
        assert result.campaign_name == "Test Campaign"
        assert result.total_recipients == 2
        assert result.status == BulkMessageStatus.SCHEDULED
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_process_bulk_message_with_template_variables(self, bulk_message_service, mock_db):
        """Test processing bulk messages with template variable substitution."""
        # Create mock bulk message
        bulk_message = MagicMock(
            id=uuid4(),
            message_template="Hi {{display_name}}, your total spent is ${{total_spent}}!",
            recipient_data=[
                {"fan_id": str(uuid4()), "display_name": "John", "total_spent": 150},
                {"fan_id": str(uuid4()), "display_name": "Jane", "total_spent": 200}
            ],
            platform="onlyfans",
            status=BulkMessageStatus.PROCESSING
        )
        
        # Mock platform API
        with patch.object(bulk_message_service, '_send_platform_message', return_value=True):
            # Process messages
            await bulk_message_service._process_bulk_message_batch(
                bulk_message, bulk_message.recipient_data, mock_db
            )
            
            # Verify template substitution
            assert bulk_message.sent_count == 2
            assert bulk_message.status == BulkMessageStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_bulk_message_rate_limiting(self, bulk_message_service, mock_db):
        """Test rate limiting for bulk messages."""
        # Create mock bulk message with many recipients
        recipients = [{"fan_id": str(uuid4()), "display_name": f"Fan {i}"} for i in range(100)]
        bulk_message = MagicMock(
            id=uuid4(),
            message_template="Test message",
            recipient_data=recipients,
            platform="onlyfans",
            status=BulkMessageStatus.PROCESSING
        )
        
        # Mock platform API with rate limit tracking
        send_times = []
        async def mock_send(fan_id, message, platform):
            send_times.append(datetime.utcnow())
            return True
        
        with patch.object(bulk_message_service, '_send_platform_message', side_effect=mock_send):
            # Process messages
            await bulk_message_service._process_bulk_message_batch(
                bulk_message, recipients[:10], mock_db  # Process first 10
            )
            
            # Verify rate limiting (should have delays)
            assert len(send_times) == 10
            # Check that messages are spaced appropriately
            for i in range(1, len(send_times)):
                time_diff = (send_times[i] - send_times[i-1]).total_seconds()
                assert time_diff >= 0.1  # At least 100ms between messages


class TestMessageScheduling:
    """Test message scheduling functionality."""
    
    @pytest.fixture
    def scheduling_service(self):
        return MessageSchedulingService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_create_scheduled_message(self, scheduling_service, mock_db):
        """Test creating a scheduled message."""
        # Prepare test data
        agency_id = uuid4()
        model_id = uuid4()
        user_id = uuid4()
        fan_id = uuid4()
        
        schedule_data = MessageScheduleCreate(
            model_id=model_id,
            fan_id=fan_id,
            message_content="Scheduled message test",
            scheduled_for=datetime.utcnow() + timedelta(hours=2),
            platform="onlyfans",
            is_recurring=False
        )
        
        # Execute
        result = await scheduling_service.create_scheduled_message(
            schedule_data, agency_id, user_id, mock_db
        )
        
        # Verify
        assert result.message_content == "Scheduled message test"
        assert result.status == ScheduleStatus.PENDING
        assert result.is_recurring is False
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_recurring_scheduled_message(self, scheduling_service, mock_db):
        """Test creating a recurring scheduled message."""
        # Prepare test data
        agency_id = uuid4()
        model_id = uuid4()
        user_id = uuid4()
        fan_id = uuid4()
        
        schedule_data = MessageScheduleCreate(
            model_id=model_id,
            fan_id=fan_id,
            message_content="Weekly update",
            scheduled_for=datetime.utcnow() + timedelta(days=1),
            platform="onlyfans",
            is_recurring=True,
            recurrence_pattern="weekly",
            recurrence_end_date=datetime.utcnow() + timedelta(days=30)
        )
        
        # Execute
        result = await scheduling_service.create_scheduled_message(
            schedule_data, agency_id, user_id, mock_db
        )
        
        # Verify
        assert result.is_recurring is True
        assert result.recurrence_pattern == "weekly"
        assert result.recurrence_end_date is not None
    
    @pytest.mark.asyncio
    async def test_process_due_scheduled_messages(self, scheduling_service, mock_db):
        """Test processing messages that are due to be sent."""
        # Mock due messages
        mock_messages = [
            MagicMock(
                id=uuid4(),
                message_content="Test message 1",
                fan_id=uuid4(),
                platform="onlyfans",
                status=ScheduleStatus.PENDING,
                is_recurring=False
            ),
            MagicMock(
                id=uuid4(),
                message_content="Test message 2",
                fan_id=uuid4(),
                platform="onlyfans",
                status=ScheduleStatus.PENDING,
                is_recurring=True,
                recurrence_pattern="daily"
            )
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_messages
        
        # Mock sending
        with patch.object(scheduling_service, '_send_scheduled_message', return_value=True):
            # Process messages
            await scheduling_service.process_scheduled_messages(mock_db)
            
            # Verify status updates
            assert mock_messages[0].status == ScheduleStatus.SENT
            assert mock_messages[1].status == ScheduleStatus.SENT
            assert mock_messages[1].last_sent_at is not None


class TestAIResponseSystem:
    """Test AI-powered response system."""
    
    @pytest.fixture
    def ai_response_service(self):
        return AIResponseService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_get_response_suggestions(self, ai_response_service, mock_db):
        """Test getting AI response suggestions."""
        # Mock OpenAI response
        mock_openai_response = {
            "choices": [{
                "message": {
                    "content": json.dumps([
                        {
                            "response": "Thanks for your support! 💕",
                            "tone": "friendly",
                            "intent": "appreciation"
                        },
                        {
                            "response": "I'm so glad you enjoyed it!",
                            "tone": "enthusiastic",
                            "intent": "appreciation"
                        }
                    ])
                }
            }]
        }
        
        with patch('openai.ChatCompletion.create', return_value=mock_openai_response):
            # Get suggestions
            suggestions = await ai_response_service.get_response_suggestions(
                message_content="I love your content!",
                conversation_history=[],
                model_id=uuid4(),
                fan_id=uuid4(),
                agency_id=uuid4(),
                db=mock_db
            )
            
            # Verify
            assert len(suggestions) >= 2
            assert all('response' in s for s in suggestions)
            assert all('confidence' in s for s in suggestions)
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis(self, ai_response_service):
        """Test sentiment analysis functionality."""
        # Test positive sentiment
        positive_sentiment = ai_response_service._analyze_sentiment(
            "I absolutely love your content! You're amazing!"
        )
        assert positive_sentiment > 0.5
        
        # Test negative sentiment
        negative_sentiment = ai_response_service._analyze_sentiment(
            "I'm disappointed with the recent posts."
        )
        assert negative_sentiment < -0.2
        
        # Test neutral sentiment
        neutral_sentiment = ai_response_service._analyze_sentiment(
            "What time do you usually post?"
        )
        assert -0.2 <= neutral_sentiment <= 0.2
    
    @pytest.mark.asyncio
    async def test_find_similar_responses(self, ai_response_service, mock_db):
        """Test finding similar past responses."""
        # Mock past responses
        mock_suggestions = [
            MagicMock(
                suggested_response="Thanks for your support!",
                was_used=True,
                user_rating=5
            ),
            MagicMock(
                suggested_response="I appreciate your kind words!",
                was_used=True,
                user_rating=4
            )
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_suggestions
        
        # Find similar
        similar = await ai_response_service._find_similar_responses(
            "Thank you so much!",
            model_id=uuid4(),
            agency_id=uuid4(),
            db=mock_db
        )
        
        # Verify
        assert len(similar) > 0
        assert all('response' in s for s in similar)
        assert all('similarity' in s for s in similar)


class TestCannedResponseLibrary:
    """Test canned response functionality."""
    
    @pytest.fixture
    def canned_response_service(self):
        return CannedResponseService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_create_canned_response(self, canned_response_service, mock_db):
        """Test creating a canned response."""
        # Prepare test data
        agency_id = uuid4()
        user_id = uuid4()
        
        response_data = CannedResponseCreate(
            title="Welcome Message",
            content="Welcome to my page! Thanks for subscribing 💕",
            category="greetings",
            tags=["welcome", "new subscriber"],
            shortcuts=["welcome", "hi"]
        )
        
        # Execute
        result = await canned_response_service.create_canned_response(
            response_data, agency_id, user_id, mock_db
        )
        
        # Verify
        assert result.title == "Welcome Message"
        assert result.category == "greetings"
        assert "welcome" in result.tags
        assert len(result.shortcuts) == 2
    
    @pytest.mark.asyncio
    async def test_search_canned_responses(self, canned_response_service, mock_db):
        """Test searching canned responses."""
        # Mock responses
        mock_responses = [
            MagicMock(
                id=uuid4(),
                title="Welcome Message",
                content="Welcome to my page!",
                category="greetings",
                tags=["welcome", "new"],
                use_count=10
            ),
            MagicMock(
                id=uuid4(),
                title="Thank You",
                content="Thank you for your support!",
                category="appreciation",
                tags=["thanks", "support"],
                use_count=5
            )
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_responses
        
        # Search
        results = await canned_response_service.search_canned_responses(
            agency_id=uuid4(),
            search_query="welcome",
            category="greetings",
            db=mock_db
        )
        
        # Verify search was performed
        assert mock_db.execute.called
    
    @pytest.mark.asyncio
    async def test_track_canned_response_usage(self, canned_response_service, mock_db):
        """Test tracking usage of canned responses."""
        # Mock response
        mock_response = MagicMock(
            id=uuid4(),
            use_count=5,
            last_used_at=None
        )
        mock_db.get = AsyncMock(return_value=mock_response)
        
        # Track usage
        await canned_response_service.track_response_usage(
            response_id=mock_response.id,
            agency_id=uuid4(),
            db=mock_db
        )
        
        # Verify
        assert mock_response.use_count == 6
        assert mock_response.last_used_at is not None
        mock_db.commit.assert_called()


class TestAnalyticsExport:
    """Test analytics export functionality."""
    
    @pytest.fixture
    def export_service(self):
        return ExportService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_export_revenue_data_csv(self, export_service, mock_db):
        """Test exporting revenue data as CSV."""
        # Mock revenue data
        mock_revenue = [
            MagicMock(
                date=datetime(2024, 1, 1),
                total_revenue=1000.0,
                subscription_revenue=600.0,
                tip_revenue=200.0,
                ppv_revenue=150.0,
                message_revenue=50.0,
                transaction_count=10,
                model=MagicMock(display_name="Model 1")
            )
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_revenue
        
        # Export
        result = await export_service.export_analytics(
            export_type="revenue",
            format="csv",
            agency_id=uuid4(),
            db=mock_db
        )
        
        # Verify CSV content
        content = result.read().decode('utf-8')
        assert "date,total_revenue" in content
        assert "1000.0" in content
    
    @pytest.mark.asyncio
    async def test_export_fan_data_excel(self, export_service, mock_db):
        """Test exporting fan data as Excel."""
        # Mock fan data
        mock_fans = [
            MagicMock(
                id=uuid4(),
                username="fan1",
                display_name="Fan One",
                subscription_status="active",
                subscribed_at=datetime(2024, 1, 1),
                total_spent=500.0,
                message_count=20,
                last_activity=datetime(2024, 1, 15),
                lifetime_value=600.0,
                tags=["vip", "high-value"],
                model=MagicMock(has=lambda **kwargs: True)
            )
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_fans
        
        # Export
        result = await export_service.export_analytics(
            export_type="fans",
            format="excel",
            agency_id=uuid4(),
            db=mock_db
        )
        
        # Verify Excel file
        assert result.read()  # Should not be empty
        result.seek(0)
        # In real test, would load with openpyxl and verify structure
    
    @pytest.mark.asyncio
    async def test_export_comprehensive_pdf(self, export_service, mock_db):
        """Test exporting comprehensive report as PDF."""
        # Mock various data
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        # Export
        result = await export_service.export_analytics(
            export_type="comprehensive",
            format="pdf",
            agency_id=uuid4(),
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 1, 31),
            db=mock_db
        )
        
        # Verify PDF
        pdf_content = result.read()
        assert pdf_content.startswith(b'%PDF')  # PDF header


class TestReportBuilder:
    """Test custom report builder functionality."""
    
    @pytest.fixture
    def report_builder_service(self):
        return ReportBuilderService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_create_report_template(self, report_builder_service, mock_db):
        """Test creating a custom report template."""
        # Prepare test data
        agency_id = uuid4()
        user_id = uuid4()
        
        template_data = ReportTemplateCreate(
            name="Monthly Revenue Report",
            description="Comprehensive monthly revenue analysis",
            report_type="revenue",
            layout={"columns": 2, "rows": 3},
            widgets=[
                ReportWidgetConfig(
                    type="metric",
                    title="Total Revenue",
                    config={"metric_type": "revenue", "show_comparison": True},
                    position=0,
                    size="large"
                ),
                ReportWidgetConfig(
                    type="chart",
                    title="Revenue Trend",
                    config={"chart_type": "line", "data_source": "revenue"},
                    position=1,
                    size="large"
                )
            ]
        )
        
        # Execute
        result = await report_builder_service.create_report_template(
            template_data, agency_id, user_id, mock_db
        )
        
        # Verify
        assert result.name == "Monthly Revenue Report"
        assert result.report_type == "revenue"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_generate_report_from_template(self, report_builder_service, mock_db):
        """Test generating a report from template."""
        # Mock template with widgets
        mock_template = MagicMock(
            id=uuid4(),
            name="Test Report",
            report_type="revenue",
            widgets=[
                MagicMock(
                    id=uuid4(),
                    widget_type="metric",
                    title="Total Revenue",
                    config={"metric_type": "revenue"},
                    position=0,
                    size="medium"
                )
            ]
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_template
        
        # Mock metric data
        mock_db.execute.return_value.scalar.return_value = 5000.0
        
        # Generate report
        request = ReportGenerateRequest(
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 1, 31),
            format="json"
        )
        
        result = await report_builder_service.generate_report(
            template_id=mock_template.id,
            request=request,
            agency_id=uuid4(),
            user_id=uuid4(),
            db=mock_db
        )
        
        # Verify
        assert result.status == ReportStatus.COMPLETED
        assert result.report_data is not None
        assert "widgets" in result.report_data
    
    @pytest.mark.asyncio
    async def test_duplicate_report_template(self, report_builder_service, mock_db):
        """Test duplicating an existing report template."""
        # Mock original template
        mock_original = MagicMock(
            id=uuid4(),
            name="Original Report",
            description="Original description",
            report_type="revenue",
            layout={"columns": 2},
            filters={},
            widgets=[
                MagicMock(
                    widget_type="metric",
                    title="Revenue",
                    config={},
                    position=0,
                    size="medium"
                )
            ]
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_original
        
        # Duplicate
        result = await report_builder_service.duplicate_template(
            template_id=mock_original.id,
            new_name="Duplicated Report",
            agency_id=uuid4(),
            user_id=uuid4(),
            db=mock_db
        )
        
        # Verify
        assert result.name == "Duplicated Report"
        assert result.report_type == mock_original.report_type
        mock_db.add.assert_called()


class TestScheduledReports:
    """Test scheduled report generation."""
    
    @pytest.fixture
    def scheduled_report_service(self):
        return ScheduledReportService()
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        db.get = AsyncMock()
        return db
    
    @pytest.mark.asyncio
    async def test_create_report_schedule(self, scheduled_report_service, mock_db):
        """Test creating a scheduled report."""
        # Mock template
        mock_template = MagicMock(id=uuid4(), agency_id=uuid4(), is_public=False)
        mock_db.get.return_value = mock_template
        
        # Prepare test data
        agency_id = mock_template.agency_id
        user_id = uuid4()
        
        schedule_data = ReportScheduleCreate(
            name="Weekly Revenue Report",
            description="Automated weekly revenue summary",
            template_id=mock_template.id,
            schedule_type="weekly",
            timezone="UTC",
            parameters=ScheduleParameters(
                date_range_type="last_7_days",
                filters={"model_id": str(uuid4())}
            ),
            delivery_method=DeliveryMethod.EMAIL,
            delivery_config=DeliveryConfig(
                recipients=["report@example.com"]
            )
        )
        
        # Execute
        result = await scheduled_report_service.create_report_schedule(
            schedule_data, agency_id, user_id, mock_db
        )
        
        # Verify
        assert result.name == "Weekly Revenue Report"
        assert result.schedule_type == "weekly"
        assert result.next_run_at is not None
        mock_db.add.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_scheduled_reports(self, scheduled_report_service, mock_db):
        """Test processing due scheduled reports."""
        # Mock due schedules
        mock_schedules = [
            MagicMock(
                id=uuid4(),
                name="Daily Report",
                template_id=uuid4(),
                parameters={"date_range_type": "last_24_hours"},
                delivery_method=DeliveryMethod.EMAIL,
                delivery_config={"recipients": ["test@example.com"]},
                agency_id=uuid4(),
                created_by_id=uuid4(),
                success_count=0,
                failure_count=0
            )
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = mock_schedules
        
        # Mock report generation
        with patch.object(
            scheduled_report_service.report_builder,
            'generate_report',
            return_value=MagicMock(status=ReportStatus.COMPLETED, report_data={})
        ):
            # Process
            await scheduled_report_service.process_scheduled_reports(mock_db)
            
            # Verify
            assert mock_schedules[0].last_run_at is not None
            assert mock_schedules[0].success_count == 1
    
    @pytest.mark.asyncio
    async def test_calculate_next_run_time(self, scheduled_report_service):
        """Test calculating next run time for various schedule types."""
        # Daily schedule
        daily_schedule = MagicMock(
            schedule_type="daily",
            is_active=True,
            last_run_at=datetime(2024, 1, 1, 10, 0)
        )
        next_daily = scheduled_report_service._calculate_next_run(daily_schedule)
        assert next_daily == datetime(2024, 1, 2, 10, 0)
        
        # Weekly schedule
        weekly_schedule = MagicMock(
            schedule_type="weekly",
            is_active=True,
            last_run_at=datetime(2024, 1, 1)
        )
        next_weekly = scheduled_report_service._calculate_next_run(weekly_schedule)
        assert next_weekly == datetime(2024, 1, 8)
        
        # Monthly schedule
        monthly_schedule = MagicMock(
            schedule_type="monthly",
            is_active=True,
            last_run_at=datetime(2024, 1, 15)
        )
        next_monthly = scheduled_report_service._calculate_next_run(monthly_schedule)
        assert next_monthly.month == 2
        
        # Cron schedule
        cron_schedule = MagicMock(
            schedule_type="cron",
            is_active=True,
            cron_expression="0 9 * * 1",  # Every Monday at 9 AM
            last_run_at=datetime(2024, 1, 1, 9, 0)  # Monday
        )
        next_cron = scheduled_report_service._calculate_next_run(cron_schedule)
        assert next_cron.weekday() == 0  # Monday
        assert next_cron.hour == 9


class TestIntegration:
    """Integration tests for Phase 4 features."""
    
    @pytest.mark.asyncio
    async def test_bulk_message_with_ai_suggestions(self):
        """Test bulk messaging integrated with AI suggestions."""
        # This would test the flow of:
        # 1. Creating a bulk campaign
        # 2. Using AI to generate personalized variations
        # 3. Sending messages with rate limiting
        # 4. Tracking delivery and engagement
        pass
    
    @pytest.mark.asyncio
    async def test_scheduled_report_with_export(self):
        """Test scheduled report generation with multiple export formats."""
        # This would test:
        # 1. Creating a custom report template
        # 2. Scheduling the report
        # 3. Generating report at scheduled time
        # 4. Exporting in multiple formats (CSV, Excel, PDF)
        # 5. Delivering via configured method
        pass
    
    @pytest.mark.asyncio
    async def test_canned_response_with_analytics(self):
        """Test canned responses with usage analytics."""
        # This would test:
        # 1. Creating canned responses
        # 2. Using them in conversations
        # 3. Tracking usage statistics
        # 4. Analyzing effectiveness
        # 5. Generating reports on response performance
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
