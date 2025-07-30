"""Reports endpoints for analytics and business intelligence."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel, Field
import io

from core.dependencies import get_db, get_current_user
from models.user import User
from core.application.reports_service import ReportsService
from core.exceptions import ValidationError, PermissionError

router = APIRouter()


# Request/Response schemas
class RevenueReportRequest(BaseModel):
    """Revenue report request."""
    start_date: date
    end_date: date
    group_by: str = Field("day", pattern="^(day|week|month)$")


class PerformanceReportRequest(BaseModel):
    """Performance report request."""
    start_date: date
    end_date: date


class CustomReportRequest(BaseModel):
    """Custom report request."""
    report_type: str = Field(..., pattern="^(conversion|retention|growth)$")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    """Generic report response."""
    report_type: str
    generated_at: str
    data: Dict[str, Any]


@router.post("/revenue", response_model=ReportResponse)
async def generate_revenue_report(
    request: RevenueReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportResponse:
    """
    Generate revenue report for the agency.
    
    - Shows revenue by time period
    - Includes platform fees and net revenue
    - Lists top performing models
    - Requires manager access or higher
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for revenue reports")
    
    try:
        report_data = await ReportsService.generate_revenue_report(
            db=db,
            agency_id=current_user.agency_id,
            start_date=request.start_date,
            end_date=request.end_date,
            group_by=request.group_by
        )
        
        return ReportResponse(
            report_type="revenue",
            generated_at=datetime.utcnow().isoformat(),
            data=report_data
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/performance", response_model=ReportResponse)
async def generate_performance_report(
    request: PerformanceReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportResponse:
    """
    Generate performance report for the agency.
    
    - Message statistics and response times
    - Content performance by type
    - Model activity and engagement scores
    - Requires manager access or higher
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for performance reports")
    
    try:
        report_data = await ReportsService.generate_performance_report(
            db=db,
            agency_id=current_user.agency_id,
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        return ReportResponse(
            report_type="performance",
            generated_at=datetime.utcnow().isoformat(),
            data=report_data
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/custom", response_model=ReportResponse)
async def generate_custom_report(
    request: CustomReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ReportResponse:
    """
    Generate custom report based on type.
    
    Available report types:
    - conversion: Fan conversion funnel analysis
    - retention: Fan retention cohort analysis
    - growth: Growth metrics and trends
    
    Requires manager access or higher
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for custom reports")
    
    try:
        report_data = await ReportsService.generate_custom_report(
            db=db,
            agency_id=current_user.agency_id,
            report_type=request.report_type,
            parameters=request.parameters
        )
        
        return ReportResponse(
            report_type=request.report_type,
            generated_at=datetime.utcnow().isoformat(),
            data=report_data
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary")
async def get_report_summary(
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get quick summary of key metrics.
    
    - Revenue summary
    - Activity summary
    - Top performers
    - Available to all users
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)
    
    # Get basic metrics (simplified for all users)
    try:
        # Revenue summary (if user has access)
        revenue_summary = {}
        if current_user.role in ["admin", "owner", "manager"]:
            revenue_data = await ReportsService.generate_revenue_report(
                db=db,
                agency_id=current_user.agency_id,
                start_date=start_date,
                end_date=end_date,
                group_by="month"
            )
            revenue_summary = revenue_data.get("summary", {})
        
        # Performance summary
        performance_data = await ReportsService.generate_performance_report(
            db=db,
            agency_id=current_user.agency_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": period_days
            },
            "revenue": revenue_summary,
            "activity": performance_data.get("messaging", {}),
            "content": performance_data.get("content", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")


@router.post("/export/{report_type}")
async def export_report(
    report_type: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Export report in specified format.
    
    - Supports JSON and CSV formats
    - Requires manager access or higher
    """
    # Check permissions
    if current_user.role not in ["admin", "owner", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions for report export")
    
    try:
        # Generate report based on type
        if report_type == "revenue":
            report_data = await ReportsService.generate_revenue_report(
                db=db,
                agency_id=current_user.agency_id,
                start_date=start_date,
                end_date=end_date,
                group_by="day"
            )
        elif report_type == "performance":
            report_data = await ReportsService.generate_performance_report(
                db=db,
                agency_id=current_user.agency_id,
                start_date=start_date,
                end_date=end_date
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")
        
        # Export report
        content, content_type = await ReportsService.export_report(report_data, format)
        
        # Create response
        filename = f"{report_type}_report_{start_date}_{end_date}.{format}"
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/available")
async def get_available_reports(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get list of available reports based on user role."""
    base_reports = ["performance_summary"]
    
    if current_user.role in ["admin", "owner", "manager"]:
        base_reports.extend([
            "revenue",
            "performance",
            "conversion",
            "retention",
            "growth"
        ])
    
    return {
        "available_reports": base_reports,
        "user_role": current_user.role,
        "export_formats": ["json", "csv"]
    }