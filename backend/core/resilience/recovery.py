"""
Error recovery workflows for handling failures gracefully
"""
import asyncio
import json
from typing import Dict, Any, Optional, List, Callable, TypeVar, Union
from datetime import datetime, timedelta
from enum import Enum
import traceback

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_context
from core.redis import redis_client
from core.logging import logger
from core.models import Task

T = TypeVar('T')


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types"""
    RETRY = "retry"
    COMPENSATE = "compensate"
    FALLBACK = "fallback"
    IGNORE = "ignore"
    ESCALATE = "escalate"
    ROLLBACK = "rollback"


class ErrorType(Enum):
    """Types of errors that can occur"""
    NETWORK = "network"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class RecoveryContext:
    """Context for error recovery"""
    
    def __init__(
        self,
        error: Exception,
        error_type: ErrorType,
        operation: str,
        context_data: Dict[str, Any],
        attempt: int = 1
    ):
        self.error = error
        self.error_type = error_type
        self.operation = operation
        self.context_data = context_data
        self.attempt = attempt
        self.timestamp = datetime.utcnow()
        self.traceback = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'error': str(self.error),
            'error_type': self.error_type.value,
            'operation': self.operation,
            'context_data': self.context_data,
            'attempt': self.attempt,
            'timestamp': self.timestamp.isoformat(),
            'traceback': self.traceback
        }


class RecoveryWorkflow:
    """
    Manages error recovery workflows
    """
    
    def __init__(self):
        self.recovery_strategies: Dict[ErrorType, List[RecoveryStrategy]] = {
            ErrorType.NETWORK: [RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK],
            ErrorType.TIMEOUT: [RecoveryStrategy.RETRY, RecoveryStrategy.COMPENSATE],
            ErrorType.RATE_LIMIT: [RecoveryStrategy.RETRY, RecoveryStrategy.ESCALATE],
            ErrorType.AUTHENTICATION: [RecoveryStrategy.ESCALATE],
            ErrorType.VALIDATION: [RecoveryStrategy.IGNORE, RecoveryStrategy.COMPENSATE],
            ErrorType.BUSINESS_LOGIC: [RecoveryStrategy.COMPENSATE, RecoveryStrategy.ROLLBACK],
            ErrorType.SYSTEM: [RecoveryStrategy.RETRY, RecoveryStrategy.ESCALATE],
            ErrorType.UNKNOWN: [RecoveryStrategy.ESCALATE]
        }
        
        self.compensation_handlers: Dict[str, Callable] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.rollback_handlers: Dict[str, Callable] = {}
    
    def register_compensation_handler(
        self,
        operation: str,
        handler: Callable[[RecoveryContext], Any]
    ):
        """Register a compensation handler for an operation"""
        self.compensation_handlers[operation] = handler
    
    def register_fallback_handler(
        self,
        operation: str,
        handler: Callable[[RecoveryContext], Any]
    ):
        """Register a fallback handler for an operation"""
        self.fallback_handlers[operation] = handler
    
    def register_rollback_handler(
        self,
        operation: str,
        handler: Callable[[RecoveryContext], Any]
    ):
        """Register a rollback handler for an operation"""
        self.rollback_handlers[operation] = handler
    
    async def handle_error(
        self,
        error: Exception,
        operation: str,
        context_data: Dict[str, Any],
        attempt: int = 1
    ) -> Optional[Any]:
        """
        Handle an error with appropriate recovery strategy
        """
        # Classify error
        error_type = self._classify_error(error)
        
        # Create recovery context
        context = RecoveryContext(
            error=error,
            error_type=error_type,
            operation=operation,
            context_data=context_data,
            attempt=attempt
        )
        
        # Log error
        await self._log_error(context)
        
        # Get recovery strategies
        strategies = self.recovery_strategies.get(error_type, [RecoveryStrategy.ESCALATE])
        
        # Try each strategy
        for strategy in strategies:
            try:
                result = await self._execute_strategy(strategy, context)
                if result is not None:
                    await self._log_recovery_success(context, strategy)
                    return result
            except Exception as exc:
                logger.error(f"Recovery strategy {strategy} failed: {exc}")
                continue
        
        # All strategies failed - escalate
        await self._escalate_error(context)
        raise error
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify error type based on exception"""
        error_str = str(error).lower()
        error_type_name = type(error).__name__.lower()
        
        # Network errors
        if any(keyword in error_str or keyword in error_type_name for keyword in
               ['connection', 'network', 'socket', 'dns', 'refused']):
            return ErrorType.NETWORK
        
        # Timeout errors
        if any(keyword in error_str or keyword in error_type_name for keyword in
               ['timeout', 'timed out', 'deadline']):
            return ErrorType.TIMEOUT
        
        # Rate limit errors
        if any(keyword in error_str for keyword in
               ['rate limit', 'too many requests', '429']):
            return ErrorType.RATE_LIMIT
        
        # Authentication errors
        if any(keyword in error_str or keyword in error_type_name for keyword in
               ['auth', 'unauthorized', '401', 'forbidden', '403']):
            return ErrorType.AUTHENTICATION
        
        # Validation errors
        if any(keyword in error_str or keyword in error_type_name for keyword in
               ['validation', 'invalid', 'bad request', '400']):
            return ErrorType.VALIDATION
        
        # Business logic errors
        if any(keyword in error_str for keyword in
               ['business', 'constraint', 'rule', 'policy']):
            return ErrorType.BUSINESS_LOGIC
        
        # System errors
        if any(keyword in error_str or keyword in error_type_name for keyword in
               ['system', 'internal', '500', 'database']):
            return ErrorType.SYSTEM
        
        return ErrorType.UNKNOWN
    
    async def _execute_strategy(
        self,
        strategy: RecoveryStrategy,
        context: RecoveryContext
    ) -> Optional[Any]:
        """
        Execute a recovery strategy
        """
        if strategy == RecoveryStrategy.RETRY:
            return await self._retry_operation(context)
        
        elif strategy == RecoveryStrategy.COMPENSATE:
            return await self._compensate_operation(context)
        
        elif strategy == RecoveryStrategy.FALLBACK:
            return await self._fallback_operation(context)
        
        elif strategy == RecoveryStrategy.ROLLBACK:
            return await self._rollback_operation(context)
        
        elif strategy == RecoveryStrategy.IGNORE:
            logger.warning(f"Ignoring error for operation {context.operation}")
            return None
        
        elif strategy == RecoveryStrategy.ESCALATE:
            # Escalation handled by caller
            return None
        
        return None
    
    async def _retry_operation(self, context: RecoveryContext) -> Optional[Any]:
        """
        Retry the failed operation
        """
        # Check if we should retry
        if context.attempt >= 3:  # Max 3 attempts
            return None
        
        # Calculate delay with exponential backoff
        delay = min(2 ** (context.attempt - 1), 30)  # Max 30 seconds
        
        # Add jitter
        import random
        delay = delay * (0.5 + random.random() * 0.5)
        
        logger.info(
            f"Retrying operation {context.operation} after {delay:.1f}s "
            f"(attempt {context.attempt + 1})"
        )
        
        await asyncio.sleep(delay)
        
        # Store retry attempt
        retry_key = f"recovery:retry:{context.operation}:{context.timestamp.timestamp()}"
        await redis_client.setex(
            retry_key,
            3600,  # 1 hour
            json.dumps({
                'attempt': context.attempt + 1,
                'delay': delay,
                'timestamp': datetime.utcnow().isoformat()
            })
        )
        
        # Retry logic would be implemented by the caller
        return None
    
    async def _compensate_operation(self, context: RecoveryContext) -> Optional[Any]:
        """
        Execute compensation logic
        """
        handler = self.compensation_handlers.get(context.operation)
        if not handler:
            logger.warning(f"No compensation handler for operation {context.operation}")
            return None
        
        logger.info(f"Executing compensation for operation {context.operation}")
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(context)
            else:
                result = handler(context)
            
            # Log compensation
            await self._log_compensation(context, result)
            
            return result
        except Exception as exc:
            logger.error(f"Compensation failed for {context.operation}: {exc}")
            raise
    
    async def _fallback_operation(self, context: RecoveryContext) -> Optional[Any]:
        """
        Execute fallback logic
        """
        handler = self.fallback_handlers.get(context.operation)
        if not handler:
            logger.warning(f"No fallback handler for operation {context.operation}")
            return None
        
        logger.info(f"Executing fallback for operation {context.operation}")
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(context)
            else:
                result = handler(context)
            
            return result
        except Exception as exc:
            logger.error(f"Fallback failed for {context.operation}: {exc}")
            raise
    
    async def _rollback_operation(self, context: RecoveryContext) -> Optional[Any]:
        """
        Execute rollback logic
        """
        handler = self.rollback_handlers.get(context.operation)
        if not handler:
            logger.warning(f"No rollback handler for operation {context.operation}")
            return None
        
        logger.info(f"Executing rollback for operation {context.operation}")
        
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(context)
            else:
                result = handler(context)
            
            # Log rollback
            await self._log_rollback(context, result)
            
            return result
        except Exception as exc:
            logger.error(f"Rollback failed for {context.operation}: {exc}")
            raise
    
    async def _log_error(self, context: RecoveryContext):
        """
        Log error to database
        """
        try:
            async with get_db_context() as db:
                # Store error log in Redis for now
                error_key = f"error_log:{context.operation}:{context.timestamp.timestamp()}"
                await redis_client.setex(
                    error_key,
                    86400 * 7,  # 7 days
                    json.dumps({
                        'error_type': context.error_type.value,
                        'operation': context.operation,
                        'error_message': str(context.error),
                        'traceback': context.traceback,
                        'context_data': context.context_data,
                        'attempt': context.attempt,
                        'occurred_at': context.timestamp.isoformat()
                    })
                )
        except Exception as exc:
            logger.error(f"Failed to log error: {exc}")
    
    async def _log_recovery_success(
        self,
        context: RecoveryContext,
        strategy: RecoveryStrategy
    ):
        """
        Log successful recovery
        """
        try:
            async with get_db_context() as db:
                # Store recovery action in Redis
                recovery_key = f"recovery_action:{context.operation}:{datetime.utcnow().timestamp()}"
                await redis_client.setex(
                    recovery_key,
                    86400,  # 24 hours
                    json.dumps({
                        'error_type': context.error_type.value,
                        'operation': context.operation,
                        'strategy': strategy.value,
                        'success': True,
                        'attempt': context.attempt,
                        'executed_at': datetime.utcnow().isoformat()
                    })
                )
        except Exception as exc:
            logger.error(f"Failed to log recovery success: {exc}")
    
    async def _log_compensation(self, context: RecoveryContext, result: Any):
        """
        Log compensation action
        """
        compensation_key = f"recovery:compensation:{context.operation}:{datetime.utcnow().timestamp()}"
        await redis_client.setex(
            compensation_key,
            86400,  # 24 hours
            json.dumps({
                'operation': context.operation,
                'error_type': context.error_type.value,
                'result': str(result),
                'timestamp': datetime.utcnow().isoformat()
            })
        )
    
    async def _log_rollback(self, context: RecoveryContext, result: Any):
        """
        Log rollback action
        """
        rollback_key = f"recovery:rollback:{context.operation}:{datetime.utcnow().timestamp()}"
        await redis_client.setex(
            rollback_key,
            86400,  # 24 hours
            json.dumps({
                'operation': context.operation,
                'error_type': context.error_type.value,
                'result': str(result),
                'timestamp': datetime.utcnow().isoformat()
            })
        )
    
    async def _escalate_error(self, context: RecoveryContext):
        """
        Escalate error for manual intervention
        """
        # Create alert
        alert_key = f"recovery:escalation:{datetime.utcnow().strftime('%Y%m%d')}"
        alert_data = {
            'operation': context.operation,
            'error': str(context.error),
            'error_type': context.error_type.value,
            'attempts': context.attempt,
            'context_data': context.context_data,
            'timestamp': context.timestamp.isoformat(),
            'severity': 'critical'
        }
        
        await redis_client.lpush(alert_key, json.dumps(alert_data))
        await redis_client.expire(alert_key, 86400)  # 24 hours
        
        # Log critical error
        logger.critical(
            f"ESCALATION REQUIRED: {context.operation} failed after all recovery attempts",
            extra={
                'operation': context.operation,
                'error_type': context.error_type.value,
                'error': str(context.error)
            }
        )


# Global recovery workflow instance
recovery_workflow = RecoveryWorkflow()


# Recovery decorators
import functools


def with_recovery(
    operation: str,
    compensation: Optional[Callable] = None,
    fallback: Optional[Callable] = None,
    rollback: Optional[Callable] = None
):
    """
    Decorator to add recovery capabilities to functions
    
    Usage:
        @with_recovery(
            operation="sync_transactions",
            compensation=compensate_sync,
            fallback=use_cached_data
        )
        async def sync_transactions():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Register handlers if provided
        if compensation:
            recovery_workflow.register_compensation_handler(operation, compensation)
        if fallback:
            recovery_workflow.register_fallback_handler(operation, fallback)
        if rollback:
            recovery_workflow.register_rollback_handler(operation, rollback)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = kwargs.pop('_recovery_attempt', 1)
            
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                # Extract context data
                context_data = {
                    'args': str(args),
                    'kwargs': str(kwargs)
                }
                
                # Handle error with recovery
                result = await recovery_workflow.handle_error(
                    error=exc,
                    operation=operation,
                    context_data=context_data,
                    attempt=attempt
                )
                
                # If recovery suggests retry
                if result is None and attempt < 3:
                    kwargs['_recovery_attempt'] = attempt + 1
                    return await async_wrapper(*args, **kwargs)
                
                return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Example compensation handlers
async def compensate_failed_payment(context: RecoveryContext) -> Dict[str, Any]:
    """
    Compensate for failed payment processing
    """
    payment_data = context.context_data
    
    # Reverse any partial charges
    if payment_data.get('charge_id'):
        # Refund logic here
        pass
    
    # Update transaction status
    async with get_db_context() as db:
        # Update transaction to failed status
        pass
    
    return {
        'compensation': 'payment_reversed',
        'payment_id': payment_data.get('payment_id')
    }


async def fallback_to_cache(context: RecoveryContext) -> Any:
    """
    Fallback to cached data when API fails
    """
    cache_key = f"fallback:{context.operation}:{context.context_data.get('key')}"
    cached_data = await redis_client.get(cache_key)
    
    if cached_data:
        logger.info(f"Using cached data for {context.operation}")
        return json.loads(cached_data)
    
    return None