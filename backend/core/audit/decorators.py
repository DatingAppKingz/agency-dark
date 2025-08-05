"""
Decorators for audit logging in endpoints.
"""
import functools
from typing import Optional, Dict, Any, Callable
from fastapi import Request
import inspect

from core.audit.audit_service import audit_service
from models.audit_log import AuditAction, AuditSeverity
from core.database import get_db
from core.logger import get_logger

logger = get_logger(__name__)


def audit_log(
    action: AuditAction,
    resource_type: Optional[str] = None,
    resource_id_param: Optional[str] = None,
    description: Optional[str] = None,
    severity: AuditSeverity = AuditSeverity.INFO,
    include_response: bool = False,
    include_duration: bool = True
):
    """
    Decorator to automatically log audit events for endpoints.
    
    Args:
        action: The audit action to log
        resource_type: Type of resource being accessed
        resource_id_param: Parameter name containing resource ID
        description: Custom description (auto-generated if not provided)
        severity: Severity level
        include_response: Whether to include response in metadata
        include_duration: Whether to track execution time
        
    Example:
        @router.post("/users/{user_id}/activate")
        @audit_log(
            action=AuditAction.USER_ACTIVATED,
            resource_type="user",
            resource_id_param="user_id"
        )
        async def activate_user(user_id: str, current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.time() if include_duration else None
            
            # Extract request and user
            request = None
            current_user = None
            db_session = None
            
            # Get from kwargs
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                elif hasattr(value, "email") and hasattr(value, "role"):  # User object
                    current_user = value
                elif key == "db":  # Database session
                    db_session = value
            
            # Get resource ID if specified
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = str(kwargs[resource_id_param])
            
            # Execute the function
            response = None
            error = None
            
            try:
                response = await func(*args, **kwargs)
                return response
                
            except Exception as e:
                error = e
                raise
                
            finally:
                # Log audit event
                try:
                    # Get DB session if not provided
                    if not db_session:
                        async for db in get_db():
                            db_session = db
                            break
                    
                    if db_session and current_user:
                        # Build metadata
                        metadata = {
                            "endpoint": func.__name__,
                            "module": func.__module__
                        }
                        
                        if include_response and response and hasattr(response, "dict"):
                            try:
                                metadata["response"] = response.dict() if hasattr(response, "dict") else str(response)
                            except:
                                pass
                        
                        if error:
                            metadata["error"] = {
                                "type": type(error).__name__,
                                "message": str(error)
                            }
                        
                        # Calculate duration
                        duration_ms = None
                        if start_time:
                            duration_ms = int((time.time() - start_time) * 1000)
                        
                        # Extract request info
                        ip_address = None
                        user_agent = None
                        if request:
                            ip_address = request.client.host if request.client else None
                            user_agent = request.headers.get("user-agent")
                        
                        # Log audit
                        await audit_service.log(
                            db=db_session,
                            action=action,
                            user=current_user,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            description=description or f"{action.value} via {func.__name__}",
                            metadata=metadata,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            severity=AuditSeverity.ERROR if error else severity,
                            duration_ms=duration_ms
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to log audit from decorator: {e}")
        
        return wrapper
    return decorator


def audit_financial(
    action: AuditAction,
    amount_param: str = "amount",
    currency_param: str = "currency",
    transaction_id_param: Optional[str] = None
):
    """
    Specialized decorator for financial operations.
    
    Args:
        action: The financial action
        amount_param: Parameter name containing amount
        currency_param: Parameter name containing currency
        transaction_id_param: Parameter name containing transaction ID
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract parameters
            amount = kwargs.get(amount_param, 0)
            currency = kwargs.get(currency_param, "USD")
            transaction_id = kwargs.get(transaction_id_param) if transaction_id_param else None
            
            # Execute function
            response = await func(*args, **kwargs)
            
            # Log financial action
            try:
                # Get user and DB from kwargs
                current_user = None
                db_session = None
                
                for key, value in kwargs.items():
                    if hasattr(value, "email") and hasattr(value, "role"):
                        current_user = value
                    elif key == "db":
                        db_session = value
                
                if not db_session:
                    async for db in get_db():
                        db_session = db
                        break
                
                if db_session and current_user:
                    await audit_service.log_financial_action(
                        db=db_session,
                        user=current_user,
                        action=action,
                        amount=amount,
                        currency=currency,
                        transaction_id=transaction_id,
                        endpoint=func.__name__
                    )
                    
            except Exception as e:
                logger.error(f"Failed to log financial audit: {e}")
            
            return response
        
        return wrapper
    return decorator


def audit_data_access(resource_type: str):
    """
    Decorator for data access operations.
    
    Args:
        resource_type: Type of data being accessed
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute function
            response = await func(*args, **kwargs)
            
            # Log data access
            try:
                # Extract info from kwargs
                current_user = None
                db_session = None
                request = None
                
                for key, value in kwargs.items():
                    if hasattr(value, "email") and hasattr(value, "role"):
                        current_user = value
                    elif key == "db":
                        db_session = value
                    elif isinstance(value, Request):
                        request = value
                
                if not db_session:
                    async for db in get_db():
                        db_session = db
                        break
                
                if db_session and current_user:
                    # Extract filters from kwargs
                    filters = {k: v for k, v in kwargs.items() 
                              if k not in ["db", "current_user", "request"]}
                    
                    await audit_service.log_data_access(
                        db=db_session,
                        user=current_user,
                        resource_type=resource_type,
                        resource_id=func.__name__,
                        action="read",
                        ip_address=request.client.host if request and request.client else None,
                        **filters
                    )
                    
            except Exception as e:
                logger.error(f"Failed to log data access audit: {e}")
            
            return response
        
        return wrapper
    return decorator


class AuditContext:
    """Context manager for batch audit logging."""
    
    def __init__(self, db_session):
        self.db_session = db_session
        self.logs = []
    
    async def log(self, **kwargs):
        """Add log to batch."""
        kwargs["batch"] = True
        self.logs.append(kwargs)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Flush all logs."""
        if self.logs:
            async with audit_service.batch_context(self.db_session):
                for log_kwargs in self.logs:
                    await audit_service.log(db=self.db_session, **log_kwargs)