"""Error recovery mechanisms for sync operations."""

from typing import Any, Dict, List, Optional, Callable, Type
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import traceback
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession
from core.logger import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Types of errors that can occur during sync."""
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "auth_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    TIMEOUT_ERROR = "timeout_error"
    PARSING_ERROR = "parsing_error"
    VALIDATION_ERROR = "validation_error"
    DATABASE_ERROR = "database_error"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY_IMMEDIATE = "retry_immediate"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    RETRY_AFTER_DELAY = "retry_after_delay"
    SKIP_ITEM = "skip_item"
    SKIP_BATCH = "skip_batch"
    PAUSE_SYNC = "pause_sync"
    ABORT_SYNC = "abort_sync"
    REFRESH_AUTH = "refresh_auth"
    REDUCE_BATCH_SIZE = "reduce_batch_size"


@dataclass
class ErrorContext:
    """Context information about an error."""
    error_type: ErrorType
    error_message: str
    error_code: Optional[str] = None
    retry_count: int = 0
    first_occurred_at: datetime = field(default_factory=datetime.utcnow)
    last_occurred_at: datetime = field(default_factory=datetime.utcnow)
    item_id: Optional[str] = None
    batch_info: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryAction:
    """Action to take for error recovery."""
    strategy: RecoveryStrategy
    delay_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    new_batch_size: Optional[int] = None
    skip_items: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ErrorClassifier:
    """Classifies errors and determines recovery strategies."""
    
    @staticmethod
    def classify_error(exception: Exception) -> ErrorType:
        """Classify an exception into an error type."""
        error_message = str(exception).lower()
        exception_type = type(exception).__name__
        
        # Network errors
        if any(term in error_message for term in ['connection', 'network', 'dns', 'socket']):
            return ErrorType.NETWORK_ERROR
        
        # Authentication errors
        if any(term in error_message for term in ['unauthorized', 'forbidden', '401', '403', 'auth']):
            return ErrorType.AUTHENTICATION_ERROR
        
        # Rate limit errors
        if any(term in error_message for term in ['rate limit', 'too many requests', '429']):
            return ErrorType.RATE_LIMIT_ERROR
        
        # Timeout errors
        if any(term in error_message for term in ['timeout', 'timed out']):
            return ErrorType.TIMEOUT_ERROR
        
        # Parsing errors
        if any(term in error_message for term in ['json', 'parse', 'decode', 'invalid response']):
            return ErrorType.PARSING_ERROR
        
        # Validation errors
        if any(term in error_message for term in ['validation', 'invalid', 'constraint']):
            return ErrorType.VALIDATION_ERROR
        
        # Database errors
        if any(term in error_message for term in ['database', 'sql', 'integrity']):
            return ErrorType.DATABASE_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    @staticmethod
    def get_recovery_strategy(error_type: ErrorType, retry_count: int = 0) -> RecoveryAction:
        """Determine recovery strategy based on error type and retry count."""
        
        strategies = {
            ErrorType.NETWORK_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.RETRY_IMMEDIATE, max_retries=3)),
                (3, RecoveryAction(RecoveryStrategy.RETRY_WITH_BACKOFF, delay_seconds=60, max_retries=5)),
                (8, RecoveryAction(RecoveryStrategy.PAUSE_SYNC, delay_seconds=300))
            ],
            
            ErrorType.AUTHENTICATION_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.REFRESH_AUTH)),
                (1, RecoveryAction(RecoveryStrategy.ABORT_SYNC))
            ],
            
            ErrorType.RATE_LIMIT_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.RETRY_AFTER_DELAY, delay_seconds=60)),
                (3, RecoveryAction(RecoveryStrategy.REDUCE_BATCH_SIZE, new_batch_size=10)),
                (5, RecoveryAction(RecoveryStrategy.PAUSE_SYNC, delay_seconds=600))
            ],
            
            ErrorType.TIMEOUT_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.RETRY_IMMEDIATE, max_retries=2)),
                (2, RecoveryAction(RecoveryStrategy.REDUCE_BATCH_SIZE, new_batch_size=25)),
                (4, RecoveryAction(RecoveryStrategy.SKIP_BATCH))
            ],
            
            ErrorType.PARSING_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.SKIP_ITEM)),
                (5, RecoveryAction(RecoveryStrategy.SKIP_BATCH))
            ],
            
            ErrorType.VALIDATION_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.SKIP_ITEM))
            ],
            
            ErrorType.DATABASE_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.RETRY_WITH_BACKOFF, delay_seconds=5, max_retries=3)),
                (3, RecoveryAction(RecoveryStrategy.ABORT_SYNC))
            ],
            
            ErrorType.UNKNOWN_ERROR: [
                (0, RecoveryAction(RecoveryStrategy.RETRY_IMMEDIATE, max_retries=1)),
                (1, RecoveryAction(RecoveryStrategy.SKIP_ITEM)),
                (10, RecoveryAction(RecoveryStrategy.ABORT_SYNC))
            ]
        }
        
        # Find appropriate strategy based on retry count
        error_strategies = strategies.get(error_type, strategies[ErrorType.UNKNOWN_ERROR])
        
        for threshold, action in reversed(error_strategies):
            if retry_count >= threshold:
                return action
        
        return error_strategies[0][1]  # Default to first strategy


class ErrorRecoveryHandler(ABC):
    """Abstract base class for error recovery handlers."""
    
    @abstractmethod
    async def handle_error(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """
        Handle error with given recovery action.
        
        Returns:
            bool: True if recovery was successful, False otherwise
        """
        pass


class RetryHandler(ErrorRecoveryHandler):
    """Handles retry-based recovery strategies."""
    
    def __init__(self, retry_func: Callable):
        self.retry_func = retry_func
    
    async def handle_error(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Implement retry logic with various strategies."""
        
        if recovery_action.strategy == RecoveryStrategy.RETRY_IMMEDIATE:
            return await self._retry_immediate(error_context, recovery_action)
        
        elif recovery_action.strategy == RecoveryStrategy.RETRY_WITH_BACKOFF:
            return await self._retry_with_backoff(error_context, recovery_action)
        
        elif recovery_action.strategy == RecoveryStrategy.RETRY_AFTER_DELAY:
            return await self._retry_after_delay(error_context, recovery_action)
        
        return False
    
    async def _retry_immediate(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Retry immediately up to max retries."""
        max_retries = recovery_action.max_retries or 3
        
        for attempt in range(max_retries):
            try:
                await self.retry_func()
                return True
            except Exception as e:
                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} failed: {e}",
                    extra={"error_context": error_context}
                )
                if attempt == max_retries - 1:
                    return False
        
        return False
    
    async def _retry_with_backoff(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Retry with exponential backoff."""
        max_retries = recovery_action.max_retries or 5
        base_delay = recovery_action.delay_seconds or 1
        
        for attempt in range(max_retries):
            try:
                await self.retry_func()
                return True
            except Exception as e:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Retry attempt {attempt + 1}/{max_retries} failed, waiting {delay}s: {e}",
                    extra={"error_context": error_context}
                )
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                else:
                    return False
        
        return False
    
    async def _retry_after_delay(
        self,
        error_context: ErrorContext,
        recovery_action: RecoveryAction
    ) -> bool:
        """Retry after a fixed delay."""
        delay = recovery_action.delay_seconds or 60
        
        logger.info(
            f"Waiting {delay}s before retry due to {error_context.error_type.value}",
            extra={"error_context": error_context}
        )
        
        await asyncio.sleep(delay)
        
        try:
            await self.retry_func()
            return True
        except Exception as e:
            logger.error(f"Retry after delay failed: {e}")
            return False


class CircuitBreaker:
    """Circuit breaker pattern for handling repeated failures."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
        self.half_open_attempts = 0
    
    def record_success(self):
        """Record a successful operation."""
        if self.state == "half-open":
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_requests:
                # Enough successful requests, close the circuit
                self.state = "closed"
                self.failure_count = 0
                self.half_open_attempts = 0
                logger.info("Circuit breaker closed after successful recovery")
    
    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == "half-open":
            # Failed in half-open state, reopen the circuit
            self.state = "open"
            self.half_open_attempts = 0
            logger.warning("Circuit breaker reopened after failure in half-open state")
        
        elif self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")
    
    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            # Check if recovery timeout has passed
            if self.last_failure_time:
                time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_timeout:
                    # Try half-open state
                    self.state = "half-open"
                    self.half_open_attempts = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False
        
        # half-open state
        return self.half_open_attempts < self.half_open_requests
    
    def get_wait_time(self) -> Optional[int]:
        """Get remaining wait time if circuit is open."""
        if self.state == "open" and self.last_failure_time:
            time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
            remaining = self.recovery_timeout - time_since_failure
            return max(0, int(remaining))
        return None


class SyncErrorRecoveryService:
    """Main service for handling sync error recovery."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_history: List[ErrorContext] = []
        self.recovery_callbacks: Dict[RecoveryStrategy, Callable] = {}
    
    def get_circuit_breaker(self, service_id: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service."""
        if service_id not in self.circuit_breakers:
            self.circuit_breakers[service_id] = CircuitBreaker()
        return self.circuit_breakers[service_id]
    
    def register_recovery_callback(
        self,
        strategy: RecoveryStrategy,
        callback: Callable
    ):
        """Register a callback for a specific recovery strategy."""
        self.recovery_callbacks[strategy] = callback
    
    async def handle_sync_error(
        self,
        exception: Exception,
        service_id: str,
        context: Dict[str, Any]
    ) -> RecoveryAction:
        """Handle a sync error and determine recovery action."""
        
        # Create error context
        error_context = ErrorContext(
            error_type=ErrorClassifier.classify_error(exception),
            error_message=str(exception),
            error_code=getattr(exception, 'code', None),
            stack_trace=traceback.format_exc(),
            additional_data=context
        )
        
        # Check existing errors for this item/batch
        retry_count = self._get_retry_count(service_id, error_context)
        error_context.retry_count = retry_count
        
        # Store error in history
        self.error_history.append(error_context)
        
        # Log error
        await self._log_error(error_context)
        
        # Get recovery strategy
        recovery_action = ErrorClassifier.get_recovery_strategy(
            error_context.error_type,
            retry_count
        )
        
        # Check circuit breaker
        circuit_breaker = self.get_circuit_breaker(service_id)
        if not circuit_breaker.can_execute():
            wait_time = circuit_breaker.get_wait_time()
            logger.warning(
                f"Circuit breaker open for {service_id}, wait {wait_time}s",
                extra={"error_context": error_context}
            )
            recovery_action = RecoveryAction(
                RecoveryStrategy.PAUSE_SYNC,
                delay_seconds=wait_time
            )
        
        # Execute recovery callback if registered
        if recovery_action.strategy in self.recovery_callbacks:
            try:
                callback = self.recovery_callbacks[recovery_action.strategy]
                success = await callback(error_context, recovery_action)
                
                if success:
                    circuit_breaker.record_success()
                else:
                    circuit_breaker.record_failure()
            except Exception as e:
                logger.error(f"Recovery callback failed: {e}")
                circuit_breaker.record_failure()
        
        return recovery_action
    
    def _get_retry_count(self, service_id: str, error_context: ErrorContext) -> int:
        """Get retry count for similar errors."""
        similar_errors = [
            err for err in self.error_history
            if (err.error_type == error_context.error_type and
                err.item_id == error_context.item_id and
                err.additional_data.get('service_id') == service_id and
                (datetime.utcnow() - err.last_occurred_at).total_seconds() < 3600)
        ]
        return len(similar_errors)
    
    async def _log_error(self, error_context: ErrorContext):
        """Log error to database for analysis."""
        from models.sync_error_log import SyncErrorLog
        
        try:
            error_log = SyncErrorLog(
                error_type=error_context.error_type.value,
                error_message=error_context.error_message,
                error_code=error_context.error_code,
                retry_count=error_context.retry_count,
                item_id=error_context.item_id,
                stack_trace=error_context.stack_trace,
                context_data=error_context.additional_data,
                occurred_at=error_context.last_occurred_at
            )
            
            self.db.add(error_log)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")
    
    def get_error_summary(self, service_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of errors for monitoring."""
        relevant_errors = self.error_history
        if service_id:
            relevant_errors = [
                err for err in self.error_history
                if err.additional_data.get('service_id') == service_id
            ]
        
        if not relevant_errors:
            return {"total_errors": 0}
        
        # Group by error type
        errors_by_type = {}
        for err in relevant_errors:
            error_type = err.error_type.value
            if error_type not in errors_by_type:
                errors_by_type[error_type] = 0
            errors_by_type[error_type] += 1
        
        # Calculate error rate
        time_window = 3600  # 1 hour
        recent_errors = [
            err for err in relevant_errors
            if (datetime.utcnow() - err.last_occurred_at).total_seconds() < time_window
        ]
        
        return {
            "total_errors": len(relevant_errors),
            "recent_errors": len(recent_errors),
            "errors_by_type": errors_by_type,
            "circuit_breaker_states": {
                sid: cb.state for sid, cb in self.circuit_breakers.items()
            },
            "error_rate_per_hour": len(recent_errors)
        }