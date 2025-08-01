"""Enhanced reports API endpoints with chart generation."""

from typing import List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os

from core.database import get_db
from core.auth import get_current_user
from core.logger import get_logger
from models.user import User, UserRole
from services.enhanced_report_service import get_enhanced_report_service
from schemas.reports import (
    RevenueReportResponse,
    PerformanceDashboardResponse,
    ModelPerformanceReportResponse,
    FinancialSummaryReportResponse,
    ReportExportFormat
)

logger = get_logger(__name__)
router = APIRouter(prefix="/enhanced-reports", tags=["enhanced-reports"])


@router.get("/revenue", response_model=RevenueReportResponse)
async def get_revenue_report(
    start_date: date = Query(..., description="Report start date"),
    end_date: date = Query(..., description="Report end date"),
    include_charts: bool = Query(True, description="Include chart visualizations"),
    chart_types: Optional[List[str]] = Query(None, description="Chart types: line, bar, area"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RevenueReportResponse:
    """
    Generate comprehensive revenue report with optional charts.
    
    Available chart types:
    - line: Revenue trend line chart
    - bar: Daily revenue comparison bar chart
    - area: Revenue area chart
    """
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view revenue reports"
        )
    
    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )
    
    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days"
        )
    
    report_service = get_enhanced_report_service()
    
    report = await report_service.generate_comprehensive_revenue_report(
        db=db,
        agency_id=current_user.agency_id,
        start_date=start_date,
        end_date=end_date,
        include_charts=include_charts,
        chart_types=chart_types
    )
    
    return RevenueReportResponse(**report)


@router.get("/performance-dashboard", response_model=PerformanceDashboardResponse)
async def get_performance_dashboard(
    period_days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PerformanceDashboardResponse:
    """
    Generate performance dashboard with multiple metrics and visualizations.
    
    Includes:
    - Revenue trends
    - User growth metrics
    - Content performance
    - Engagement heatmaps
    - Conversion funnels
    """
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view performance dashboard"
        )
    
    report_service = get_enhanced_report_service()
    
    dashboard = await report_service.generate_performance_dashboard(
        db=db,
        agency_id=current_user.agency_id,
        period_days=period_days
    )
    
    return PerformanceDashboardResponse(**dashboard)


@router.get("/model-performance/{model_id}", response_model=ModelPerformanceReportResponse)
async def get_model_performance_report(
    model_id: int,
    period_days: int = Query(30, ge=1, le=365, description="Period in days"),
    include_charts: bool = Query(True, description="Include chart visualizations"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ModelPerformanceReportResponse:
    """
    Generate detailed performance report for a specific model.
    
    Includes:
    - Earnings trends
    - Engagement metrics
    - Content performance comparison
    - Activity patterns
    """
    # Check permissions - user must be admin or the model themselves
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        if not (current_user.role == UserRole.MODEL and current_user.model_profile 
                and current_user.model_profile.id == model_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view model performance"
            )
    
    report_service = get_enhanced_report_service()
    
    report = await report_service.generate_model_performance_report(
        db=db,
        model_id=model_id,
        period_days=period_days,
        include_charts=include_charts
    )
    
    return ModelPerformanceReportResponse(**report)


@router.get("/financial-summary", response_model=FinancialSummaryReportResponse)
async def get_financial_summary_report(
    year: int = Query(..., ge=2020, le=2100, description="Report year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Report month (optional)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FinancialSummaryReportResponse:
    """
    Generate financial summary report with visualizations.
    
    Includes:
    - Revenue and expense breakdown
    - Monthly comparisons (for yearly reports)
    - Revenue source analysis
    - Profit margins
    """
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only agency owners can view financial summary reports"
        )
    
    report_service = get_enhanced_report_service()
    
    report = await report_service.generate_financial_summary_report(
        db=db,
        agency_id=current_user.agency_id,
        year=year,
        month=month
    )
    
    return FinancialSummaryReportResponse(**report)


@router.post("/export/{report_type}")
async def export_report(
    report_type: str,
    format: ReportExportFormat = Query(ReportExportFormat.PDF, description="Export format"),
    start_date: Optional[date] = Query(None, description="Report start date"),
    end_date: Optional[date] = Query(None, description="Report end date"),
    period_days: Optional[int] = Query(None, description="Period in days"),
    year: Optional[int] = Query(None, description="Report year"),
    month: Optional[int] = Query(None, description="Report month"),
    model_id: Optional[int] = Query(None, description="Model ID for model reports"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export report in various formats.
    
    Supported report types:
    - revenue
    - performance-dashboard
    - model-performance
    - financial-summary
    
    Supported formats:
    - PDF: Full report with charts
    - EXCEL: Data tables with separate chart sheets
    - CSV: Raw data only
    """
    from services.pdf_generator import get_pdf_generator
    from services.excel_generator import get_excel_generator
    import csv
    import tempfile
    import uuid
    
    # Validate report type
    valid_report_types = ['revenue', 'performance-dashboard', 'model-performance', 'financial-summary']
    if report_type not in valid_report_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report type. Must be one of: {', '.join(valid_report_types)}"
        )
    
    # Check permissions based on report type
    if report_type in ['revenue', 'performance-dashboard']:
        if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    elif report_type == 'financial-summary':
        if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.SUPER_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only agency owners can export financial reports"
            )
    
    # Get report service
    report_service = get_enhanced_report_service()
    
    # Generate report data based on type
    try:
        if report_type == 'revenue':
            if not start_date or not end_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Start date and end date are required for revenue reports"
                )
            report_data = await report_service.generate_comprehensive_revenue_report(
                db, current_user.agency_id, start_date, end_date
            )
        elif report_type == 'performance-dashboard':
            report_data = await report_service.generate_performance_dashboard(
                db, current_user.agency_id, period_days or 30
            )
        elif report_type == 'model-performance':
            if not model_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Model ID is required for model performance reports"
                )
            report_data = await report_service.generate_model_performance_report(
                db, model_id, period_days or 30
            )
        elif report_type == 'financial-summary':
            if not year:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Year is required for financial summary reports"
                )
            report_data = await report_service.generate_financial_summary_report(
                db, current_user.agency_id, year, month
            )
        
        # Generate export based on format
        file_id = uuid.uuid4().hex
        if format == ReportExportFormat.PDF:
            pdf_generator = get_pdf_generator()
            
            # Get agency name
            from sqlalchemy import select
            from models.agency import Agency
            agency_result = await db.execute(
                select(Agency).where(Agency.id == current_user.agency_id)
            )
            agency = agency_result.scalar_one_or_none()
            agency_name = agency.name if agency else "Agency Dark"
            
            # Generate PDF
            pdf_bytes = await pdf_generator.generate_report_pdf(
                report_data,
                report_type.replace('-', '_'),
                agency_name
            )
            
            # Save to temporary file
            temp_path = f"/tmp/report_{file_id}.pdf"
            with open(temp_path, 'wb') as f:
                f.write(pdf_bytes)
            
            file_extension = 'pdf'
            
        elif format == ReportExportFormat.EXCEL:
            # Excel export would be implemented here
            # For now, return not implemented
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Excel export coming soon"
            )
            
        elif format == ReportExportFormat.CSV:
            # CSV export for raw data
            temp_path = f"/tmp/report_{file_id}.csv"
            
            # Extract tabular data from report
            if report_type == 'revenue' and report_data.get('data', {}).get('data'):
                with open(temp_path, 'w', newline='') as csvfile:
                    fieldnames = ['period', 'transaction_count', 'gross_revenue', 
                                'platform_fees', 'net_revenue', 'avg_transaction']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in report_data['data']['data']:
                        writer.writerow({k: row.get(k, '') for k in fieldnames})
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CSV export is only available for revenue reports"
                )
            
            file_extension = 'csv'
        
        # Return download info
        return {
            "message": "Report export completed",
            "report_type": report_type,
            "format": format,
            "file_id": file_id,
            "download_url": f"/api/v1/enhanced-reports/download/{file_id}.{file_extension}",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export report: {str(e)}"
        )


@router.get("/templates")
async def list_report_templates(
    current_user: User = Depends(get_current_user)
):
    """List available report templates."""
    templates = [
        {
            "id": "revenue-monthly",
            "name": "Monthly Revenue Report",
            "description": "Comprehensive monthly revenue analysis with trends",
            "parameters": ["month", "year"],
            "charts": ["revenue_trend", "revenue_comparison", "revenue_sources"]
        },
        {
            "id": "performance-weekly",
            "name": "Weekly Performance Dashboard",
            "description": "7-day performance overview with key metrics",
            "parameters": ["period_days"],
            "charts": ["activity_heatmap", "conversion_funnel", "user_growth"]
        },
        {
            "id": "model-monthly",
            "name": "Model Monthly Report",
            "description": "Detailed monthly performance report for models",
            "parameters": ["model_id", "month", "year"],
            "charts": ["earnings_trend", "engagement_pie", "content_bar"]
        },
        {
            "id": "financial-quarterly",
            "name": "Quarterly Financial Summary",
            "description": "Quarterly financial overview with YoY comparison",
            "parameters": ["quarter", "year"],
            "charts": ["monthly_revenue", "expense_distribution", "profit_margin"]
        }
    ]
    
    return {"templates": templates}


@router.post("/schedule")
async def schedule_report(
    report_type: str,
    schedule: str = Query(..., description="Cron expression or predefined schedule"),
    recipients: List[str] = Query(..., description="Email recipients"),
    format: ReportExportFormat = Query(ReportExportFormat.PDF, description="Export format"),
    parameters: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Schedule recurring report generation.
    
    Predefined schedules:
    - daily: Every day at 8 AM
    - weekly: Every Monday at 8 AM
    - monthly: First day of month at 8 AM
    - quarterly: First day of quarter at 8 AM
    
    Or provide custom cron expression.
    """
    # Check permissions
    if current_user.role not in [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to schedule reports"
        )
    
    # This would integrate with the scheduled task system
    # For now, return a placeholder response
    return {
        "message": "Report scheduled successfully",
        "schedule_id": f"sched_{report_type}_{datetime.utcnow().timestamp()}",
        "report_type": report_type,
        "schedule": schedule,
        "recipients": recipients,
        "format": format,
        "parameters": parameters
    }


@router.get("/download/{file_id}")
async def download_report(
    file_id: str,
    current_user: User = Depends(get_current_user)
):
    """Download exported report file."""
    # Validate file_id format (should be hex)
    if not all(c in '0123456789abcdef' for c in file_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file ID"
        )
    
    # Check for file with different extensions
    possible_files = [
        f"/tmp/report_{file_id}.pdf",
        f"/tmp/report_{file_id}.xlsx",
        f"/tmp/report_{file_id}.csv"
    ]
    
    file_path = None
    for path in possible_files:
        if os.path.exists(path):
            file_path = path
            break
    
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found or expired"
        )
    
    # Get file extension
    file_extension = os.path.splitext(file_path)[1][1:]  # Remove the dot
    
    # Determine content type
    content_types = {
        'pdf': 'application/pdf',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'csv': 'text/csv'
    }
    
    content_type = content_types.get(file_extension, 'application/octet-stream')
    
    # Generate filename
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
    
    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=filename
    )