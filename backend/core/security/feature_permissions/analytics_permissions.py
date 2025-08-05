"""
Analytics-specific permission service for controlling analytics data access.

This service manages analytics permissions, enforces data scope restrictions,
and filters analytics data based on user roles and permissions.
"""
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import json

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope,
    DataSensitivity
)
from core.security.feature_permissions.service import feature_permission_service
from core.logger import get_logger
from core.exceptions import PermissionDeniedError
from core.redis import redis_client


logger = get_logger(__name__)


class AnalyticsPermissionService:
    """Service for managing analytics-specific permissions."""
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes
    
    async def check_analytics_access(
        self,
        db: AsyncSession,
        user: User,
        analytics_type: str,
        requested_scope: AnalyticsScope = AnalyticsScope.OWN,
        metrics: Optional[List[str]] = None,
        date_range: Optional[Dict[str, datetime]] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check if user can access analytics with given parameters.
        
        Returns:
            Tuple of (allowed, denial_reason, data_filters)
        """
        # Prepare context
        context = {
            "analytics_type": analytics_type,
            "scope": requested_scope.value,
            "metrics": metrics or [],
            "includes_revenue": any(m in ["revenue", "earnings", "income"] for m in (metrics or [])),
            "includes_costs": any(m in ["costs", "expenses", "fees"] for m in (metrics or []))
        }
        
        if date_range:
            context["date_range"] = date_range
            if "start" in date_range and "end" in date_range:
                context["date_range_days"] = (date_range["end"] - date_range["start"]).days
        
        # Check basic feature permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.ANALYTICS, "view_analytics", analytics_type, context
        )
        
        if not allowed:
            return False, reason, None
        
        # Get user's analytics permissions
        permissions = await self._get_analytics_permissions(db, user)
        
        if not permissions:
            return False, "No analytics permissions configured", None
        
        # Check scope access
        max_scope = await self._get_max_analytics_scope(permissions)
        if not self._check_scope_access(max_scope, requested_scope):
            return False, f"Analytics scope '{requested_scope.value}' not allowed", None
        
        # Check metric permissions
        allowed_metrics = await self._get_allowed_metrics(permissions)
        if metrics and allowed_metrics is not None:  # None means all metrics allowed
            denied_metrics = set(metrics) - allowed_metrics
            if denied_metrics:
                return False, f"Metrics not allowed: {', '.join(denied_metrics)}", None
        
        # Check financial data access
        can_view_revenue = any(p.can_view_revenue_data for p in permissions)
        can_view_costs = any(p.can_view_cost_data for p in permissions)
        
        if context["includes_revenue"] and not can_view_revenue:
            return False, "No permission to view revenue data", None
        
        if context["includes_costs"] and not can_view_costs:
            return False, "No permission to view cost data", None
        
        # Build data filters based on scope and permissions
        data_filters = await self._build_data_filters(db, user, requested_scope, permissions)
        
        return True, None, data_filters
    
    async def _get_analytics_permissions(
        self,
        db: AsyncSession,
        user: User
    ) -> List[FeaturePermission]:
        """Get analytics permissions for user."""
        return await feature_permission_service.get_user_permissions(
            db, user, FeatureType.ANALYTICS
        )
    
    async def _get_max_analytics_scope(
        self,
        permissions: List[FeaturePermission]
    ) -> AnalyticsScope:
        """Get maximum analytics scope from permissions."""
        scope_hierarchy = {
            AnalyticsScope.OWN: 0,
            AnalyticsScope.TEAM: 1,
            AnalyticsScope.AGENCY: 2,
            AnalyticsScope.GLOBAL: 3
        }
        
        max_scope = AnalyticsScope.OWN
        max_level = 0
        
        for perm in permissions:
            if perm.analytics_scope:
                level = scope_hierarchy.get(perm.analytics_scope, 0)
                if level > max_level:
                    max_level = level
                    max_scope = perm.analytics_scope
        
        return max_scope
    
    def _check_scope_access(
        self,
        user_scope: AnalyticsScope,
        requested_scope: AnalyticsScope
    ) -> bool:
        """Check if user's scope allows requested scope."""
        scope_hierarchy = {
            AnalyticsScope.OWN: 0,
            AnalyticsScope.TEAM: 1,
            AnalyticsScope.AGENCY: 2,
            AnalyticsScope.GLOBAL: 3
        }
        
        return scope_hierarchy.get(user_scope, 0) >= scope_hierarchy.get(requested_scope, 0)
    
    async def _get_allowed_metrics(
        self,
        permissions: List[FeaturePermission]
    ) -> Optional[Set[str]]:
        """Get set of allowed metrics from permissions."""
        # If any permission has no metric restrictions, allow all
        for perm in permissions:
            if not perm.allowed_metrics:
                return None
        
        # Otherwise, combine all allowed metrics
        allowed = set()
        for perm in permissions:
            if perm.allowed_metrics:
                allowed.update(perm.allowed_metrics)
        
        return allowed
    
    async def _build_data_filters(
        self,
        db: AsyncSession,
        user: User,
        scope: AnalyticsScope,
        permissions: List[FeaturePermission]
    ) -> Dict[str, Any]:
        """Build data filters based on scope and permissions."""
        filters = {
            "scope": scope.value,
            "user_id": str(user.id),
            "agency_id": str(user.agency_id) if user.agency_id else None
        }
        
        # Apply scope-based filters
        if scope == AnalyticsScope.OWN:
            # Only user's own data
            filters["filter_user_id"] = str(user.id)
            
            # For models, include their fans/chatters data
            if user.role == UserRole.MODEL:
                filters["include_related_users"] = True
        
        elif scope == AnalyticsScope.TEAM:
            # Team members' data
            team_ids = await self._get_team_member_ids(db, user)
            filters["filter_user_ids"] = team_ids
        
        elif scope == AnalyticsScope.AGENCY:
            # All agency data
            filters["filter_agency_id"] = str(user.agency_id)
        
        elif scope == AnalyticsScope.GLOBAL:
            # No filters for global scope (admin only)
            pass
        
        # Add metric filters
        allowed_metrics = await self._get_allowed_metrics(permissions)
        if allowed_metrics is not None:
            filters["allowed_metrics"] = list(allowed_metrics)
        
        # Add financial data flags
        filters["include_revenue"] = any(p.can_view_revenue_data for p in permissions)
        filters["include_costs"] = any(p.can_view_cost_data for p in permissions)
        
        # Add custom metric creation flag
        filters["can_create_custom"] = any(p.can_create_custom_metrics for p in permissions)
        
        return filters
    
    async def _get_team_member_ids(
        self,
        db: AsyncSession,
        user: User
    ) -> List[str]:
        """Get IDs of team members for team scope."""
        # This would query team membership tables
        # For now, return empty list
        return []
    
    async def get_analytics_dashboards(
        self,
        db: AsyncSession,
        user: User
    ) -> List[Dict[str, Any]]:
        """Get available analytics dashboards for user."""
        # Check cache
        cache_key = f"analytics_dashboards:{user.id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Get permissions
        permissions = await self._get_analytics_permissions(db, user)
        max_scope = await self._get_max_analytics_scope(permissions)
        allowed_metrics = await self._get_allowed_metrics(permissions)
        
        # Build dashboard list based on permissions
        dashboards = []
        
        # Personal dashboard (always available)
        dashboards.append({
            "id": "personal",
            "name": "Personal Analytics",
            "description": "Your personal performance metrics",
            "scope": AnalyticsScope.OWN.value,
            "available_metrics": self._get_personal_metrics(user.role)
        })
        
        # Team dashboard
        if self._check_scope_access(max_scope, AnalyticsScope.TEAM):
            dashboards.append({
                "id": "team",
                "name": "Team Analytics",
                "description": "Team performance and collaboration metrics",
                "scope": AnalyticsScope.TEAM.value,
                "available_metrics": self._get_team_metrics()
            })
        
        # Agency dashboard
        if self._check_scope_access(max_scope, AnalyticsScope.AGENCY):
            dashboards.append({
                "id": "agency",
                "name": "Agency Analytics",
                "description": "Agency-wide performance and business metrics",
                "scope": AnalyticsScope.AGENCY.value,
                "available_metrics": self._get_agency_metrics(permissions)
            })
        
        # Global dashboard (admin only)
        if self._check_scope_access(max_scope, AnalyticsScope.GLOBAL):
            dashboards.append({
                "id": "global",
                "name": "Global Analytics",
                "description": "Platform-wide analytics and insights",
                "scope": AnalyticsScope.GLOBAL.value,
                "available_metrics": self._get_global_metrics()
            })
        
        # Filter metrics by permission
        if allowed_metrics is not None:
            for dashboard in dashboards:
                dashboard["available_metrics"] = [
                    m for m in dashboard["available_metrics"]
                    if m["id"] in allowed_metrics
                ]
        
        # Cache result
        await redis_client.setex(cache_key, self.cache_ttl, json.dumps(dashboards))
        
        return dashboards
    
    def _get_personal_metrics(self, role: UserRole) -> List[Dict[str, str]]:
        """Get personal metrics based on role."""
        base_metrics = [
            {"id": "messages_sent", "name": "Messages Sent", "category": "activity"},
            {"id": "response_time", "name": "Avg Response Time", "category": "performance"},
            {"id": "active_hours", "name": "Active Hours", "category": "activity"}
        ]
        
        if role == UserRole.MODEL:
            base_metrics.extend([
                {"id": "fans_count", "name": "Total Fans", "category": "audience"},
                {"id": "new_fans", "name": "New Fans", "category": "growth"},
                {"id": "fan_retention", "name": "Fan Retention", "category": "engagement"}
            ])
        elif role == UserRole.CHATTER:
            base_metrics.extend([
                {"id": "conversations", "name": "Conversations Handled", "category": "activity"},
                {"id": "conversion_rate", "name": "Conversion Rate", "category": "performance"},
                {"id": "satisfaction_score", "name": "Satisfaction Score", "category": "quality"}
            ])
        
        return base_metrics
    
    def _get_team_metrics(self) -> List[Dict[str, str]]:
        """Get team-level metrics."""
        return [
            {"id": "team_messages", "name": "Team Messages", "category": "activity"},
            {"id": "team_response_time", "name": "Team Response Time", "category": "performance"},
            {"id": "team_coverage", "name": "Coverage Hours", "category": "availability"},
            {"id": "team_workload", "name": "Workload Distribution", "category": "efficiency"}
        ]
    
    def _get_agency_metrics(self, permissions: List[FeaturePermission]) -> List[Dict[str, str]]:
        """Get agency-level metrics."""
        metrics = [
            {"id": "total_models", "name": "Total Models", "category": "scale"},
            {"id": "total_fans", "name": "Total Fans", "category": "audience"},
            {"id": "active_users", "name": "Active Users", "category": "engagement"}
        ]
        
        # Add revenue metrics if permitted
        if any(p.can_view_revenue_data for p in permissions):
            metrics.extend([
                {"id": "revenue", "name": "Total Revenue", "category": "financial"},
                {"id": "avg_revenue_per_model", "name": "Avg Revenue/Model", "category": "financial"},
                {"id": "revenue_growth", "name": "Revenue Growth", "category": "financial"}
            ])
        
        # Add cost metrics if permitted
        if any(p.can_view_cost_data for p in permissions):
            metrics.extend([
                {"id": "costs", "name": "Total Costs", "category": "financial"},
                {"id": "profit_margin", "name": "Profit Margin", "category": "financial"},
                {"id": "cost_per_acquisition", "name": "Cost per Acquisition", "category": "efficiency"}
            ])
        
        return metrics
    
    def _get_global_metrics(self) -> List[Dict[str, str]]:
        """Get global platform metrics."""
        return [
            {"id": "platform_users", "name": "Platform Users", "category": "scale"},
            {"id": "platform_revenue", "name": "Platform Revenue", "category": "financial"},
            {"id": "platform_growth", "name": "Platform Growth", "category": "growth"},
            {"id": "system_health", "name": "System Health", "category": "technical"},
            {"id": "api_usage", "name": "API Usage", "category": "technical"}
        ]
    
    async def create_custom_metric(
        self,
        db: AsyncSession,
        user: User,
        name: str,
        formula: str,
        category: str,
        scope: AnalyticsScope
    ) -> Dict[str, Any]:
        """Create a custom metric if user has permission."""
        # Check permission
        allowed, reason, _ = await self.check_analytics_access(
            db, user, "custom_metrics", scope
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot create custom metric: {reason}")
        
        # Get permissions to check if custom metrics allowed
        permissions = await self._get_analytics_permissions(db, user)
        if not any(p.can_create_custom_metrics for p in permissions):
            raise PermissionDeniedError("No permission to create custom metrics")
        
        # Validate formula (simplified - in production would parse and validate)
        if not self._validate_metric_formula(formula):
            raise ValueError("Invalid metric formula")
        
        # Generate metric ID
        metric_id = f"custom_{user.id}_{name.lower().replace(' ', '_')}"
        
        # Store custom metric (in production, would save to database)
        metric_data = {
            "id": metric_id,
            "name": name,
            "formula": formula,
            "category": category,
            "scope": scope.value,
            "created_by": str(user.id),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Cache the custom metric
        cache_key = f"custom_metric:{metric_id}"
        await redis_client.setex(cache_key, 86400, json.dumps(metric_data))  # 24 hour cache
        
        return metric_data
    
    def _validate_metric_formula(self, formula: str) -> bool:
        """Validate a metric formula for safety."""
        # Basic validation - in production would use proper parser
        forbidden_keywords = ["drop", "delete", "update", "insert", "exec", "system"]
        formula_lower = formula.lower()
        
        for keyword in forbidden_keywords:
            if keyword in formula_lower:
                return False
        
        # Check for basic mathematical operations
        allowed_chars = set("0123456789+-*/().,_ abcdefghijklmnopqrstuvwxyz")
        if not all(c.lower() in allowed_chars for c in formula):
            return False
        
        return True
    
    async def get_metric_data(
        self,
        db: AsyncSession,
        user: User,
        metric_id: str,
        scope: AnalyticsScope,
        date_range: Dict[str, datetime],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get data for a specific metric with permission checks."""
        # Check access
        allowed, reason, data_filters = await self.check_analytics_access(
            db, user, "metrics", scope, [metric_id], date_range
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Cannot access metric: {reason}")
        
        # Merge filters
        if filters:
            data_filters.update(filters)
        
        # In production, this would query the actual data
        # For now, return mock data
        return {
            "metric_id": metric_id,
            "scope": scope.value,
            "date_range": {
                "start": date_range["start"].isoformat(),
                "end": date_range["end"].isoformat()
            },
            "filters": data_filters,
            "data": {
                "values": [],  # Time series data would go here
                "summary": {
                    "total": 0,
                    "average": 0,
                    "min": 0,
                    "max": 0
                }
            }
        }


# Global instance
analytics_permission_service = AnalyticsPermissionService()