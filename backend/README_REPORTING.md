# Advanced Reporting System

## Overview

The Advanced Reporting System provides comprehensive reporting capabilities for the agency platform, including custom report building, multiple export formats, scheduling, and sharing features.

## Features

### 1. Report Types
- **Revenue Reports**: Track revenue by model, platform, and time period
- **User Activity Reports**: Monitor user engagement and activity metrics
- **Model Performance Reports**: Analyze model performance and earnings
- **Transaction Reports**: Detailed transaction history and analysis
- **Payout Reports**: Track payouts to models and payment methods
- **Engagement Reports**: Measure fan engagement and retention
- **Conversion Reports**: Track conversion rates and funnel analysis
- **Custom Reports**: Build custom reports with flexible queries
- **Executive Reports**: High-level dashboards for executives

### 2. Export Formats
- **PDF**: Professional reports with charts and formatting
- **Excel**: Interactive spreadsheets with multiple sheets
- **CSV**: Simple data export for analysis
- **JSON**: Structured data for API integration
- **HTML**: Interactive web-based reports

### 3. Key Features
- Custom report builder with drag-and-drop interface
- Real-time data processing
- Report scheduling and automation
- Report sharing with permission controls
- Report templates for quick setup
- Caching for performance optimization
- Audit logging for compliance

## Architecture

### Components

1. **Report Builder Service** (`core/reporting/report_builder.py`)
   - Creates and manages report definitions
   - Executes reports and generates data
   - Handles caching and performance optimization

2. **Export Manager** (`core/reporting/exporters.py`)
   - Handles all export formats
   - Generates formatted outputs
   - Manages file generation and storage

3. **Models** (`core/reporting/models.py`)
   - Report: Report definition and configuration
   - ReportExecution: Individual report runs
   - ReportSchedule: Scheduled report generation
   - ReportTemplate: Pre-built templates
   - ReportWidget: Dashboard widgets
   - ReportCache: Performance caching
   - ReportAuditLog: Audit trail

4. **API Endpoints** (`api/v1/endpoints/reports.py`)
   - Full REST API for report management
   - Execution and export endpoints
   - Sharing and scheduling features

## Usage Examples

### Creating a Report

```python
from core.reporting.report_builder import report_builder
from core.reporting.models import ReportType

# Create a revenue report
report = await report_builder.create_report(
    name="Monthly Revenue Report",
    report_type=ReportType.REVENUE,
    query_config={
        "date_field": "created_at",
        "aggregation": "sum",
        "group_by": ["model_id", "platform"]
    },
    user=current_user,
    session=db,
    filters={
        "date_range": {
            "operator": "between",
            "value": ["2024-01-01", "2024-01-31"]
        }
    },
    columns=["model_name", "platform", "revenue", "transaction_count"],
    sorting={"revenue": "desc"}
)
```

### Executing a Report

```python
from core.reporting.models import ReportFormat

# Execute report in different formats
execution = await report_builder.execute_report(
    report_id=report.id,
    format=ReportFormat.PDF,
    user=current_user,
    session=db,
    parameters={
        "include_charts": True,
        "include_summary": True
    }
)

# Get execution results
if execution.status == ReportStatus.COMPLETED:
    download_url = f"/api/v1/reports/executions/{execution.id}/download"
```

### Creating from Template

```python
# Use a pre-built template
report = await report_builder.create_from_template(
    template_id=template_id,
    name="Q1 2024 Revenue Report",
    user=current_user,
    session=db,
    customizations={
        "filters": {
            "quarter": "Q1",
            "year": 2024
        }
    }
)
```

### Scheduling Reports

```python
# Schedule daily report
schedule = await report_builder.schedule_report(
    report_id=report.id,
    cron_expression="0 9 * * *",  # Daily at 9 AM
    format=ReportFormat.EXCEL,
    delivery_config={
        "method": "email",
        "recipients": ["manager@agency.com"]
    },
    user=current_user,
    session=db
)
```

### Sharing Reports

```python
# Share with other users
await report_builder.share_report(
    report_id=report.id,
    user_ids=[user1.id, user2.id],
    permission="view",
    shared_by=current_user,
    session=db
)
```

## API Endpoints

### Report Management
- `POST /api/v1/reports/` - Create new report
- `GET /api/v1/reports/` - List reports
- `GET /api/v1/reports/{id}` - Get report details
- `PUT /api/v1/reports/{id}` - Update report
- `DELETE /api/v1/reports/{id}` - Delete report

### Report Execution
- `POST /api/v1/reports/{id}/execute` - Execute report
- `GET /api/v1/reports/{id}/preview` - Preview report data
- `GET /api/v1/reports/executions/{id}` - Get execution status
- `GET /api/v1/reports/executions/{id}/download` - Download report

### Templates and Sharing
- `GET /api/v1/reports/templates` - List templates
- `POST /api/v1/reports/from-template` - Create from template
- `POST /api/v1/reports/{id}/share` - Share report
- `POST /api/v1/reports/{id}/schedule` - Schedule report

### Statistics
- `GET /api/v1/reports/statistics/usage` - Usage statistics

## Report Templates

The system includes pre-built templates:

1. **Financial Templates**
   - Daily Revenue Report
   - Monthly Revenue Summary
   - Transaction Detail Report
   - Payout Summary

2. **Analytics Templates**
   - User Engagement Report
   - Chatter Performance
   - Model Performance Dashboard
   - Top Models Report

3. **Executive Templates**
   - Executive Dashboard
   - KPI Summary
   - Growth Metrics

## Performance Optimization

### Caching
- Reports are cached based on parameters
- Cache duration is configurable per report
- Cache hit/miss tracking for optimization

### Query Optimization
- Automatic index suggestions
- Query analysis and optimization
- Batch processing for large datasets

### Async Processing
- Reports execute asynchronously
- Background tasks for large reports
- Real-time status updates

## Security

### Access Control
- Role-based permissions
- Report sharing with granular permissions
- Agency-level isolation

### Audit Trail
- All report actions are logged
- User access tracking
- Compliance reporting

## Configuration

### Environment Variables
```bash
# Report storage
REPORT_STORAGE_PATH=/var/reports
REPORT_MAX_SIZE_MB=100

# Cache settings
REPORT_CACHE_DURATION_MINUTES=60
REPORT_CACHE_MAX_SIZE_MB=1000

# Export settings
REPORT_PDF_PAGE_SIZE=letter
REPORT_EXCEL_MAX_ROWS=1000000
```

## Testing

```bash
# Run report tests
pytest tests/test_reporting.py -v

# Test specific components
pytest tests/test_reporting.py::TestReportBuilder -v
pytest tests/test_reporting.py::TestReportExporters -v
```

## Troubleshooting

### Common Issues

1. **Report execution fails**
   - Check query syntax
   - Verify database permissions
   - Check available memory

2. **Export fails**
   - Verify export dependencies (reportlab, openpyxl)
   - Check disk space
   - Verify file permissions

3. **Performance issues**
   - Enable caching
   - Add database indexes
   - Limit result set size

## Future Enhancements

1. **Advanced Analytics**
   - Machine learning predictions
   - Trend analysis
   - Anomaly detection

2. **Visualization**
   - Interactive dashboards
   - Real-time charts
   - Custom widgets

3. **Integration**
   - External data sources
   - Third-party BI tools
   - API webhooks
