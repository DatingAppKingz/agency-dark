"""
Feature permission decorators for endpoint-level access control.

These decorators provide a convenient way to enforce feature permissions
on individual endpoints without relying solely on middleware.
"""
from functools import wraps
from typing import Optional, List, Dict, Any, Callable
from fastapi import HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security.dependencies import get_current_active_user
from models.user import User
from models.feature_permission import (
    FeatureType, ReportType, ExportFormat, AnalyticsScope,
    MessagePermission, DataSensitivity
)
from core.security.feature_permissions.service import feature_permission_service
from core.security.feature_permissions.report_permissions import report_permission_service
from core.security.feature_permissions.export_permissions import export_permission_service
from core.security.feature_permissions.analytics_permissions import analytics_permission_service
from core.security.feature_permissions.messaging_permissions import messaging_permission_service
from core.logger import get_logger


logger = get_logger(__name__)


def require_feature_permission(
    feature_type: FeatureType,
    action: str,
    resource_id_param: Optional[str] = None,
    get_context: Optional[Callable] = None
):
    """
    Decorator to require feature permission for an endpoint.
    
    Args:
        feature_type: The type of feature being accessed
        action: The action being performed
        resource_id_param: Name of the parameter containing resource ID
        get_context: Function to extract additional context from request
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            db = None
            user = None
            
            for key, value in kwargs.items():
                if isinstance(value, AsyncSession):
                    db = value
                elif isinstance(value, User):
                    user = value
            
            if not db or not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            # Get resource ID if specified
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = str(kwargs[resource_id_param])
            
            # Build context
            context = {}
            if get_context:
                context = get_context(**kwargs)
            
            # Check permission
            try:
                allowed, reason = await feature_permission_service.check_feature_permission(
                    db=db,
                    user=user,
                    feature_type=feature_type,
                    action=action,
                    resource_id=resource_id,
                    request_context=context
                )
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {reason}"
                    )
                
            except Exception as e:
                logger.error(f"Error checking feature permission: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission check failed"
                )
            
            # Call the original function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_report_access(
    get_template_id: Optional[Callable] = None,
    get_parameters: Optional[Callable] = None
):
    """
    Decorator to require report access permission.
    
    Args:
        get_template_id: Function to extract template ID from request
        get_parameters: Function to extract report parameters from request
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            db = kwargs.get("db")
            user = kwargs.get("current_user")
            
            if not db or not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            # Get template ID
            template_id = None
            if get_template_id:
                template_id = get_template_id(**kwargs)
            elif "template_id" in kwargs:
                template_id = kwargs["template_id"]
            
            if not template_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Template ID required"
                )
            
            # Get parameters
            parameters = {}
            if get_parameters:
                parameters = get_parameters(**kwargs)
            
            # Check access
            try:
                allowed, reason, filtered_params = await report_permission_service.can_access_report(
                    db=db,
                    user=user,
                    template_id=str(template_id),
                    parameters=parameters
                )
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Report access denied: {reason}"
                    )
                
                # Add filtered parameters to kwargs for the endpoint to use
                kwargs["_filtered_parameters"] = filtered_params
                
            except Exception as e:
                logger.error(f"Error checking report access: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Report access check failed"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_export_permission(
    export_type: str,
    get_format: Optional[Callable] = None,
    get_size_estimate: Optional[Callable] = None
):
    """
    Decorator to require export permission.
    
    Args:
        export_type: Type of export being performed
        get_format: Function to extract export format from request
        get_size_estimate: Function to estimate export size
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            db = kwargs.get("db")
            user = kwargs.get("current_user")
            
            if not db or not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            # Get format
            format = ExportFormat.CSV  # Default
            if get_format:
                format = get_format(**kwargs)
            elif "format" in kwargs:
                format = kwargs["format"]
            
            # Get size estimates
            estimated_rows = None
            estimated_size_mb = None
            if get_size_estimate:
                estimates = get_size_estimate(**kwargs)
                estimated_rows = estimates.get("rows")
                estimated_size_mb = estimates.get("size_mb")
            
            # Check permission
            try:
                allowed, reason, limits = await export_permission_service.can_export_data(
                    db=db,
                    user=user,
                    export_type=export_type,
                    format=format,
                    estimated_rows=estimated_rows,
                    estimated_size_mb=estimated_size_mb
                )
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Export denied: {reason}"
                    )
                
                # Add limits to kwargs for the endpoint to use
                kwargs["_export_limits"] = limits
                
            except Exception as e:
                logger.error(f"Error checking export permission: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Export permission check failed"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_analytics_access(
    analytics_type: str,
    default_scope: AnalyticsScope = AnalyticsScope.OWN,
    get_scope: Optional[Callable] = None,
    get_metrics: Optional[Callable] = None
):
    """
    Decorator to require analytics access permission.
    
    Args:
        analytics_type: Type of analytics being accessed
        default_scope: Default scope if not specified
        get_scope: Function to extract requested scope from request
        get_metrics: Function to extract requested metrics from request
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            db = kwargs.get("db")
            user = kwargs.get("current_user")
            
            if not db or not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            # Get scope
            scope = default_scope
            if get_scope:
                scope = get_scope(**kwargs)
            elif "scope" in kwargs:
                scope = kwargs["scope"]
            
            # Get metrics
            metrics = []
            if get_metrics:
                metrics = get_metrics(**kwargs)
            elif "metrics" in kwargs:
                metrics = kwargs["metrics"]
            
            # Get date range if available
            date_range = kwargs.get("date_range", {})
            
            # Check access
            try:
                allowed, reason, filters = await analytics_permission_service.check_analytics_access(
                    db=db,
                    user=user,
                    analytics_type=analytics_type,
                    requested_scope=scope,
                    metrics=metrics,
                    date_range=date_range
                )
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Analytics access denied: {reason}"
                    )
                
                # Add filters to kwargs for the endpoint to use
                kwargs["_data_filters"] = filters
                
            except Exception as e:
                logger.error(f"Error checking analytics access: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Analytics access check failed"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_messaging_permission(
    action: str = "send_message",
    get_recipient_count: Optional[Callable] = None,
    get_chat_id: Optional[Callable] = None
):
    """
    Decorator to require messaging permission.
    
    Args:
        action: Messaging action being performed
        get_recipient_count: Function to get recipient count from request
        get_chat_id: Function to get chat ID from request
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            db = kwargs.get("db")
            user = kwargs.get("current_user")
            
            if not db or not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies"
                )
            
            # Get recipient count
            recipient_count = 1
            if get_recipient_count:
                recipient_count = get_recipient_count(**kwargs)
            elif "recipient_count" in kwargs:
                recipient_count = kwargs["recipient_count"]
            elif "recipients" in kwargs:
                recipient_count = len(kwargs["recipients"])
            
            # Get chat ID
            chat_id = None
            if get_chat_id:
                chat_id = get_chat_id(**kwargs)
            elif "chat_id" in kwargs:
                chat_id = kwargs["chat_id"]
            
            # Determine message type
            message_type = "bulk" if recipient_count > 1 else "individual"
            
            # Check permission
            try:
                allowed, reason, limits = await messaging_permission_service.can_send_message(
                    db=db,
                    user=user,
                    message_type=message_type,
                    recipient_count=recipient_count,
                    chat_id=chat_id,
                    is_automated=kwargs.get("is_automated", False)
                )
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Messaging denied: {reason}"
                    )
                
                # Add limits to kwargs for the endpoint to use
                kwargs["_messaging_limits"] = limits
                
            except Exception as e:
                logger.error(f"Error checking messaging permission: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Messaging permission check failed"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_data_sensitivity(
    min_level: DataSensitivity = DataSensitivity.INTERNAL,
    check_field: Optional[str] = None
):
    """
    Decorator to require minimum data sensitivity level.
    
    Args:
        min_level: Minimum sensitivity level required
        check_field: Field in response to check for sensitivity
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user
            user = kwargs.get("current_user")
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing user dependency"
                )
            
            # Get user's max sensitivity level
            # This would be cached in production
            user_level = DataSensitivity.INTERNAL  # Default
            
            # Check if user meets minimum level
            level_hierarchy = {
                DataSensitivity.PUBLIC: 0,
                DataSensitivity.INTERNAL: 1,
                DataSensitivity.CONFIDENTIAL: 2,
                DataSensitivity.RESTRICTED: 3,
                DataSensitivity.TOP_SECRET: 4
            }
            
            if level_hierarchy.get(user_level, 0) < level_hierarchy.get(min_level, 1):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient data sensitivity clearance. Required: {min_level.value}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Utility function for endpoints to check permissions inline
async def check_feature_permission_inline(
    db: AsyncSession,
    user: User,
    feature_type: FeatureType,
    action: str,
    resource_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Check feature permission inline within an endpoint.
    
    Raises:
        HTTPException: If permission is denied
    """
    allowed, reason = await feature_permission_service.check_feature_permission(
        db=db,
        user=user,
        feature_type=feature_type,
        action=action,
        resource_id=resource_id,
        request_context=context
    )
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {reason}"
        )