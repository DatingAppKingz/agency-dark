"""
Analytics schemas for API responses.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


class TimeGranularity(str, Enum):
    """Time granularity for analytics."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class ChartType(str, Enum):
    """Supported chart types."""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"


class MetricType(str, Enum):
    """Available metric types."""
    SUBSCRIBERS = "subscribers"
    REVENUE = "revenue"
    ENGAGEMENT = "engagement"
    CONTENT = "content"


# Base schemas
class TimeSeriesDataPoint(BaseModel):
    """Single data point in a time series."""
    timestamp: datetime
    value: Union[int, float, Decimal]
    label: Optional[str] = None


class ChartSeries(BaseModel):
    """A single series in a chart."""
    name: str
    data: List[TimeSeriesDataPoint]
    color: Optional[str] = None
    type: Optional[ChartType] = ChartType.LINE


class ChartData(BaseModel):
    """Chart data in Recharts-compatible format."""
    title: str
    type: ChartType
    series: List[ChartSeries]
    xAxis: Dict[str, Any] = Field(default_factory=dict)
    yAxis: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Subscriber analytics
class SubscriberGrowthData(BaseModel):
    """Subscriber growth over time."""
    period_start: datetime
    period_end: datetime
    granularity: TimeGranularity
    total_subscribers: List[TimeSeriesDataPoint]
    paying_subscribers: List[TimeSeriesDataPoint]
    non_paying_fans: List[TimeSeriesDataPoint]
    new_subscribers: List[TimeSeriesDataPoint]
    lost_subscribers: List[TimeSeriesDataPoint]


# Revenue analytics
class RevenueBreakdown(BaseModel):
    """Revenue breakdown by type."""
    period_start: datetime
    period_end: datetime
    total_revenue: Decimal
    subscription_revenue: Decimal
    tip_revenue: Decimal
    ppv_revenue: Decimal
    
    # Percentage breakdown
    subscription_percentage: float
    tip_percentage: float
    ppv_percentage: float


class RevenueTimeSeriesData(BaseModel):
    """Revenue over time."""
    period_start: datetime
    period_end: datetime
    granularity: TimeGranularity
    total_revenue: List[TimeSeriesDataPoint]
    subscription_revenue: List[TimeSeriesDataPoint]
    tip_revenue: List[TimeSeriesDataPoint]
    ppv_revenue: List[TimeSeriesDataPoint]


# Fan analytics
class FanRevenueData(BaseModel):
    """Revenue data for specific fans."""
    fan_id: str
    username: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    total_spent: Decimal
    revenue_timeline: List[TimeSeriesDataPoint]
    spending_breakdown: RevenueBreakdown


class TopFansAnalytics(BaseModel):
    """Analytics for top spending fans."""
    period_start: datetime
    period_end: datetime
    top_fans: List[FanRevenueData]
    total_revenue_from_top_fans: Decimal
    percentage_of_total_revenue: float


# Content analytics
class ContentCategoryPerformance(BaseModel):
    """Performance metrics for a content category."""
    category_name: str
    content_count: int
    total_revenue: Decimal
    avg_revenue_per_content: Decimal
    total_views: int
    total_likes: int
    engagement_rate: float
    top_performing_content: List[Dict[str, Any]]


class CategoryPopularityData(BaseModel):
    """Category popularity metrics."""
    period_start: datetime
    period_end: datetime
    categories: List[ContentCategoryPerformance]
    most_profitable_category: str
    most_viewed_category: str
    highest_engagement_category: str


class ContentPerformanceData(BaseModel):
    """Individual content performance."""
    content_id: str
    content_type: str
    title: Optional[str]
    published_at: datetime
    categories: List[str]
    views: int
    likes: int
    comments: int
    engagement_rate: float
    total_revenue: Decimal
    revenue_per_view: Decimal


# Dashboard summary
class DashboardSummary(BaseModel):
    """High-level dashboard metrics."""
    period: str  # today, week, month
    
    # Key metrics
    total_revenue: Decimal
    revenue_change: float  # Percentage change from previous period
    
    total_subscribers: int
    subscriber_change: float
    
    paying_subscribers: int
    paying_subscriber_change: float
    
    avg_revenue_per_subscriber: Decimal
    conversion_rate: float
    
    # Top performers
    top_earning_content: Optional[ContentPerformanceData]
    top_spending_fan: Optional[FanRevenueData]
    most_popular_category: Optional[str]


# Export schemas
class ExportFormat(str, Enum):
    """Supported export formats."""
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class ExportRequest(BaseModel):
    """Request to export analytics data."""
    export_type: str  # revenue, subscribers, content, fans
    format: ExportFormat
    period_start: date
    period_end: date
    filters: Dict[str, Any] = Field(default_factory=dict)
    include_metadata: bool = True


class ExportResponse(BaseModel):
    """Response with export file information."""
    export_id: str
    file_url: str
    file_size: int
    expires_at: datetime
    format: ExportFormat


# Chart request/response
class ChartRequest(BaseModel):
    """Request for chart data."""
    chart_type: str  # subscriber_growth, revenue_timeline, etc.
    period_start: date
    period_end: date
    granularity: TimeGranularity = TimeGranularity.DAY
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    # For multi-line charts (e.g., per-fan revenue)
    entity_ids: Optional[List[str]] = None
    max_series: int = Field(10, le=10)  # Max 10 lines on a chart


class ChartResponse(BaseModel):
    """Response with chart data."""
    chart_data: ChartData
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    cache_expires_at: Optional[datetime] = None


class TrendAnalysis(BaseModel):
    """Trend analysis results."""
    trend_direction: str  # 'up', 'down', 'stable'
    trend_strength: float
    slope: float
    intercept: float
    r_squared: float
    confidence_interval: Tuple[float, float]
    trend_line: List[float]
    
    
class GrowthMetrics(BaseModel):
    """Growth metrics analysis."""
    growth_rate: float
    compound_growth_rate: float
    month_over_month: float
    year_over_year: float
    volatility: float
    periods: List[Dict[str, Any]]
    
    
class Forecast(BaseModel):
    """Forecast results."""
    forecast_values: List[float]
    confidence_intervals: List[Tuple[float, float]]
    dates: List[datetime]
    method: str
    accuracy_metrics: Dict[str, float]
    
    
class SeasonalPattern(BaseModel):
    """Seasonal pattern analysis."""
    has_seasonality: bool
    seasonal_period: Optional[int] = None
    seasonal_strength: Optional[float] = None
    seasonal_components: Optional[List[float]] = None
    pattern_type: Optional[str] = None  # 'weekly', 'monthly', 'yearly', etc.