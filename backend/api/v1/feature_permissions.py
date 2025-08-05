"""
Feature permission management endpoints.

This module provides REST APIs for managing feature-specific permissions,
including creating, updating, and querying permissions for reports, exports,
analytics, and messaging features.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel, Field, validator
import uuid

from core.database import get_db
from core.security.dependencies import get_current_active_user
from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, ReportType, ExportFormat,
    AnalyticsScope, MessagePermission, DataSensitivity,
    ReportTemplate, ReportSchedule, ReportExecution
)
from core.security.feature_permissions.service import feature_permission_service
from core.security.feature_permissions.report_permissions import report_permission_service
from core.security.feature_permissions.export_permissions import export_permission_service
from core.security.feature_permissions.analytics_permissions import analytics_permission_service
from core.security.feature_permissions.messaging_permissions import messaging_permission_service
from core.logger import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/feature-permissions", tags=["feature-permissions"])


# Request/Response Models
class FeaturePermissionCreate(BaseModel):
    """Request model for creating feature permissions."""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    feature_type: FeatureType
    role_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    
    # Feature-specific permissions
    allowed_actions: List[str] = Field(default_factory=list)
    denied_actions: List[str] = Field(default_factory=list)
    
    # Report permissions
    allowed_report_types: List[ReportType] = Field(default_factory=list)
    max_report_range_days: Optional[int] = Field(None, ge=1, le=3650)
    can_access_financial_data: bool = False
    can_access_pii_data: bool = False
    data_sensitivity_level: DataSensitivity = DataSensitivity.INTERNAL
    
    # Export permissions
    allowed_export_formats: List[ExportFormat] = Field(default_factory=list)
    max_export_rows: Optional[int] = Field(None, ge=1)
    max_export_size_mb: Optional[int] = Field(None, ge=1, le=10000)
    export_rate_limit_per_hour: int = Field(10, ge=1, le=1000)
    can_export_all_data: bool = False
    requires_export_approval: bool = False
    
    # Analytics permissions
    analytics_scope: AnalyticsScope = AnalyticsScope.OWN
    allowed_metrics: List[str] = Field(default_factory=list)
    can_view_revenue_data: bool = False
    can_view_cost_data: bool = False
    can_create_custom_metrics: bool = False
    
    # Messaging permissions
    message_permissions: List[MessagePermission] = Field(default_factory=list)
    max_bulk_recipients: Optional[int] = Field(None, ge=1)
    max_messages_per_hour: Optional[int] = Field(None, ge=1)
    can_use_automation: bool = False
    can_access_all_conversations: bool = False
    
    # Time restrictions
    access_start_time: Optional[str] = Field(None, regex=r"^\d{2}:\d{2}$")
    access_end_time: Optional[str] = Field(None, regex=r"^\d{2}:\d{2}$")
    access_days_of_week: List[int] = Field(default_factory=list)
    access_timezone: str = "UTC"
    
    # Conditional access
    requires_mfa: bool = False
    requires_vpn: bool = False
    allowed_ip_ranges: Optional[List[str]] = None
    allowed_countries: Optional[List[str]] = None
    
    # Approval workflow
    requires_approval: bool = False
    approval_chain: List[uuid.UUID] = Field(default_factory=list)
    auto_expire_hours: Optional[int] = Field(None, ge=1, le=8760)
    
    # Usage tracking
    usage_quota_daily: Optional[int] = Field(None, ge=1)
    usage_quota_monthly: Optional[int] = Field(None, ge=1)
    cost_per_use: Optional[float] = Field(None, ge=0)
    
    # Metadata
    priority: int = Field(0, ge=0, le=1000)
    expires_at: Optional[datetime] = None
    
    @validator("role_id", "user_id")
    def validate_target(cls, v, values):
        """Ensure either role_id or user_id is set."""
        if not v and not values.get("role_id") and not values.get("user_id"):
            raise ValueError("Either role_id or user_id must be specified")
        return v


class FeaturePermissionUpdate(BaseModel):
    """Request model for updating feature permissions."""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    allowed_actions: Optional[List[str]] = None
    denied_actions: Optional[List[str]] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=1000)
    expires_at: Optional[datetime] = None
    
    # Add other fields as needed...


class FeaturePermissionResponse(BaseModel):
    """Response model for feature permissions."""
    id: uuid.UUID
    name: str
    description: Optional[str]
    feature_type: FeatureType
    role_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ReportTemplateCreate(BaseModel):
    """Request model for creating report templates."""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    report_type: ReportType
    query_template: str
    parameters: dict = Field(default_factory=dict)
    default_filters: dict = Field(default_factory=dict)
    available_columns: List[str] = Field(default_factory=list)
    default_columns: List[str] = Field(default_factory=list)
    
    # Visualization
    chart_types: List[str] = Field(default_factory=list)
    default_chart_type: Optional[str] = None
    
    # Access control
    required_permission_level: DataSensitivity = DataSensitivity.INTERNAL
    required_roles: List[uuid.UUID] = Field(default_factory=list)
    excluded_roles: List[uuid.UUID] = Field(default_factory=list)
    requires_approval: bool = False
    
    # Settings
    max_date_range_days: Optional[int] = Field(None, ge=1, le=3650)
    allow_export: bool = True
    export_formats: List[ExportFormat] = Field(default=["csv", "excel", "pdf"])
    allow_scheduling: bool = True
    execution_cost: float = Field(1.0, ge=0)


class ExportRequest(BaseModel):
    """Request model for data export."""
    export_type: str
    format: ExportFormat
    filters: dict = Field(default_factory=dict)
    include_metadata: bool = False
    compress: bool = False


class AnalyticsRequest(BaseModel):
    """Request model for analytics data."""
    analytics_type: str
    scope: AnalyticsScope = AnalyticsScope.OWN
    metrics: List[str]
    date_range: dict
    filters: dict = Field(default_factory=dict)
    group_by: Optional[List[str]] = None


class MessageSendRequest(BaseModel):
    """Request model for sending messages."""
    recipient_ids: List[str]
    content: str
    template_id: Optional[str] = None
    variables: dict = Field(default_factory=dict)
    schedule_time: Optional[datetime] = None
    is_automated: bool = False


# Endpoints
@router.get("/", response_model=List[FeaturePermissionResponse])
async def list_feature_permissions(
    feature_type: Optional[FeatureType] = None,
    is_active: Optional[bool] = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List feature permissions accessible to the current user."""
    # Build query
    query = select(FeaturePermission)
    
    # Filter by feature type
    if feature_type:
        query = query.where(FeaturePermission.feature_type == feature_type)
    
    # Filter by active status
    if is_active is not None:
        query = query.where(FeaturePermission.is_active == is_active)
    
    # Filter by user access
    if current_user.role != UserRole.ADMIN:
        user_role_ids = [role.id for role in current_user.roles]
        query = query.where(
            or_(
                FeaturePermission.user_id == current_user.id,
                FeaturePermission.role_id.in_(user_role_ids) if user_role_ids else False,
                and_(
                    FeaturePermission.agency_id == current_user.agency_id,
                    FeaturePermission.user_id.is_(None),
                    FeaturePermission.role_id.is_(None)
                )
            )
        )
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(FeaturePermission.priority.desc())
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=FeaturePermissionResponse)
async def create_feature_permission(
    permission_data: FeaturePermissionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new feature permission."""
    try:
        # Convert message permissions to string values
        message_perms = [p.value if hasattr(p, 'value') else p for p in permission_data.message_permissions]
        
        permission = await feature_permission_service.create_feature_permission(
            db=db,
            user=current_user,
            name=permission_data.name,
            feature_type=permission_data.feature_type,
            description=permission_data.description,
            role_id=permission_data.role_id,
            user_id=permission_data.user_id,
            allowed_actions=permission_data.allowed_actions,
            denied_actions=permission_data.denied_actions,
            allowed_report_types=[rt.value for rt in permission_data.allowed_report_types],
            max_report_range_days=permission_data.max_report_range_days,
            can_access_financial_data=permission_data.can_access_financial_data,
            can_access_pii_data=permission_data.can_access_pii_data,
            data_sensitivity_level=permission_data.data_sensitivity_level,
            allowed_export_formats=[ef.value for ef in permission_data.allowed_export_formats],
            max_export_rows=permission_data.max_export_rows,
            max_export_size_mb=permission_data.max_export_size_mb,
            export_rate_limit_per_hour=permission_data.export_rate_limit_per_hour,
            can_export_all_data=permission_data.can_export_all_data,
            requires_export_approval=permission_data.requires_export_approval,
            analytics_scope=permission_data.analytics_scope,
            allowed_metrics=permission_data.allowed_metrics,
            can_view_revenue_data=permission_data.can_view_revenue_data,
            can_view_cost_data=permission_data.can_view_cost_data,
            can_create_custom_metrics=permission_data.can_create_custom_metrics,
            message_permissions=message_perms,
            max_bulk_recipients=permission_data.max_bulk_recipients,
            max_messages_per_hour=permission_data.max_messages_per_hour,
            can_use_automation=permission_data.can_use_automation,
            can_access_all_conversations=permission_data.can_access_all_conversations,
            access_start_time=permission_data.access_start_time,
            access_end_time=permission_data.access_end_time,
            access_days_of_week=permission_data.access_days_of_week,
            access_timezone=permission_data.access_timezone,
            requires_mfa=permission_data.requires_mfa,
            requires_vpn=permission_data.requires_vpn,
            allowed_ip_ranges=permission_data.allowed_ip_ranges,
            allowed_countries=permission_data.allowed_countries,
            requires_approval=permission_data.requires_approval,
            approval_chain=permission_data.approval_chain,
            auto_expire_hours=permission_data.auto_expire_hours,
            usage_quota_daily=permission_data.usage_quota_daily,
            usage_quota_monthly=permission_data.usage_quota_monthly,
            cost_per_use=permission_data.cost_per_use,
            priority=permission_data.priority,
            expires_at=permission_data.expires_at,
            agency_id=current_user.agency_id if current_user.role != UserRole.ADMIN else None
        )
        
        return permission
        
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating feature permission: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{permission_id}", response_model=FeaturePermissionResponse)
async def get_feature_permission(
    permission_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific feature permission."""
    permission = await db.get(FeaturePermission, permission_id)
    
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    
    # Check access
    if current_user.role != UserRole.ADMIN:
        user_role_ids = [role.id for role in current_user.roles]
        has_access = (
            permission.user_id == current_user.id or
            permission.role_id in user_role_ids or
            (permission.agency_id == current_user.agency_id and 
             permission.user_id is None and permission.role_id is None)
        )
        
        if not has_access:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return permission


@router.put("/{permission_id}", response_model=FeaturePermissionResponse)
async def update_feature_permission(
    permission_id: uuid.UUID,
    permission_update: FeaturePermissionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a feature permission."""
    try:
        updates = permission_update.dict(exclude_unset=True)
        
        permission = await feature_permission_service.update_feature_permission(
            db=db,
            user=current_user,
            permission_id=str(permission_id),
            **updates
        )
        
        return permission
        
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating feature permission: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{permission_id}")
async def delete_feature_permission(
    permission_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a feature permission."""
    try:
        await feature_permission_service.delete_feature_permission(
            db=db,
            user=current_user,
            permission_id=str(permission_id)
        )
        
        return {"detail": "Permission deleted successfully"}
        
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting feature permission: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Report-specific endpoints
@router.post("/reports/templates", response_model=dict)
async def create_report_template(
    template_data: ReportTemplateCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new report template."""
    try:
        template = await report_permission_service.create_report_template(
            db=db,
            user=current_user,
            name=template_data.name,
            report_type=template_data.report_type,
            query_template=template_data.query_template,
            description=template_data.description,
            parameters=template_data.parameters,
            default_filters=template_data.default_filters,
            available_columns=template_data.available_columns,
            default_columns=template_data.default_columns,
            chart_types=template_data.chart_types,
            default_chart_type=template_data.default_chart_type,
            required_permission_level=template_data.required_permission_level,
            required_roles=template_data.required_roles,
            excluded_roles=template_data.excluded_roles,
            requires_approval=template_data.requires_approval,
            max_date_range_days=template_data.max_date_range_days,
            allow_export=template_data.allow_export,
            export_formats=[ef.value for ef in template_data.export_formats],
            allow_scheduling=template_data.allow_scheduling,
            execution_cost=template_data.execution_cost
        )
        
        return {"id": str(template.id), "name": template.name}
        
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating report template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/reports/available")
async def get_available_reports(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all report templates available to the current user."""
    try:
        reports = await report_permission_service.get_available_reports(db, current_user)
        
        return [
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "report_type": r.report_type,
                "requires_approval": r.requires_approval
            }
            for r in reports
        ]
        
    except Exception as e:
        logger.error(f"Error getting available reports: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Export-specific endpoints
@router.post("/exports/check-permission")
async def check_export_permission(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user can perform an export."""
    try:
        allowed, reason, limits = await export_permission_service.can_export_data(
            db=db,
            user=current_user,
            export_type=export_request.export_type,
            format=export_request.format
        )
        
        return {
            "allowed": allowed,
            "reason": reason,
            "limits": limits
        }
        
    except Exception as e:
        logger.error(f"Error checking export permission: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/exports/quota")
async def get_export_quota(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's export quota usage."""
    try:
        quota = await export_permission_service.check_export_quota(db, current_user)
        return quota
        
    except Exception as e:
        logger.error(f"Error getting export quota: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Analytics-specific endpoints
@router.get("/analytics/dashboards")
async def get_analytics_dashboards(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get available analytics dashboards for user."""
    try:
        dashboards = await analytics_permission_service.get_analytics_dashboards(db, current_user)
        return dashboards
        
    except Exception as e:
        logger.error(f"Error getting analytics dashboards: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/analytics/check-access")
async def check_analytics_access(
    analytics_request: AnalyticsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user can access analytics."""
    try:
        allowed, reason, filters = await analytics_permission_service.check_analytics_access(
            db=db,
            user=current_user,
            analytics_type=analytics_request.analytics_type,
            requested_scope=analytics_request.scope,
            metrics=analytics_request.metrics,
            date_range=analytics_request.date_range
        )
        
        return {
            "allowed": allowed,
            "reason": reason,
            "data_filters": filters
        }
        
    except Exception as e:
        logger.error(f"Error checking analytics access: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# Messaging-specific endpoints
@router.post("/messaging/check-permission")
async def check_messaging_permission(
    message_request: MessageSendRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if user can send a message."""
    try:
        allowed, reason, limits = await messaging_permission_service.can_send_message(
            db=db,
            user=current_user,
            message_type="bulk" if len(message_request.recipient_ids) > 1 else "individual",
            recipient_count=len(message_request.recipient_ids),
            is_automated=message_request.is_automated
        )
        
        return {
            "allowed": allowed,
            "reason": reason,
            "limits": limits
        }
        
    except Exception as e:
        logger.error(f"Error checking messaging permission: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/messaging/stats")
async def get_messaging_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's messaging statistics and limits."""
    try:
        stats = await messaging_permission_service.get_messaging_stats(db, current_user)
        return stats
        
    except Exception as e:
        logger.error(f"Error getting messaging stats: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# My permissions endpoint
@router.get("/my-permissions")
async def get_my_permissions(
    feature_type: Optional[FeatureType] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all permissions for the current user."""
    try:
        permissions = await feature_permission_service.get_user_permissions(
            db, current_user, feature_type
        )
        
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "feature_type": p.feature_type,
                "priority": p.priority,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None
            }
            for p in permissions
        ]
        
    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))