"""
Feature permission service for managing granular feature access control.

This service handles checking and enforcing feature-specific permissions,
including reports, exports, analytics, and messaging permissions.
"""
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime, time, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
import json
from ipaddress import ip_address, ip_network

from models.user import User
from models.role import Role
from models.feature_permission import (
    FeaturePermission, FeatureUsageLog, FeatureType, 
    ReportType, ExportFormat, AnalyticsScope, MessagePermission,
    DataSensitivity, ReportTemplate
)
from core.redis import redis_client
from core.logger import get_logger
from core.audit.service import AuditService
from core.audit.models import AuditAction
from core.exceptions import PermissionDeniedError, ResourceNotFoundError


logger = get_logger(__name__)


class FeaturePermissionService:
    """Service for managing feature-specific permissions."""
    
    def __init__(self):
        self.audit_service = AuditService()
        self.cache_ttl = 300  # 5 minutes
    
    async def check_feature_permission(
        self,
        db: AsyncSession,
        user: User,
        feature_type: FeatureType,
        action: str,
        resource_id: Optional[str] = None,
        request_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a user has permission to perform an action on a feature.
        
        Returns:
            Tuple of (allowed, denial_reason)
        """
        try:
            # Check cache first
            cache_key = f"feature_perm:{user.id}:{feature_type}:{action}"
            cached = await redis_client.get(cache_key)
            if cached:
                result = json.loads(cached)
                return result["allowed"], result.get("reason")
            
            # Get user's feature permissions
            permissions = await self._get_user_feature_permissions(
                db, user, feature_type
            )
            
            if not permissions:
                return False, "No permissions configured for this feature"
            
            # Check each permission (higher priority first)
            for perm in sorted(permissions, key=lambda p: p.priority, reverse=True):
                allowed, reason = await self._evaluate_permission(
                    db, user, perm, action, request_context
                )
                
                if allowed is not None:  # Explicit allow or deny
                    # Cache the result
                    await redis_client.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps({"allowed": allowed, "reason": reason})
                    )
                    
                    # Log usage
                    await self._log_feature_usage(
                        db, user, perm, feature_type, action,
                        resource_id, allowed, reason, request_context
                    )
                    
                    return allowed, reason
            
            # No explicit permission found
            return False, "No matching permission rule found"
            
        except Exception as e:
            logger.error(f"Error checking feature permission: {e}")
            return False, f"Permission check failed: {str(e)}"
    
    async def _get_user_feature_permissions(
        self,
        db: AsyncSession,
        user: User,
        feature_type: FeatureType
    ) -> List[FeaturePermission]:
        """Get all feature permissions applicable to a user."""
        # Get user's roles
        user_role_ids = [role.id for role in user.roles]
        
        # Query permissions
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.feature_type == feature_type,
                FeaturePermission.is_active == True,
                or_(
                    FeaturePermission.expires_at.is_(None),
                    FeaturePermission.expires_at > datetime.utcnow()
                ),
                or_(
                    FeaturePermission.user_id == user.id,
                    FeaturePermission.role_id.in_(user_role_ids) if user_role_ids else False,
                    and_(
                        FeaturePermission.agency_id == user.agency_id,
                        FeaturePermission.user_id.is_(None),
                        FeaturePermission.role_id.is_(None)
                    )
                )
            )
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def _evaluate_permission(
        self,
        db: AsyncSession,
        user: User,
        permission: FeaturePermission,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Evaluate a single permission rule."""
        # Check time restrictions
        if not self._check_time_restrictions(permission):
            return False, "Access denied outside allowed time window"
        
        # Check location restrictions
        if context and not self._check_location_restrictions(permission, context):
            return False, "Access denied from this location"
        
        # Check conditional access
        if not await self._check_conditional_access(user, permission, context):
            return False, "Conditional access requirements not met"
        
        # Check action permissions
        if permission.denied_actions and action in permission.denied_actions:
            return False, f"Action '{action}' is explicitly denied"
        
        if permission.allowed_actions:
            if action in permission.allowed_actions:
                return True, None
            else:
                return None, None  # Not explicitly allowed or denied
        
        # Feature-specific checks
        if permission.feature_type == FeatureType.REPORTS:
            return await self._check_report_permission(permission, action, context)
        elif permission.feature_type == FeatureType.EXPORTS:
            return await self._check_export_permission(permission, action, context)
        elif permission.feature_type == FeatureType.ANALYTICS:
            return await self._check_analytics_permission(permission, action, context)
        elif permission.feature_type == FeatureType.MESSAGING:
            return await self._check_messaging_permission(permission, action, context)
        
        # Default allow if no specific rules
        return True, None
    
    def _check_time_restrictions(self, permission: FeaturePermission) -> bool:
        """Check if current time is within allowed access window."""
        if not permission.access_start_time and not permission.access_end_time:
            return True
        
        # Get current time in permission's timezone
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(permission.access_timezone or "UTC")
        now = datetime.now(tz)
        current_time = now.time()
        current_day = now.weekday()  # 0 = Monday
        
        # Check day of week
        if permission.access_days_of_week and current_day not in permission.access_days_of_week:
            return False
        
        # Check time window
        if permission.access_start_time and permission.access_end_time:
            start = time.fromisoformat(permission.access_start_time)
            end = time.fromisoformat(permission.access_end_time)
            
            # Handle overnight windows
            if start <= end:
                return start <= current_time <= end
            else:
                return current_time >= start or current_time <= end
        
        return True
    
    def _check_location_restrictions(
        self,
        permission: FeaturePermission,
        context: Dict[str, Any]
    ) -> bool:
        """Check if access is allowed from current location."""
        if not context:
            return True
        
        # Check IP ranges
        if permission.allowed_ip_ranges and "ip_address" in context:
            try:
                user_ip = ip_address(context["ip_address"])
                allowed = False
                for ip_range in permission.allowed_ip_ranges:
                    if user_ip in ip_network(ip_range):
                        allowed = True
                        break
                if not allowed:
                    return False
            except Exception as e:
                logger.error(f"Error checking IP restrictions: {e}")
                return False
        
        # Check countries
        if permission.allowed_countries and "country_code" in context:
            if context["country_code"] not in permission.allowed_countries:
                return False
        
        return True
    
    async def _check_conditional_access(
        self,
        user: User,
        permission: FeaturePermission,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check conditional access requirements."""
        # Check MFA requirement
        if permission.requires_mfa:
            # Check if user has MFA enabled and current session used MFA
            if not user.mfa_enabled:
                return False
            if context and not context.get("mfa_verified"):
                return False
        
        # Check VPN requirement
        if permission.requires_vpn and context:
            # Simple check - in production, implement proper VPN detection
            if not context.get("is_vpn"):
                return False
        
        return True
    
    async def _check_report_permission(
        self,
        permission: FeaturePermission,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Check report-specific permissions."""
        if action == "view_report" and context:
            report_type = context.get("report_type")
            if report_type and permission.allowed_report_types:
                if report_type not in permission.allowed_report_types:
                    return False, f"Report type '{report_type}' not allowed"
            
            # Check date range
            if permission.max_report_range_days and "date_range_days" in context:
                if context["date_range_days"] > permission.max_report_range_days:
                    return False, f"Date range exceeds maximum of {permission.max_report_range_days} days"
            
            # Check data sensitivity
            if context.get("contains_financial") and not permission.can_access_financial_data:
                return False, "No permission to access financial data"
            
            if context.get("contains_pii") and not permission.can_access_pii_data:
                return False, "No permission to access PII data"
        
        return True, None
    
    async def _check_export_permission(
        self,
        permission: FeaturePermission,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Check export-specific permissions."""
        if action == "export_data" and context:
            # Check format
            export_format = context.get("format")
            if export_format and permission.allowed_export_formats:
                if export_format not in permission.allowed_export_formats:
                    return False, f"Export format '{export_format}' not allowed"
            
            # Check size limits
            if permission.max_export_rows and "row_count" in context:
                if context["row_count"] > permission.max_export_rows:
                    return False, f"Export exceeds maximum of {permission.max_export_rows} rows"
            
            if permission.max_export_size_mb and "size_mb" in context:
                if context["size_mb"] > permission.max_export_size_mb:
                    return False, f"Export exceeds maximum size of {permission.max_export_size_mb} MB"
            
            # Check if approval required
            if permission.requires_export_approval and not context.get("is_approved"):
                return False, "Export requires approval"
        
        return True, None
    
    async def _check_analytics_permission(
        self,
        permission: FeaturePermission,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Check analytics-specific permissions."""
        if action == "view_analytics" and context:
            # Check scope
            requested_scope = context.get("scope", AnalyticsScope.OWN)
            if permission.analytics_scope:
                scope_hierarchy = {
                    AnalyticsScope.OWN: 0,
                    AnalyticsScope.TEAM: 1,
                    AnalyticsScope.AGENCY: 2,
                    AnalyticsScope.GLOBAL: 3
                }
                
                if scope_hierarchy.get(requested_scope, 0) > scope_hierarchy.get(permission.analytics_scope, 0):
                    return False, f"Analytics scope '{requested_scope}' not allowed"
            
            # Check metrics
            if permission.allowed_metrics and "metrics" in context:
                for metric in context["metrics"]:
                    if metric not in permission.allowed_metrics:
                        return False, f"Metric '{metric}' not allowed"
            
            # Check data types
            if context.get("includes_revenue") and not permission.can_view_revenue_data:
                return False, "No permission to view revenue data"
            
            if context.get("includes_costs") and not permission.can_view_cost_data:
                return False, "No permission to view cost data"
        
        return True, None
    
    async def _check_messaging_permission(
        self,
        permission: FeaturePermission,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Check messaging-specific permissions."""
        # Map actions to message permissions
        action_mapping = {
            "send_message": MessagePermission.SEND_INDIVIDUAL,
            "send_bulk": MessagePermission.SEND_BULK,
            "view_history": MessagePermission.VIEW_HISTORY,
            "delete_message": MessagePermission.DELETE_MESSAGES,
            "edit_template": MessagePermission.EDIT_TEMPLATES,
            "approve_scheduled": MessagePermission.APPROVE_SCHEDULED,
            "manage_automation": MessagePermission.MANAGE_AUTOMATION,
            "access_all_chats": MessagePermission.ACCESS_ALL_CHATS,
            "export_chats": MessagePermission.EXPORT_CHATS
        }
        
        required_perm = action_mapping.get(action)
        if required_perm and permission.message_permissions:
            if required_perm.value not in permission.message_permissions:
                return False, f"Missing permission: {required_perm.value}"
        
        # Check bulk limits
        if action == "send_bulk" and context:
            if permission.max_bulk_recipients and "recipient_count" in context:
                if context["recipient_count"] > permission.max_bulk_recipients:
                    return False, f"Bulk send exceeds maximum of {permission.max_bulk_recipients} recipients"
        
        # Check rate limits
        if action in ["send_message", "send_bulk"] and permission.max_messages_per_hour:
            # Check usage in last hour
            # This would query the usage logs - simplified here
            return True, None
        
        return True, None
    
    async def _log_feature_usage(
        self,
        db: AsyncSession,
        user: User,
        permission: FeaturePermission,
        feature_type: FeatureType,
        action: str,
        resource_id: Optional[str],
        was_allowed: bool,
        denial_reason: Optional[str],
        context: Optional[Dict[str, Any]] = None
    ):
        """Log feature permission usage."""
        try:
            usage_log = FeatureUsageLog(
                permission_id=permission.id,
                feature_type=feature_type,
                action=action,
                resource_id=resource_id,
                resource_type=context.get("resource_type") if context else None,
                user_id=user.id,
                role_id=user.primary_role_id,
                ip_address=context.get("ip_address") if context else None,
                user_agent=context.get("user_agent") if context else None,
                was_allowed=was_allowed,
                denial_reason=denial_reason,
                data_accessed=context.get("data_accessed") if context else None,
                rows_affected=context.get("rows_affected") if context else None,
                export_format=context.get("export_format") if context else None,
                export_size_mb=context.get("export_size_mb") if context else None,
                processing_time_ms=context.get("processing_time_ms") if context else None,
                usage_cost=permission.cost_per_use,
                request_id=context.get("request_id") if context else None,
                session_id=context.get("session_id") if context else None,
                metadata=context.get("metadata") if context else {}
            )
            
            db.add(usage_log)
            await db.commit()
            
            # Audit log
            await self.audit_service.log(
                db=db,
                action=AuditAction.FEATURE_ACCESS,
                user=user,
                resource_id=resource_id,
                resource_type=f"{feature_type}:{action}",
                details={
                    "feature_type": feature_type,
                    "action": action,
                    "was_allowed": was_allowed,
                    "denial_reason": denial_reason,
                    "permission_id": str(permission.id)
                },
                ip_address=context.get("ip_address") if context else None,
                user_agent=context.get("user_agent") if context else None
            )
            
        except Exception as e:
            logger.error(f"Error logging feature usage: {e}")
    
    async def create_feature_permission(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        feature_type: FeatureType,
        **kwargs
    ) -> FeaturePermission:
        """Create a new feature permission."""
        # Check if user can create permissions
        can_create, reason = await self.check_feature_permission(
            db, user, FeatureType.ADMIN, "manage_permissions"
        )
        if not can_create:
            raise PermissionDeniedError(f"Cannot create permissions: {reason}")
        
        permission = FeaturePermission(
            name=name,
            feature_type=feature_type,
            **kwargs
        )
        
        db.add(permission)
        await db.commit()
        await db.refresh(permission)
        
        # Clear cache
        await self._clear_permission_cache()
        
        # Audit log
        await self.audit_service.log(
            db=db,
            action=AuditAction.PERMISSION_CREATED,
            user=user,
            resource_id=str(permission.id),
            resource_type="feature_permission",
            details={
                "permission_name": name,
                "feature_type": feature_type
            }
        )
        
        return permission
    
    async def update_feature_permission(
        self,
        db: AsyncSession,
        user: User,
        permission_id: str,
        **updates
    ) -> FeaturePermission:
        """Update a feature permission."""
        # Check permission
        can_update, reason = await self.check_feature_permission(
            db, user, FeatureType.ADMIN, "manage_permissions"
        )
        if not can_update:
            raise PermissionDeniedError(f"Cannot update permissions: {reason}")
        
        # Get permission
        permission = await db.get(FeaturePermission, permission_id)
        if not permission:
            raise ResourceNotFoundError("Permission not found")
        
        if permission.is_system:
            raise PermissionDeniedError("Cannot modify system permissions")
        
        # Update fields
        for key, value in updates.items():
            if hasattr(permission, key):
                setattr(permission, key, value)
        
        permission.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(permission)
        
        # Clear cache
        await self._clear_permission_cache()
        
        # Audit log
        await self.audit_service.log(
            db=db,
            action=AuditAction.PERMISSION_UPDATED,
            user=user,
            resource_id=str(permission.id),
            resource_type="feature_permission",
            details={"updates": updates}
        )
        
        return permission
    
    async def delete_feature_permission(
        self,
        db: AsyncSession,
        user: User,
        permission_id: str
    ):
        """Delete a feature permission."""
        # Check permission
        can_delete, reason = await self.check_feature_permission(
            db, user, FeatureType.ADMIN, "manage_permissions"
        )
        if not can_delete:
            raise PermissionDeniedError(f"Cannot delete permissions: {reason}")
        
        # Get permission
        permission = await db.get(FeaturePermission, permission_id)
        if not permission:
            raise ResourceNotFoundError("Permission not found")
        
        if permission.is_system:
            raise PermissionDeniedError("Cannot delete system permissions")
        
        # Delete
        await db.delete(permission)
        await db.commit()
        
        # Clear cache
        await self._clear_permission_cache()
        
        # Audit log
        await self.audit_service.log(
            db=db,
            action=AuditAction.PERMISSION_DELETED,
            user=user,
            resource_id=str(permission_id),
            resource_type="feature_permission",
            details={"permission_name": permission.name}
        )
    
    async def get_user_permissions(
        self,
        db: AsyncSession,
        user: User,
        feature_type: Optional[FeatureType] = None
    ) -> List[FeaturePermission]:
        """Get all permissions for a user."""
        user_role_ids = [role.id for role in user.roles]
        
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.is_active == True,
                or_(
                    FeaturePermission.expires_at.is_(None),
                    FeaturePermission.expires_at > datetime.utcnow()
                ),
                or_(
                    FeaturePermission.user_id == user.id,
                    FeaturePermission.role_id.in_(user_role_ids) if user_role_ids else False,
                    and_(
                        FeaturePermission.agency_id == user.agency_id,
                        FeaturePermission.user_id.is_(None),
                        FeaturePermission.role_id.is_(None)
                    )
                )
            )
        )
        
        if feature_type:
            query = query.where(FeaturePermission.feature_type == feature_type)
        
        result = await db.execute(query.order_by(FeaturePermission.priority.desc()))
        return result.scalars().all()
    
    async def check_quota_usage(
        self,
        db: AsyncSession,
        user: User,
        permission: FeaturePermission,
        period: str = "daily"  # daily or monthly
    ) -> Tuple[int, Optional[int]]:
        """Check quota usage for a permission. Returns (used, limit)."""
        if period == "daily":
            since = datetime.utcnow() - timedelta(days=1)
            limit = permission.usage_quota_daily
        else:
            since = datetime.utcnow() - timedelta(days=30)
            limit = permission.usage_quota_monthly
        
        if not limit:
            return 0, None
        
        # Count usage
        query = select(func.sum(FeatureUsageLog.quota_used)).where(
            and_(
                FeatureUsageLog.permission_id == permission.id,
                FeatureUsageLog.user_id == user.id,
                FeatureUsageLog.timestamp >= since,
                FeatureUsageLog.was_allowed == True
            )
        )
        
        result = await db.execute(query)
        used = result.scalar() or 0
        
        return used, limit
    
    async def _clear_permission_cache(self):
        """Clear all permission cache entries."""
        try:
            # Use pattern to delete all feature permission cache keys
            pattern = "feature_perm:*"
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis_client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Error clearing permission cache: {e}")


# Global instance
feature_permission_service = FeaturePermissionService()