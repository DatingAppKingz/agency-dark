"""
Export-specific permission service for controlling data export functionality.

This service manages export permissions, enforces size/format restrictions,
and tracks export usage for compliance and auditing.
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
import os
import hashlib
import json

from models.user import User, UserRole
from models.feature_permission import (
    FeaturePermission, FeatureUsageLog, FeatureType,
    ExportFormat, DataSensitivity
)
from core.security.feature_permissions.service import feature_permission_service
from core.logger import get_logger
from core.exceptions import PermissionDeniedError, QuotaExceededError
from core.redis import redis_client
from core.audit.service import AuditService
from core.audit.models import AuditAction


logger = get_logger(__name__)


class ExportPermissionService:
    """Service for managing export-specific permissions."""
    
    def __init__(self):
        self.audit_service = AuditService()
        self.rate_limit_window = 3600  # 1 hour in seconds
    
    async def can_export_data(
        self,
        db: AsyncSession,
        user: User,
        export_type: str,
        format: ExportFormat,
        estimated_rows: Optional[int] = None,
        estimated_size_mb: Optional[float] = None,
        data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check if user can export data with given parameters.
        
        Returns:
            Tuple of (allowed, denial_reason, export_limits)
        """
        # Prepare context
        context = {
            "export_type": export_type,
            "format": format.value,
            "row_count": estimated_rows,
            "size_mb": estimated_size_mb,
            "data_sensitivity": data_sensitivity.value
        }
        
        # Check basic feature permission
        allowed, reason = await feature_permission_service.check_feature_permission(
            db, user, FeatureType.EXPORTS, "export_data", export_type, context
        )
        
        if not allowed:
            return False, reason, None
        
        # Get user's export permissions
        permissions = await self._get_export_permissions(db, user)
        
        if not permissions:
            return False, "No export permissions configured", None
        
        # Check each permission and collect limits
        export_limits = {
            "max_rows": None,
            "max_size_mb": None,
            "allowed_formats": set(),
            "rate_limit_per_hour": None,
            "requires_approval": False,
            "watermark_required": False,
            "encryption_required": False
        }
        
        for perm in permissions:
            # Check format restrictions
            if perm.allowed_export_formats:
                export_limits["allowed_formats"].update(perm.allowed_export_formats)
            
            # Check size limits
            if perm.max_export_rows:
                if export_limits["max_rows"] is None or perm.max_export_rows > export_limits["max_rows"]:
                    export_limits["max_rows"] = perm.max_export_rows
            
            if perm.max_export_size_mb:
                if export_limits["max_size_mb"] is None or perm.max_export_size_mb > export_limits["max_size_mb"]:
                    export_limits["max_size_mb"] = perm.max_export_size_mb
            
            # Check rate limits
            if perm.export_rate_limit_per_hour:
                if export_limits["rate_limit_per_hour"] is None or perm.export_rate_limit_per_hour > export_limits["rate_limit_per_hour"]:
                    export_limits["rate_limit_per_hour"] = perm.export_rate_limit_per_hour
            
            # Check approval requirement
            if perm.requires_export_approval:
                export_limits["requires_approval"] = True
            
            # Check data sensitivity
            if not self._check_sensitivity_access(perm.data_sensitivity_level, data_sensitivity):
                continue
        
        # Validate against limits
        if export_limits["allowed_formats"] and format.value not in export_limits["allowed_formats"]:
            return False, f"Export format {format.value} not allowed", export_limits
        
        if estimated_rows and export_limits["max_rows"] and estimated_rows > export_limits["max_rows"]:
            return False, f"Export exceeds maximum of {export_limits['max_rows']} rows", export_limits
        
        if estimated_size_mb and export_limits["max_size_mb"] and estimated_size_mb > export_limits["max_size_mb"]:
            return False, f"Export exceeds maximum size of {export_limits['max_size_mb']} MB", export_limits
        
        # Check rate limits
        if export_limits["rate_limit_per_hour"]:
            current_usage = await self._get_export_usage(db, user)
            if current_usage >= export_limits["rate_limit_per_hour"]:
                return False, f"Export rate limit exceeded ({current_usage}/{export_limits['rate_limit_per_hour']} per hour)", export_limits
        
        # Check approval
        if export_limits["requires_approval"] and not context.get("is_approved"):
            return False, "Export requires approval", export_limits
        
        # Add security requirements based on sensitivity
        if data_sensitivity in [DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED, DataSensitivity.TOP_SECRET]:
            export_limits["watermark_required"] = True
            if data_sensitivity in [DataSensitivity.RESTRICTED, DataSensitivity.TOP_SECRET]:
                export_limits["encryption_required"] = True
        
        return True, None, export_limits
    
    async def _get_export_permissions(
        self,
        db: AsyncSession,
        user: User
    ) -> List[FeaturePermission]:
        """Get export permissions for user."""
        return await feature_permission_service.get_user_permissions(
            db, user, FeatureType.EXPORTS
        )
    
    def _check_sensitivity_access(
        self,
        user_level: Optional[DataSensitivity],
        required_level: DataSensitivity
    ) -> bool:
        """Check if user's sensitivity level meets requirement."""
        if not user_level:
            return required_level == DataSensitivity.PUBLIC
        
        level_hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.RESTRICTED: 3,
            DataSensitivity.TOP_SECRET: 4
        }
        
        return level_hierarchy.get(user_level, 0) >= level_hierarchy.get(required_level, 0)
    
    async def _get_export_usage(
        self,
        db: AsyncSession,
        user: User
    ) -> int:
        """Get number of exports in current rate limit window."""
        # Check cache first
        cache_key = f"export_usage:{user.id}"
        cached = await redis_client.get(cache_key)
        if cached:
            return int(cached)
        
        # Query database
        since = datetime.utcnow() - timedelta(seconds=self.rate_limit_window)
        
        query = select(func.count(FeatureUsageLog.id)).where(
            and_(
                FeatureUsageLog.user_id == user.id,
                FeatureUsageLog.feature_type == FeatureType.EXPORTS,
                FeatureUsageLog.action == "export_data",
                FeatureUsageLog.was_allowed == True,
                FeatureUsageLog.timestamp >= since
            )
        )
        
        result = await db.execute(query)
        count = result.scalar() or 0
        
        # Cache result
        ttl = self.rate_limit_window - int((datetime.utcnow() - since).total_seconds())
        if ttl > 0:
            await redis_client.setex(cache_key, ttl, str(count))
        
        return count
    
    async def prepare_export(
        self,
        db: AsyncSession,
        user: User,
        export_type: str,
        format: ExportFormat,
        data: Any,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare data for export with security features.
        
        Returns:
            Export configuration including security settings
        """
        # Check permissions and get limits
        allowed, reason, limits = await self.can_export_data(
            db, user, export_type, format,
            estimated_rows=metadata.get("row_count"),
            estimated_size_mb=metadata.get("size_mb"),
            data_sensitivity=DataSensitivity(metadata.get("sensitivity", "internal"))
        )
        
        if not allowed:
            raise PermissionDeniedError(f"Export not allowed: {reason}")
        
        # Generate export ID
        export_id = hashlib.sha256(
            f"{user.id}:{export_type}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Prepare export config
        export_config = {
            "export_id": export_id,
            "format": format,
            "user_id": str(user.id),
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata
        }
        
        # Add watermark if required
        if limits.get("watermark_required"):
            export_config["watermark"] = {
                "text": f"Exported by {user.email} on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "user_id": str(user.id),
                "export_id": export_id,
                "agency": user.agency.name if user.agency else "System"
            }
        
        # Add encryption settings if required
        if limits.get("encryption_required"):
            export_config["encryption"] = {
                "algorithm": "AES-256-GCM",
                "key_id": await self._get_encryption_key_id(user),
                "require_password": True
            }
        
        # Log export initiation
        await self._log_export_event(
            db, user, export_type, format, "initiated",
            metadata, export_id
        )
        
        return export_config
    
    async def _get_encryption_key_id(self, user: User) -> str:
        """Get encryption key ID for user exports."""
        # In production, this would retrieve from key management service
        return f"export-key-{user.agency_id or 'system'}"
    
    async def complete_export(
        self,
        db: AsyncSession,
        user: User,
        export_id: str,
        file_path: str,
        file_size_mb: float,
        row_count: int,
        format: ExportFormat
    ) -> Dict[str, Any]:
        """Mark export as completed and return download info."""
        # Update usage counter
        cache_key = f"export_usage:{user.id}"
        current = await redis_client.get(cache_key)
        if current:
            await redis_client.incr(cache_key)
        else:
            # Re-calculate and cache
            usage = await self._get_export_usage(db, user)
            await redis_client.setex(cache_key, self.rate_limit_window, str(usage + 1))
        
        # Generate secure download URL
        download_token = hashlib.sha256(
            f"{export_id}:{user.id}:{datetime.utcnow().timestamp()}".encode()
        ).hexdigest()
        
        # Store download token with expiry
        await redis_client.setex(
            f"export_download:{download_token}",
            3600,  # 1 hour expiry
            json.dumps({
                "export_id": export_id,
                "user_id": str(user.id),
                "file_path": file_path,
                "format": format.value
            })
        )
        
        # Log completion
        await self._log_export_event(
            db, user, "completed", format, "completed",
            {
                "file_size_mb": file_size_mb,
                "row_count": row_count,
                "file_path": file_path
            },
            export_id
        )
        
        return {
            "export_id": export_id,
            "download_token": download_token,
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "file_size_mb": file_size_mb,
            "row_count": row_count,
            "format": format.value
        }
    
    async def _log_export_event(
        self,
        db: AsyncSession,
        user: User,
        export_type: str,
        format: ExportFormat,
        event: str,
        metadata: Dict[str, Any],
        export_id: str
    ):
        """Log export event for auditing."""
        await self.audit_service.log(
            db=db,
            action=AuditAction.DATA_EXPORT,
            user=user,
            resource_id=export_id,
            resource_type=f"export:{export_type}",
            details={
                "export_type": export_type,
                "format": format.value,
                "event": event,
                "metadata": metadata
            }
        )
    
    async def get_export_history(
        self,
        db: AsyncSession,
        user: User,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get user's export history."""
        since = datetime.utcnow() - timedelta(days=days)
        
        query = select(FeatureUsageLog).where(
            and_(
                FeatureUsageLog.user_id == user.id,
                FeatureUsageLog.feature_type == FeatureType.EXPORTS,
                FeatureUsageLog.timestamp >= since,
                FeatureUsageLog.was_allowed == True
            )
        ).order_by(FeatureUsageLog.timestamp.desc()).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        history = []
        for log in logs:
            history.append({
                "timestamp": log.timestamp.isoformat(),
                "export_type": log.resource_type,
                "format": log.export_format,
                "rows": log.rows_affected,
                "size_mb": log.export_size_mb,
                "export_id": log.resource_id
            })
        
        return history
    
    async def request_export_approval(
        self,
        db: AsyncSession,
        user: User,
        export_type: str,
        format: ExportFormat,
        justification: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Request approval for an export that requires it."""
        # Create approval request ID
        request_id = hashlib.sha256(
            f"approval:{user.id}:{export_type}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Store approval request
        await redis_client.setex(
            f"export_approval:{request_id}",
            86400 * 7,  # 7 days expiry
            json.dumps({
                "user_id": str(user.id),
                "export_type": export_type,
                "format": format.value,
                "justification": justification,
                "metadata": metadata,
                "requested_at": datetime.utcnow().isoformat(),
                "status": "pending"
            })
        )
        
        # Log approval request
        await self.audit_service.log(
            db=db,
            action=AuditAction.APPROVAL_REQUESTED,
            user=user,
            resource_id=request_id,
            resource_type="export_approval",
            details={
                "export_type": export_type,
                "format": format.value,
                "justification": justification
            }
        )
        
        # TODO: Send notification to approvers
        
        return request_id
    
    async def check_export_quota(
        self,
        db: AsyncSession,
        user: User
    ) -> Dict[str, Any]:
        """Check user's export quota usage."""
        # Get permissions
        permissions = await self._get_export_permissions(db, user)
        
        # Get current usage
        current_usage = await self._get_export_usage(db, user)
        
        # Find applicable rate limit
        max_rate_limit = 0
        for perm in permissions:
            if perm.export_rate_limit_per_hour:
                if perm.export_rate_limit_per_hour > max_rate_limit:
                    max_rate_limit = perm.export_rate_limit_per_hour
        
        # Get quota usage (daily/monthly)
        daily_quota, daily_limit = await feature_permission_service.check_quota_usage(
            db, user, permissions[0] if permissions else None, "daily"
        )
        
        monthly_quota, monthly_limit = await feature_permission_service.check_quota_usage(
            db, user, permissions[0] if permissions else None, "monthly"
        )
        
        return {
            "hourly": {
                "used": current_usage,
                "limit": max_rate_limit,
                "remaining": max(0, max_rate_limit - current_usage) if max_rate_limit else None
            },
            "daily": {
                "used": daily_quota,
                "limit": daily_limit,
                "remaining": max(0, daily_limit - daily_quota) if daily_limit else None
            },
            "monthly": {
                "used": monthly_quota,
                "limit": monthly_limit,
                "remaining": max(0, monthly_limit - monthly_quota) if monthly_limit else None
            }
        }


# Global instance
export_permission_service = ExportPermissionService()