"""
Tests for the advanced reporting system.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from core.reporting.models import (
    Report, ReportExecution, ReportTemplate,
    ReportType, ReportFormat, ReportStatus
)
from core.reporting.report_builder import report_builder
from core.reporting.exporters import export_manager
from core.domain.models import User, Agency


class TestReportBuilder:
    """Test report builder functionality."""
    
    @pytest.mark.asyncio
    async def test_create_report(self, db_session: AsyncSession, test_user: User):
        """Test creating a new report."""
        # Create report
        report = await report_builder.create_report(
            name="Test Revenue Report",
            report_type=ReportType.REVENUE,
            query_config={
                "table": "transactions",
                "date_field": "created_at"
            },
            user=test_user,
            session=db_session,
            description="Test report description",
            filters={"status": {"operator": "=", "value": "completed"}},
            columns=["date", "revenue", "transaction_count"]
        )
        
        assert report.id is not None
        assert report.name == "Test Revenue Report"
        assert report.report_type == ReportType.REVENUE
        assert report.created_by_id == test_user.id
        assert report.agency_id == test_user.agency_id
    
    @pytest.mark.asyncio
    async def test_execute_report(self, db_session: AsyncSession, test_user: User):
        """Test executing a report."""
        # Create report first
        report = await report_builder.create_report(
            name="Test Report",
            report_type=ReportType.REVENUE,
            query_config={"custom_query": "SELECT 1 as test"},
            user=test_user,
            session=db_session
        )
        
        # Execute report
        execution = await report_builder.execute_report(
            report_id=str(report.id),
            format=ReportFormat.JSON,
            user=test_user,
            session=db_session
        )
        
        assert execution.id is not None
        assert execution.report_id == report.id
        assert execution.format == ReportFormat.JSON
        assert execution.executed_by_id == test_user.id
    
    @pytest.mark.asyncio
    async def test_create_from_template(self, db_session: AsyncSession, test_user: User):
        """Test creating report from template."""
        # Create template
        template = ReportTemplate(
            name="Revenue Template",
            category="financial",
            report_type=ReportType.REVENUE,
            base_query="SELECT * FROM transactions",
            default_filters={"status": {"operator": "=", "value": "completed"}},
            default_columns=["date", "amount"],
            is_system=True
        )
        db_session.add(template)
        await db_session.commit()
        
        # Create report from template
        report = await report_builder.create_from_template(
            template_id=str(template.id),
            name="My Revenue Report",
            user=test_user,
            session=db_session,
            customizations={
                "filters": {"date_range": {"operator": "between", "value": ["2024-01-01", "2024-12-31"]}}
            }
        )
        
        assert report.name == "My Revenue Report"
        assert report.report_type == ReportType.REVENUE
        assert "date_range" in report.filters
    
    @pytest.mark.asyncio
    async def test_share_report(self, db_session: AsyncSession, test_user: User, test_user2: User):
        """Test sharing a report."""
        # Create report
        report = await report_builder.create_report(
            name="Shared Report",
            report_type=ReportType.REVENUE,
            query_config={},
            user=test_user,
            session=db_session
        )
        
        # Share report
        success = await report_builder.share_report(
            report_id=str(report.id),
            user_ids=[str(test_user2.id)],
            permission="view",
            shared_by=test_user,
            session=db_session
        )
        
        assert success is True
        
        # Verify access
        can_access = await report_builder._can_access_report(
            report,
            test_user2,
            db_session
        )
        assert can_access is True
    
    @pytest.mark.asyncio
    async def test_query_building(self):
        """Test SQL query building."""
        report = Report(
            name="Test",
            report_type=ReportType.REVENUE,
            query_config={"custom_query": "SELECT * FROM transactions"},
            filters={
                "status": {"operator": "=", "value": "completed"},
                "amount": {"operator": ">", "value": 100}
            },
            grouping=["date", "platform"],
            sorting={"date": "desc", "amount": "asc"}
        )
        
        query = report_builder._build_query(report)
        
        assert "WHERE" in query
        assert "status = 'completed'" in query
        assert "amount > '100'" in query
        assert "GROUP BY date, platform" in query
        assert "ORDER BY date DESC, amount ASC" in query
        assert "LIMIT" in query
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self):
        """Test cache key generation."""
        report = Report(id=uuid4())
        parameters = {"date_range": "last_30_days"}
        
        key1 = report_builder._generate_cache_key(report, parameters, ReportFormat.CSV)
        key2 = report_builder._generate_cache_key(report, parameters, ReportFormat.CSV)
        key3 = report_builder._generate_cache_key(report, parameters, ReportFormat.PDF)
        
        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different format = different key


class TestReportExporters:
    """Test report export functionality."""
    
    @pytest.mark.asyncio
    async def test_csv_export(self):
        """Test CSV export."""
        data = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "revenue": [1000, 1500],
            "transactions": [10, 15]
        })
        
        buffer = await export_manager.export(
            data=data,
            format="csv",
            report_name="Test Report",
            metadata={"period": "January 2024"}
        )
        
        content = buffer.read().decode('utf-8')
        assert "date,revenue,transactions" in content
        assert "2024-01-01,1000,10" in content
    
    @pytest.mark.asyncio
    async def test_json_export(self):
        """Test JSON export."""
        data = pd.DataFrame({
            "metric": ["Revenue", "Users"],
            "value": [50000, 1200]
        })
        
        buffer = await export_manager.export(
            data=data,
            format="json",
            report_name="Metrics Report"
        )
        
        import json
        content = json.loads(buffer.read().decode('utf-8'))
        
        assert "report" in content
        assert content["report"]["name"] == "Metrics Report"
        assert "data" in content
        assert len(content["data"]) == 2
    
    @pytest.mark.asyncio
    async def test_excel_export(self):
        """Test Excel export."""
        data = pd.DataFrame({
            "model": ["Model A", "Model B"],
            "revenue": [25000, 35000],
            "percentage": [41.67, 58.33]
        })
        
        buffer = await export_manager.export(
            data=data,
            format="excel",
            report_name="Model Performance",
            metadata={"include_summary": True}
        )
        
        # Verify it's a valid Excel file
        assert buffer.tell() > 0
        buffer.seek(0)
        # Excel files start with PK (ZIP format)
        assert buffer.read(2) == b'PK'
    
    @pytest.mark.asyncio
    async def test_html_export(self):
        """Test HTML export."""
        data = pd.DataFrame({
            "date": ["2024-01-01"],
            "visitors": [1500]
        })
        
        buffer = await export_manager.export(
            data=data,
            format="html",
            report_name="Traffic Report"
        )
        
        content = buffer.read().decode('utf-8')
        assert "<html>" in content
        assert "Traffic Report" in content
        assert "<table" in content
        assert "2024-01-01" in content
    
    @pytest.mark.asyncio
    async def test_pdf_export(self):
        """Test PDF export."""
        data = pd.DataFrame({
            "category": ["Tips", "Messages", "Subscriptions"],
            "amount": [5000, 3000, 12000]
        })
        
        buffer = await export_manager.export(
            data=data,
            format="pdf",
            report_name="Revenue Breakdown",
            metadata={"period": "Q1 2024"},
            charts=[{
                "type": "bar",
                "x_column": "category",
                "y_column": "amount",
                "title": "Revenue by Category"
            }]
        )
        
        # PDF files start with %PDF
        assert buffer.tell() > 0
        buffer.seek(0)
        assert buffer.read(4) == b'%PDF'


class TestReportAPI:
    """Test report API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_report_endpoint(self, client, auth_headers):
        """Test creating report via API."""
        response = await client.post(
            "/api/v1/reports/",
            json={
                "name": "API Test Report",
                "report_type": "revenue",
                "query_config": {"table": "transactions"},
                "cache_duration_minutes": 30
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "API Test Report"
        assert data["report_type"] == "revenue"
    
    @pytest.mark.asyncio
    async def test_list_reports_endpoint(self, client, auth_headers):
        """Test listing reports."""
        response = await client.get(
            "/api/v1/reports/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_execute_report_endpoint(self, client, auth_headers, test_report):
        """Test executing report via API."""
        response = await client.post(
            f"/api/v1/reports/{test_report.id}/execute",
            json={
                "format": "json",
                "use_cache": True
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["format"] == "json"
        assert data["status"] in ["pending", "generating", "completed"]
    
    @pytest.mark.asyncio
    async def test_preview_report_endpoint(self, client, auth_headers, test_report):
        """Test report preview."""
        response = await client.get(
            f"/api/v1/reports/{test_report.id}/preview?limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "columns" in data
        assert "data" in data
        assert "total_rows" in data
    
    @pytest.mark.asyncio
    async def test_share_report_endpoint(self, client, auth_headers, test_report, test_user2):
        """Test sharing report via API."""
        response = await client.post(
            f"/api/v1/reports/{test_report.id}/share",
            json={
                "user_ids": [str(test_user2.id)],
                "permission": "view"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "shared with 1 users" in data["message"]
    
    @pytest.mark.asyncio
    async def test_list_templates_endpoint(self, client, auth_headers):
        """Test listing report templates."""
        response = await client.get(
            "/api/v1/reports/templates",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_report_statistics_endpoint(self, client, admin_headers):
        """Test report statistics endpoint."""
        response = await client.get(
            "/api/v1/reports/statistics/usage?days=7",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_reports" in data
        assert "total_executions" in data
        assert "popular_reports" in data
        assert data["time_range_days"] == 7
