"""
Feature permission service for checking and enforcing permissions.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.feature_permission import (
    FeaturePermission, FeatureType, AnalyticsScope,
    DataSensitivity, FeatureUsageLog
)
from models.user import User
from core.logger import get_logger

logger = get_logger(__name__)


class FeaturePermissionService:
    """Service for managing feature permissions."""
    
    async def check_feature_permission(
        self,
        db: AsyncSession,
        user: User,
        feature_type: FeatureType,
        action: str,
        resource_id: Optional[str] = None
    ) -> bool:
        """Check if user has permission for a specific feature action."""
        # Admin users have all permissions
        if user.role == "admin":
            return True
        
        # Get user's feature permissions
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.is_active == True,
                or_(
                    FeaturePermission.user_id == user.id,
                    FeaturePermission.role_id == user.role_id if hasattr(user, 'role_id') else None
                ),
                FeaturePermission.feature_type == feature_type
            )
        )
        
        result = await db.execute(query)
        permissions = result.scalars().all()
        
        if not permissions:
            # No specific permissions, deny by default
            await self._log_usage(
                db, None, feature_type, action, user.id,
                False, "no_permission"
            )
            return False
        
        # Check each permission
        for perm in permissions:
            # Check time restrictions
            if not self._check_time_restrictions(perm):
                continue
            
            # Check if action is explicitly denied
            if action in (perm.denied_actions or []):
                await self._log_usage(
                    db, perm.id, feature_type, action, user.id,
                    False, "action_denied"
                )
                return False
            
            # Check if action is allowed
            if action in (perm.allowed_actions or []) or "*" in (perm.allowed_actions or []):
                await self._log_usage(
                    db, perm.id, feature_type, action, user.id,
                    True, None
                )
                return True
        
        # No matching permission found
        await self._log_usage(
            db, None, feature_type, action, user.id,
            False, "action_not_allowed"
        )
        return False
    
    async def get_data_filter(
        self,
        db: AsyncSession,
        user: User,
        feature_type: FeatureType
    ) -> Dict[str, Any]:
        """Get data filtering rules for a user."""
        # Admin users see all data
        if user.role == "admin":
            return {"scope": "global", "filters": {}}
        
        # Get user's feature permissions
        query = select(FeaturePermission).where(
            and_(
                FeaturePermission.is_active == True,
                or_(
                    FeaturePermission.user_id == user.id,
                    FeaturePermission.role_id == user.role_id if hasattr(user, 'role_id') else None
                ),
                FeaturePermission.feature_type == feature_type
            )
        )
        
        result = await db.execute(query)
        permissions = result.scalars().all()
        
        if not permissions:
            # Default to own data only
            return {"scope": "own", "filters": {"user_id": user.id}}
        
        # Find the most permissive scope
        max_scope = AnalyticsScope.OWN
        for perm in permissions:
            if perm.analytics_scope:
                if perm.analytics_scope == AnalyticsScope.GLOBAL:
                    max_scope = AnalyticsScope.GLOBAL
                    break
                elif perm.analytics_scope == AnalyticsScope.AGENCY and max_scope != AnalyticsScope.GLOBAL:
                    max_scope = AnalyticsScope.AGENCY
                elif perm.analytics_scope == AnalyticsScope.TEAM and max_scope == AnalyticsScope.OWN:
                    max_scope = AnalyticsScope.TEAM
        
        # Build filters based on scope
        filters = {}
        if max_scope == AnalyticsScope.OWN:
            filters["user_id"] = user.id
        elif max_scope == AnalyticsScope.TEAM:
            filters["team_id"] = getattr(user, "team_id", None)
        elif max_scope == AnalyticsScope.AGENCY:
            filters["agency_id"] = getattr(user, "agency_id", None)
        # GLOBAL has no filters
        
        return {"scope": max_scope.value, "filters": filters}
    
    def _check_time_restrictions(self, permission: FeaturePermission) -> bool:
        """Check if current time is within allowed access times."""
        if not permission.access_start_time and not permission.access_end_time:
            return True
        
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.weekday()
        
        # Check day of week
        if permission.access_days_of_week and current_day not in permission.access_days_of_week:
            return False
        
        # Check time range
        if permission.access_start_time and current_time < permission.access_start_time:
            return False
        
        if permission.access_end_time and current_time > permission.access_end_time:
            return False
        
        return True
    
    async def _log_usage(
        self,
        db: AsyncSession,
        permission_id: Optional[str],
        feature_type: FeatureType,
        action: str,
        user_id: str,
        was_allowed: bool,
        denial_reason: Optional[str] = None
    ):
        """Log feature usage attempt."""
        log = FeatureUsageLog(
            permission_id=permission_id,
            feature_type=feature_type,
            action=action,
            user_id=user_id,
            was_allowed=was_allowed,
            denial_reason=denial_reason
        )
        db.add(log)
        # Don't commit here, let the caller handle it


# Global instance
feature_permission_service = FeaturePermissionService()