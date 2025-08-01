"""Schemas for enhanced reports."""

from typing import Dict, Any, List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field
from enum import Enum


class ReportExportFormat(str, Enum):
    """Report export formats."""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"


class ChartData(BaseModel):
    """Chart data in base64 format."""
    revenue_trend: Optional[str] = Field(None, description="Revenue trend chart")
    revenue_comparison: Optional[str] = Field(None, description="Revenue comparison chart")
    revenue_area: Optional[str] = Field(None, description="Revenue area chart")
    user_growth: Optional[str] = Field(None, description="User growth chart")
    content_distribution: Optional[str] = Field(None, description="Content distribution chart")
    activity_heatmap: Optional[str] = Field(None, description="Activity heatmap")
    conversion_funnel: Optional[str] = Field(None, description="Conversion funnel chart")
    earnings_trend: Optional[str] = Field(None, description="Earnings trend chart")
    engagement_pie: Optional[str] = Field(None, description="Engagement pie chart")
    content_bar: Optional[str] = Field(None, description="Content performance bar chart")
    monthly_revenue: Optional[str] = Field(None, description="Monthly revenue comparison")
    expense_distribution: Optional[str] = Field(None, description="Expense distribution chart")
    revenue_sources: Optional[str] = Field(None, description="Revenue sources chart")


class RevenueDataPoint(BaseModel):
    """Single revenue data point."""
    period: str
    transaction_count: int
    gross_revenue: float
    platform_fees: float
    net_revenue: float
    avg_transaction: float
    currencies: List[str]


class RevenueSummary(BaseModel):
    """Revenue summary statistics."""
    total_gross: float
    total_net: float
    total_fees: float
    total_transactions: int
    avg_daily_revenue: float
    growth_rate: Optional[float]
    top_revenue_day: Optional[str]
    currency_breakdown: Dict[str, float]


class RevenueReportData(BaseModel):
    """Revenue report data."""
    data: List[RevenueDataPoint]
    summary: RevenueSummary


class RevenueReportResponse(BaseModel):
    """Revenue report response with optional charts."""
    agency_id: int
    period: Dict[str, str]
    data: RevenueReportData
    charts: Optional[ChartData] = None
    generated_at: str


class MetricData(BaseModel):
    """Generic metric data."""
    total: Optional[float] = None
    change: Optional[float] = None
    trend: Optional[List[Dict[str, Any]]] = None


class PerformanceMetrics(BaseModel):
    """Performance dashboard metrics."""
    revenue: Dict[str, Any]
    users: Dict[str, Any]
    content: Dict[str, Any]
    engagement: Dict[str, Any]


class PerformanceDashboardResponse(BaseModel):
    """Performance dashboard response."""
    agency_id: int
    period: Dict[str, Any]
    metrics: PerformanceMetrics
    charts: ChartData
    generated_at: str


class ModelPerformanceData(BaseModel):
    """Model performance data."""
    earnings_summary: Dict[str, float]
    content_stats: Dict[str, int]
    engagement_metrics: Dict[str, float]
    daily_earnings: Optional[List[Dict[str, Any]]] = None
    content_performance: Optional[List[Dict[str, Any]]] = None
    top_content: Optional[List[Dict[str, Any]]] = None


class ModelPerformanceReportResponse(BaseModel):
    """Model performance report response."""
    model_id: int
    period_days: int
    data: ModelPerformanceData
    charts: Optional[ChartData] = None
    generated_at: str


class FinancialBreakdown(BaseModel):
    """Financial breakdown data."""
    revenue: Dict[str, float]
    expenses: Dict[str, float]
    profit: Dict[str, float]
    margins: Dict[str, float]


class FinancialSummaryData(BaseModel):
    """Financial summary data."""
    summary: FinancialBreakdown
    monthly_breakdown: Optional[List[Dict[str, Any]]] = None
    expense_breakdown: Optional[Dict[str, float]] = None
    revenue_sources: Optional[List[Dict[str, Any]]] = None
    tax_summary: Optional[Dict[str, float]] = None


class FinancialSummaryReportResponse(BaseModel):
    """Financial summary report response."""
    agency_id: int
    period: Dict[str, Any]
    financial_data: FinancialSummaryData
    charts: ChartData
    generated_at: str


class ReportSchedule(BaseModel):
    """Report schedule configuration."""
    report_type: str
    schedule: str
    recipients: List[str]
    format: ReportExportFormat
    parameters: Dict[str, Any]
    is_active: bool = True


class ReportTemplate(BaseModel):
    """Report template definition."""
    id: str
    name: str
    description: str
    parameters: List[str]
    charts: List[str]
    default_format: ReportExportFormat = ReportExportFormat.PDF


class ExportRequest(BaseModel):
    """Report export request."""
    report_type: str
    format: ReportExportFormat
    parameters: Dict[str, Any]
    include_raw_data: bool = False
    compress: bool = True


class ExportResponse(BaseModel):
    """Report export response."""
    export_id: str
    status: str
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    file_size: Optional[int] = None