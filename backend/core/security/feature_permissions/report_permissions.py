"""
Report-specific permission service for granular report access control.

This service handles report template permissions, execution permissions,
and data filtering based on user roles and permissions.
"""
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import json

from models.user import User, UserRole
from models.feature_permission import (
    ReportTemplate, ReportType, ReportSchedule, ReportExecution,
    DataSensitivity, ExportFormat, FeaturePermission, FeatureType
)
from core.security.feature_permissions.service import feature_permission_service
from core.logger import get_logger
from core.exceptions import PermissionDeniedError, ResourceNotFoundError
from core.redis import redis_client


logger = get_logger(__name__)


class ReportPermissionService:
    """Service for managing report-specific permissions."""
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes
    
    async def can_access_report(
        self,
        db: AsyncSession,
        user: User,
        template_id: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check if user can access a report template.
        
        Returns:
            Tuple of (allowed, denial_reason, filtered_parameters)
        """
        # Get template
        template = await db.get(ReportTemplate, template_id)
        if not template:
            return False, "Report template not found", None
        
        if not template.is_active:
            return False, "Report template is inactive", None
        
        # Check basic feature permission
        context = {
            "report_type": template.report_type,
            "contains_financial": template.include_financial,
            "contains_pii": template.include_pii,
            "template_id": template_id
        }
        
        if parameters:
            # Calculate date range if provided
            if "start_date" in parameters and "end_date" in parameters:
                start = datetime.fromisoformat(parameters["start_date"])
                end = datetime.fromisoformat(parameters["end_date"])
                context["date_range_days"] = (end - start).days
        
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.REPORTS, "view_report", template_id, context
        )
        
        if not allowed:
            return False, reason, None
        
        # Check template-specific permissions
        user_role_ids = [role.id for role in user.roles]
        
        # Check required roles
        if template.required_roles:
            if not any(role_id in template.required_roles for role_id in user_role_ids):
                return False, "Missing required role for this report", None
        
        # Check excluded roles
        if template.excluded_roles:
            if any(role_id in template.excluded_roles for role_id in user_role_ids):
                return False, "Your role is excluded from this report", None
        
        # Check data sensitivity level
        user_sensitivity_level = await self._get_user_max_sensitivity_level(db, user)
        if not self._check_sensitivity_access(user_sensitivity_level, template.required_permission_level):
            return False, f"Insufficient data sensitivity clearance", None
        
        # Check if approval required
        if template.requires_approval:
            # Check if user has pre-approval or is in approval chain
            if not await self._check_report_approval(db, user, template):
                return False, "Report requires approval", None
        
        # Filter parameters based on permissions
        filtered_params = await self._filter_report_parameters(
            db, user, template, parameters or {}
        )
        
        return True, None, filtered_params
    
    async def _get_user_max_sensitivity_level(
        self,
        db: AsyncSession,
        user: User
    ) -> DataSensitivity:
        """Get the maximum data sensitivity level a user can access."""
        # Check cache
        cache_key = f"user_sensitivity:{user.id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return DataSensitivity(cached)
        
        # Query user's feature permissions
        permissions = await feature_permission_service.get_user_permissions(
            db, user, FeatureType.REPORTS
        )
        
        # Find highest sensitivity level
        max_level = DataSensitivity.PUBLIC
        level_hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.RESTRICTED: 3,
            DataSensitivity.TOP_SECRET: 4
        }
        
        for perm in permissions:
            if perm.data_sensitivity_level:
                if level_hierarchy.get(perm.data_sensitivity_level, 0) > level_hierarchy.get(max_level, 0):
                    max_level = perm.data_sensitivity_level
        
        # Cache result
        await redis_client.setex(cache_key, self.cache_ttl, max_level.value)
        
        return max_level
    
    def _check_sensitivity_access(
        self,
        user_level: DataSensitivity,
        required_level: DataSensitivity
    ) -> bool:
        """Check if user's sensitivity level meets requirement."""
        level_hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.RESTRICTED: 3,
            DataSensitivity.TOP_SECRET: 4
        }
        
        return level_hierarchy.get(user_level, 0) >= level_hierarchy.get(required_level, 0)
    
    async def _check_report_approval(
        self,
        db: AsyncSession,
        user: User,
        template: ReportTemplate
    ) -> bool:
        """Check if user has approval to run report."""
        # Check if user is in approval chain
        if template.approval_chain:
            user_role_ids = [role.id for role in user.roles]
            if any(role_id in template.approval_chain for role_id in user_role_ids):
                return True
        
        # Check for pre-approved schedule
        query = select(ReportSchedule).where(
            and_(
                ReportSchedule.template_id == template.id,
                ReportSchedule.created_by_id == user.id,
                ReportSchedule.approved_by_id.isnot(None),
                ReportSchedule.is_active == True
            )
        )
        
        result = await db.execute(query)
        return result.scalar() is not None
    
    async def _filter_report_parameters(
        self,
        db: AsyncSession,
        user: User,
        template: ReportTemplate,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Filter report parameters based on user permissions."""
        filtered = parameters.copy()
        
        # Get user's permissions
        permissions = await feature_permission_service.get_user_permissions(
            db, user, FeatureType.REPORTS
        )
        
        # Apply date range restrictions
        max_range_days = None
        for perm in permissions:
            if perm.max_report_range_days:
                if max_range_days is None or perm.max_report_range_days > max_range_days:
                    max_range_days = perm.max_report_range_days
        
        # Also check template restrictions
        if template.max_date_range_days:
            if max_range_days is None or template.max_date_range_days < max_range_days:
                max_range_days = template.max_date_range_days
        
        # Apply date range limit
        if max_range_days and "start_date" in filtered and "end_date" in filtered:
            start = datetime.fromisoformat(filtered["start_date"])
            end = datetime.fromisoformat(filtered["end_date"])
            
            if (end - start).days > max_range_days:
                # Adjust end date to respect limit
                filtered["end_date"] = (start + timedelta(days=max_range_days)).isoformat()
                filtered["_date_range_limited"] = True
                filtered["_max_range_days"] = max_range_days
        
        # Filter data based on user's scope
        if user.role != UserRole.ADMIN:
            # Add agency filter
            filtered["agency_id"] = user.agency_id
            
            # Add user-specific filters based on role
            if user.role == UserRole.MODEL:
                filtered["model_id"] = user.id
            elif user.role == UserRole.CHATTER:
                # Get assigned models
                filtered["assigned_model_ids"] = await self._get_assigned_models(db, user)
        
        return filtered
    
    async def _get_assigned_models(
        self,
        db: AsyncSession,
        user: User
    ) -> List[str]:
        """Get list of models assigned to a chatter."""
        # This would query the model-chatter assignment table
        # Simplified for now
        return []
    
    async def execute_report(
        self,
        db: AsyncSession,
        user: User,
        template_id: str,
        parameters: Dict[str, Any],
        export_format: Optional[ExportFormat] = None
    ) -> ReportExecution:
        """Execute a report with permission checks."""
        # Check access
        allowed, reason, filtered_params = await self.can_access_report(
            db, user, template_id, parameters
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot execute report: {reason}")
        
        # Get template
        template = await db.get(ReportTemplate, template_id)
        
        # Check export permissions if needed
        if export_format:
            if not template.allow_export:
                raise PermissionDeniedError("Export not allowed for this report")
            
            if export_format.value not in template.export_formats:
                raise PermissionDeniedError(f"Export format {export_format} not allowed")
            
            # Check export permissions
            export_context = {
                "format": export_format.value,
                "template_id": template_id
            }
            
            export_allowed, export_reason = await feature_permission_service.check_feature_permission(
                db, user, FeatureType.EXPORTS, "export_data", template_id, export_context
            )
            
            if not export_allowed:
                raise PermissionDeniedError(f"Cannot export report: {export_reason}")
        
        # Create execution record
        execution = ReportExecution(
            template_id=template_id,
            executed_by_id=user.id,
            parameters=filtered_params,
            filters=template.default_filters,
            status="pending",
            export_format=export_format.value if export_format else None
        )
        
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        
        # Queue for processing (would integrate with task queue)
        await self._queue_report_execution(execution, template, filtered_params)
        
        return execution
    
    async def _queue_report_execution(
        self,
        execution: ReportExecution,
        template: ReportTemplate,
        parameters: Dict[str, Any]
    ):
        """Queue report for execution."""
        # This would integrate with Celery or similar task queue
        # For now, just log
        logger.info(f"Queuing report execution {execution.id} for template {template.name}")
    
    async def create_report_template(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        report_type: ReportType,
        query_template: str,
        **kwargs
    ) -> ReportTemplate:
        """Create a new report template."""
        # Check permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.REPORTS, "create_template"
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot create report template: {reason}")
        
        template = ReportTemplate(
            name=name,
            report_type=report_type,
            query_template=query_template,
            created_by_id=user.id,
            agency_id=user.agency_id if user.role != UserRole.ADMIN else kwargs.get("agency_id"),
            **kwargs
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        return template
    
    async def schedule_report(
        self,
        db: AsyncSession,
        user: User,
        template_id: str,
        name: str,
        cron_expression: Optional[str] = None,
        interval_hours: Optional[int] = None,
        **kwargs
    ) -> ReportSchedule:
        """Schedule a report for periodic execution."""
        # Check if user can access the report
        allowed, reason, _ = await self.can_access_report(db, user, template_id)
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot schedule report: {reason}")
        
        # Get template
        template = await db.get(ReportTemplate, template_id)
        
        if not template.allow_scheduling:
            raise PermissionDeniedError("Scheduling not allowed for this report")
        
        # Check minimum interval
        if interval_hours and template.min_schedule_interval_hours:
            if interval_hours < template.min_schedule_interval_hours:
                raise PermissionDeniedError(
                    f"Schedule interval must be at least {template.min_schedule_interval_hours} hours"
                )
        
        # Create schedule
        schedule = ReportSchedule(
            name=name,
            template_id=template_id,
            created_by_id=user.id,
            cron_expression=cron_expression,
            interval_hours=interval_hours,
            **kwargs
        )
        
        # Check if approval required
        if template.requires_approval:
            schedule.is_active = False  # Inactive until approved
        
        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)
        
        return schedule
    
    async def get_available_reports(
        self,
        db: AsyncSession,
        user: User,
        include_inactive: bool = False
    ) -> List[ReportTemplate]:
        """Get all report templates available to a user."""
        # Base query
        query = select(ReportTemplate)
        
        if not include_inactive:
            query = query.where(ReportTemplate.is_active == True)
        
        # Filter by agency for non-admins
        if user.role != UserRole.ADMIN:
            query = query.where(
                or_(
                    ReportTemplate.agency_id == user.agency_id,
                    ReportTemplate.agency_id.is_(None)  # Global templates
                )
            )
        
        result = await db.execute(query)
        templates = result.scalars().all()
        
        # Filter by permissions
        available = []
        for template in templates:
            allowed, _, _ = await self.can_access_report(db, user, str(template.id))
            if allowed:
                available.append(template)
        
        return available
    
    async def get_report_executions(
        self,
        db: AsyncSession,
        user: User,
        template_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ReportExecution]:
        """Get report execution history."""
        query = select(ReportExecution)
        
        # Filter by template if provided
        if template_id:
            # Check if user can access this template
            allowed, _, _ = await self.can_access_report(db, user, template_id)
            if not allowed:
                return []
            
            query = query.where(ReportExecution.template_id == template_id)
        
        # Filter by user for non-admins
        if user.role != UserRole.ADMIN:
            query = query.where(ReportExecution.executed_by_id == user.id)
        
        # Order and limit
        query = query.order_by(ReportExecution.started_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()


# Global instance
report_permission_service = ReportPermissionService()