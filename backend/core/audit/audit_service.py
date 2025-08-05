"""
Comprehensive audit logging service for tracking all system activities.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import json
from contextlib import asynccontextmanager

from models.audit_log import AuditLog, AuditAction, AuditSeverity, AuditLogAlert
from models.user import User
from models.platform_api_key import PlatformAPIKey
from core.redis import redis_manager
from core.logger import get_logger

logger = get_logger(__name__)


class AuditService:
    """Service for comprehensive audit logging."""
    
    def __init__(self):
        self.batch_size = 100
        self.cache_ttl = 300  # 5 minutes
        self._pending_logs: List[Dict[str, Any]] = []
        self._batch_lock = False
    
    async def log(
        self,
        db: AsyncSession,
        action: AuditAction,
        user: Optional[User] = None,
        user_id: Optional[str] = None,
        agency_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        description: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        risk_score: Optional[int] = None,
        duration_ms: Optional[int] = None,
        api_key: Optional[PlatformAPIKey] = None,
        impersonator: Optional[User] = None,
        batch: bool = False
    ) -> Optional[AuditLog]:
        """
        Log an audit event.
        
        Args:
            db: Database session
            action: The action being logged
            user: User object (optional if user_id provided)
            user_id: User ID (optional if user provided)
            agency_id: Agency ID
            resource_type: Type of resource affected
            resource_id: ID of affected resource
            resource_name: Human-readable name
            description: Human-readable description
            changes: Before/after values for updates
            metadata: Additional context
            ip_address: Client IP
            user_agent: Client user agent
            session_id: Session identifier
            request_id: Request identifier
            correlation_id: Cross-service correlation ID
            severity: Event severity
            risk_score: Risk assessment (0-100)
            duration_ms: Operation duration
            api_key: API key used
            impersonator: User impersonating another
            batch: Whether to batch this log
            
        Returns:
            Created audit log or None if batched
        """
        try:
            # Extract user information
            if user:
                user_id = user_id or str(user.id)
                agency_id = agency_id or (str(user.agency_id) if user.agency_id else None)
            
            # Calculate risk score if not provided
            if risk_score is None:
                risk_score = await self._calculate_risk_score(
                    action=action,
                    user_id=user_id,
                    ip_address=ip_address,
                    severity=severity,
                    metadata=metadata
                )
            
            # Auto-generate description if not provided
            if not description:
                description = await self._generate_description(
                    action=action,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    user=user
                )
            
            # Create audit log data
            audit_data = {
                "user_id": user_id,
                "agency_id": agency_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "resource_name": resource_name,
                "description": description,
                "changes": changes,
                "metadata": metadata,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "session_id": session_id,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "severity": severity,
                "risk_score": risk_score,
                "duration_ms": duration_ms,
                "api_key_id": str(api_key.id) if api_key else None,
                "impersonator_id": str(impersonator.id) if impersonator else None
            }
            
            # Handle batching
            if batch:
                self._pending_logs.append(audit_data)
                if len(self._pending_logs) >= self.batch_size:
                    await self._flush_batch(db)
                return None
            
            # Create and save audit log
            audit_log = AuditLog(**audit_data)
            db.add(audit_log)
            await db.commit()
            await db.refresh(audit_log)
            
            # Check for alerts
            await self._check_alerts(db, audit_log)
            
            # Update analytics
            await self._update_analytics(audit_log)
            
            logger.debug(
                f"Audit logged: {action.value} by user {user_id} "
                f"on {resource_type}/{resource_id}"
            )
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            # Don't fail the operation due to audit logging failure
            return None
    
    async def log_login(
        self,
        db: AsyncSession,
        user: User,
        success: bool,
        ip_address: str,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None
    ):
        """Log login attempt."""
        action = AuditAction.LOGIN if success else AuditAction.LOGIN_FAILED
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        
        metadata = {
            "login_method": "password",  # Could be extended for OAuth, SSO, etc.
            "success": success
        }
        
        if failure_reason:
            metadata["failure_reason"] = failure_reason
        
        await self.log(
            db=db,
            action=action,
            user=user if success else None,
            user_id=str(user.id) if user else None,
            description=f"Login {'successful' if success else 'failed'} for {user.email if user else 'unknown user'}",
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity,
            risk_score=0 if success else 50  # Failed logins have moderate risk
        )
    
    async def log_data_access(
        self,
        db: AsyncSession,
        user: User,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: Optional[str] = None,
        **kwargs
    ):
        """Log data access for compliance."""
        await self.log(
            db=db,
            action=AuditAction.ANALYTICS_VIEWED,  # Generic data access
            user=user,
            resource_type=resource_type,
            resource_id=resource_id,
            description=f"User accessed {resource_type} data",
            metadata={
                "access_type": action,
                "additional_filters": kwargs
            },
            ip_address=ip_address,
            severity=AuditSeverity.INFO
        )
    
    async def log_financial_action(
        self,
        db: AsyncSession,
        user: User,
        action: AuditAction,
        amount: float,
        currency: str,
        transaction_id: Optional[str] = None,
        **kwargs
    ):
        """Log financial actions with enhanced tracking."""
        metadata = {
            "amount": amount,
            "currency": currency,
            "transaction_id": transaction_id,
            **kwargs
        }
        
        # Financial actions have higher severity
        severity = AuditSeverity.WARNING if amount > 1000 else AuditSeverity.INFO
        
        await self.log(
            db=db,
            action=action,
            user=user,
            resource_type="transaction",
            resource_id=transaction_id,
            metadata=metadata,
            severity=severity,
            risk_score=min(int(amount / 100), 100)  # Risk based on amount
        )
    
    async def search(
        self,
        db: AsyncSession,
        user: User,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[AuditAction]] = None,
        user_ids: Optional[List[str]] = None,
        resource_types: Optional[List[str]] = None,
        resource_ids: Optional[List[str]] = None,
        severities: Optional[List[AuditSeverity]] = None,
        ip_address: Optional[str] = None,
        text_search: Optional[str] = None,
        flagged_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[AuditLog], int]:
        """
        Search audit logs with filters.
        
        Returns:
            Tuple of (logs, total_count)
        """
        # Build base query
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))
        
        # Apply filters
        filters = []
        
        # Date range
        if start_date:
            filters.append(AuditLog.timestamp >= start_date)
        if end_date:
            filters.append(AuditLog.timestamp <= end_date)
        
        # Actions
        if actions:
            filters.append(AuditLog.action.in_(actions))
        
        # Users (check permissions)
        if user_ids:
            # Only super admins can search other users' logs
            if user.role.value != "SUPER_ADMIN":
                user_ids = [str(user.id)]
            filters.append(AuditLog.user_id.in_(user_ids))
        elif user.role.value != "SUPER_ADMIN":
            # Non-super admins can only see their own logs
            filters.append(AuditLog.user_id == str(user.id))
        
        # Resources
        if resource_types:
            filters.append(AuditLog.resource_type.in_(resource_types))
        if resource_ids:
            filters.append(AuditLog.resource_id.in_(resource_ids))
        
        # Severity
        if severities:
            filters.append(AuditLog.severity.in_(severities))
        
        # IP address
        if ip_address:
            filters.append(AuditLog.ip_address == ip_address)
        
        # Flagged only
        if flagged_only:
            filters.append(AuditLog.flagged == True)
        
        # Text search (PostgreSQL full-text search)
        if text_search:
            search_filter = or_(
                AuditLog.description.ilike(f"%{text_search}%"),
                AuditLog.resource_name.ilike(f"%{text_search}%"),
                text(f"metadata::text ILIKE '%{text_search}%'")
            )
            filters.append(search_filter)
        
        # Apply filters
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Get total count
        count_result = await db.execute(count_query)
        total_count = count_result.scalar() or 0
        
        # Apply ordering and pagination
        query = query.order_by(AuditLog.timestamp.desc())
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # Log the search itself
        await self.log(
            db=db,
            action=AuditAction.AUDIT_EXPORTED,
            user=user,
            description=f"Searched audit logs, found {len(logs)} results",
            metadata={
                "filters": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "actions": [a.value for a in actions] if actions else None,
                    "text_search": text_search
                }
            }
        )
        
        return logs, total_count
    
    async def get_user_activity_summary(
        self,
        db: AsyncSession,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get activity summary for a user."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get action counts
        result = await db.execute(
            select(
                AuditLog.action,
                func.count(AuditLog.id)
            ).where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.timestamp >= start_date
                )
            ).group_by(AuditLog.action)
        )
        action_counts = dict(result.all())
        
        # Get daily activity
        result = await db.execute(
            select(
                func.date_trunc('day', AuditLog.timestamp).label('day'),
                func.count(AuditLog.id)
            ).where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.timestamp >= start_date
                )
            ).group_by(text('day'))
        )
        daily_activity = [
            {"date": row[0].isoformat(), "count": row[1]}
            for row in result.all()
        ]
        
        # Get risk events
        result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.timestamp >= start_date,
                    AuditLog.risk_score > 50
                )
            )
        )
        high_risk_count = result.scalar() or 0
        
        return {
            "user_id": user_id,
            "period_days": days,
            "total_actions": sum(action_counts.values()),
            "action_breakdown": {k.value: v for k, v in action_counts.items()},
            "daily_activity": daily_activity,
            "high_risk_events": high_risk_count
        }
    
    async def _calculate_risk_score(
        self,
        action: AuditAction,
        user_id: Optional[str],
        ip_address: Optional[str],
        severity: AuditSeverity,
        metadata: Optional[Dict[str, Any]]
    ) -> int:
        """Calculate risk score for an audit event."""
        score = 0
        
        # Base score by severity
        severity_scores = {
            AuditSeverity.INFO: 0,
            AuditSeverity.WARNING: 25,
            AuditSeverity.ERROR: 50,
            AuditSeverity.CRITICAL: 75
        }
        score += severity_scores.get(severity, 0)
        
        # High-risk actions
        high_risk_actions = [
            AuditAction.USER_DELETED,
            AuditAction.TRANSACTION_DELETED,
            AuditAction.API_KEY_CREATED,
            AuditAction.PERMISSION_GRANTED,
            AuditAction.DATA_EXPORTED
        ]
        if action in high_risk_actions:
            score += 25
        
        # Check for suspicious patterns
        if redis_manager and user_id:
            # Check recent failed logins
            failed_login_key = f"audit:failed_logins:{user_id}"
            failed_count = await redis_manager.get(failed_login_key)
            if failed_count and int(failed_count) > 3:
                score += 20
        
        # Cap at 100
        return min(score, 100)
    
    async def _generate_description(
        self,
        action: AuditAction,
        resource_type: Optional[str],
        resource_name: Optional[str],
        user: Optional[User]
    ) -> str:
        """Generate human-readable description."""
        user_name = user.email if user else "Unknown user"
        
        descriptions = {
            AuditAction.LOGIN: f"{user_name} logged in",
            AuditAction.LOGOUT: f"{user_name} logged out",
            AuditAction.USER_CREATED: f"Created user {resource_name or resource_type}",
            AuditAction.USER_UPDATED: f"Updated user {resource_name or resource_type}",
            AuditAction.USER_DELETED: f"Deleted user {resource_name or resource_type}",
        }
        
        return descriptions.get(
            action,
            f"{user_name} performed {action.value} on {resource_type or 'system'}"
        )
    
    async def _check_alerts(self, db: AsyncSession, audit_log: AuditLog):
        """Check if this audit log triggers any alerts."""
        # Get active alerts
        result = await db.execute(
            select(AuditLogAlert).where(AuditLogAlert.is_active == True)
        )
        alerts = result.scalars().all()
        
        for alert in alerts:
            # Check action pattern
            if alert.action_pattern:
                import re
                if not re.match(alert.action_pattern, audit_log.action.value):
                    continue
            
            # Check severity
            if alert.severity_threshold:
                severity_values = {
                    AuditSeverity.INFO: 0,
                    AuditSeverity.WARNING: 1,
                    AuditSeverity.ERROR: 2,
                    AuditSeverity.CRITICAL: 3
                }
                if severity_values[audit_log.severity] < severity_values[alert.severity_threshold]:
                    continue
            
            # Check risk score
            if alert.risk_score_threshold and audit_log.risk_score < alert.risk_score_threshold:
                continue
            
            # Check threshold
            if alert.threshold_count and alert.threshold_minutes:
                window_start = datetime.utcnow() - timedelta(minutes=alert.threshold_minutes)
                count_result = await db.execute(
                    select(func.count(AuditLog.id)).where(
                        and_(
                            AuditLog.timestamp >= window_start,
                            AuditLog.action == audit_log.action
                        )
                    )
                )
                count = count_result.scalar() or 0
                
                if count >= alert.threshold_count:
                    # Trigger alert
                    await self._trigger_alert(alert, audit_log)
    
    async def _trigger_alert(self, alert: AuditLogAlert, audit_log: AuditLog):
        """Trigger an alert."""
        logger.warning(
            f"Alert triggered: {alert.name} for action {audit_log.action.value}"
        )
        
        # Update alert
        alert.last_triggered = datetime.utcnow()
        alert.trigger_count += 1
        
        # Send notifications (implement based on your notification system)
        # TODO: Implement email, webhook, and in-app notifications
    
    async def _update_analytics(self, audit_log: AuditLog):
        """Update real-time analytics."""
        if not redis_manager:
            return
        
        # Update counters
        today = datetime.utcnow().date().isoformat()
        
        # Daily action counter
        action_key = f"audit:daily:{today}:{audit_log.action.value}"
        await redis_manager.incr(action_key)
        await redis_manager.expire(action_key, 86400 * 7)  # Keep for 7 days
        
        # User activity counter
        if audit_log.user_id:
            user_key = f"audit:user:{audit_log.user_id}:{today}"
            await redis_manager.incr(user_key)
            await redis_manager.expire(user_key, 86400 * 30)  # Keep for 30 days
    
    async def _flush_batch(self, db: AsyncSession):
        """Flush pending batch logs."""
        if not self._pending_logs or self._batch_lock:
            return
        
        try:
            self._batch_lock = True
            logs_to_insert = self._pending_logs[:self.batch_size]
            self._pending_logs = self._pending_logs[self.batch_size:]
            
            # Bulk insert
            db.add_all([AuditLog(**log_data) for log_data in logs_to_insert])
            await db.commit()
            
            logger.info(f"Flushed {len(logs_to_insert)} audit logs")
        finally:
            self._batch_lock = False
    
    @asynccontextmanager
    async def batch_context(self, db: AsyncSession):
        """Context manager for batch logging."""
        try:
            yield
        finally:
            # Flush any remaining logs
            await self._flush_batch(db)


# Global audit service instance
audit_service = AuditService()