"""
Bulk operations processor service.
"""
from typing import Dict, List, Optional, Any, Callable, Type
from datetime import datetime, timedelta
import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from core.redis import redis_client
from core.database import get_db
from core.bulk_operations.models import (
    BulkOperation, BulkOperationItem, BulkOperationLog,
    BulkOperationType, BulkOperationStatus, BulkOperationLimit
)
from core.domain.models import User, Agency
from core.realtime.server import sio

logger = logging.getLogger(__name__)


class BulkOperationProgress(BaseModel):
    """Progress information for bulk operations."""
    operation_id: str
    status: str
    progress_percentage: int
    processed_count: int
    total_count: int
    success_count: int
    failed_count: int
    current_batch: int
    total_batches: int
    message: str


class BulkProcessor:
    """Main bulk operations processor."""
    
    def __init__(self):
        self.redis = redis_client
        self._operation_handlers: Dict[BulkOperationType, Callable] = {}
        self._validation_handlers: Dict[BulkOperationType, Callable] = {}
        self._rollback_handlers: Dict[BulkOperationType, Callable] = {}
        self._register_default_handlers()
    
    def register_handler(
        self,
        operation_type: BulkOperationType,
        handler: Callable,
        validation_handler: Optional[Callable] = None,
        rollback_handler: Optional[Callable] = None
    ):
        """Register handlers for a bulk operation type."""
        self._operation_handlers[operation_type] = handler
        if validation_handler:
            self._validation_handlers[operation_type] = validation_handler
        if rollback_handler:
            self._rollback_handlers[operation_type] = rollback_handler
    
    async def create_operation(
        self,
        operation_type: BulkOperationType,
        entity_type: str,
        entity_ids: List[str],
        params: Dict[str, Any],
        user: User,
        session: AsyncSession,
        scheduled_at: Optional[datetime] = None,
        validation_rules: Optional[Dict[str, Any]] = None
    ) -> BulkOperation:
        """Create a new bulk operation."""
        # Check limits
        await self._check_limits(user, operation_type, len(entity_ids), session)
        
        # Create operation
        operation = BulkOperation(
            operation_type=operation_type,
            entity_type=entity_type,
            entity_ids=entity_ids,
            total_count=len(entity_ids),
            operation_params=params,
            validation_rules=validation_rules,
            scheduled_at=scheduled_at,
            created_by_id=user.id,
            agency_id=user.agency_id,
            batch_size=self._calculate_batch_size(len(entity_ids))
        )
        
        # Calculate total batches
        operation.total_batches = (operation.total_count + operation.batch_size - 1) // operation.batch_size
        
        # Create items
        for entity_id in entity_ids:
            item = BulkOperationItem(
                operation_id=operation.id,
                entity_id=entity_id
            )
            operation.items.append(item)
        
        session.add(operation)
        await session.commit()
        
        # Log creation
        await self._log_operation(
            operation,
            "info",
            f"Bulk operation created: {operation_type.value} for {len(entity_ids)} {entity_type}",
            session
        )
        
        # Schedule or start processing
        if scheduled_at and scheduled_at > datetime.utcnow():
            operation.status = BulkOperationStatus.SCHEDULED
            await session.commit()
            # TODO: Add to scheduler
        else:
            # Start processing immediately
            asyncio.create_task(self._process_operation_async(str(operation.id)))
        
        return operation
    
    async def process_operation(
        self,
        operation_id: str,
        session: AsyncSession
    ) -> BulkOperation:
        """Process a bulk operation."""
        # Get operation
        result = await session.execute(
            select(BulkOperation)
            .options(selectinload(BulkOperation.items))
            .where(BulkOperation.id == operation_id)
        )
        operation = result.scalar_one_or_none()
        
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        if operation.status not in [BulkOperationStatus.PENDING, BulkOperationStatus.SCHEDULED]:
            raise ValueError(f"Operation {operation_id} is not in a processable state")
        
        try:
            # Update status
            operation.status = BulkOperationStatus.VALIDATING
            operation.started_at = datetime.utcnow()
            await session.commit()
            
            # Emit progress
            await self._emit_progress(operation)
            
            # Validate operation
            if operation.validation_rules:
                await self._validate_operation(operation, session)
            
            # Process operation
            operation.status = BulkOperationStatus.PROCESSING
            await session.commit()
            
            # Get handler
            handler = self._operation_handlers.get(operation.operation_type)
            if not handler:
                raise ValueError(f"No handler registered for {operation.operation_type}")
            
            # Process in batches
            for batch_num in range(operation.total_batches):
                operation.current_batch = batch_num + 1
                
                # Get batch items
                start_idx = batch_num * operation.batch_size
                end_idx = min(start_idx + operation.batch_size, operation.total_count)
                batch_items = operation.items[start_idx:end_idx]
                
                # Process batch
                await self._process_batch(
                    operation,
                    batch_items,
                    handler,
                    session
                )
                
                # Update progress
                operation.processed_count = end_idx
                operation.progress_percentage = int((operation.processed_count / operation.total_count) * 100)
                await session.commit()
                
                # Emit progress
                await self._emit_progress(operation)
                
                # Check for cancellation
                if await self._is_cancelled(operation.id):
                    operation.status = BulkOperationStatus.CANCELLED
                    await session.commit()
                    break
            
            # Complete operation
            if operation.status == BulkOperationStatus.PROCESSING:
                operation.status = BulkOperationStatus.COMPLETED
                operation.completed_at = datetime.utcnow()
                await session.commit()
                
                await self._log_operation(
                    operation,
                    "info",
                    f"Bulk operation completed: {operation.success_count} succeeded, {operation.failed_count} failed",
                    session
                )
            
        except Exception as e:
            logger.error(f"Error processing bulk operation {operation_id}: {e}")
            operation.status = BulkOperationStatus.FAILED
            operation.error_summary = str(e)
            await session.commit()
            
            await self._log_operation(
                operation,
                "error",
                f"Bulk operation failed: {str(e)}",
                session
            )
        
        finally:
            # Final progress emit
            await self._emit_progress(operation)
        
        return operation
    
    async def cancel_operation(
        self,
        operation_id: str,
        user: User,
        session: AsyncSession
    ) -> bool:
        """Cancel a bulk operation."""
        # Get operation
        result = await session.execute(
            select(BulkOperation).where(BulkOperation.id == operation_id)
        )
        operation = result.scalar_one_or_none()
        
        if not operation:
            return False
        
        # Check permissions
        if operation.created_by_id != user.id and user.role != "super_admin":
            raise PermissionError("You can only cancel your own operations")
        
        # Check if cancellable
        if operation.status not in [
            BulkOperationStatus.PENDING,
            BulkOperationStatus.SCHEDULED,
            BulkOperationStatus.VALIDATING,
            BulkOperationStatus.PROCESSING
        ]:
            return False
        
        # Set cancellation flag
        await self.redis.setex(f"bulk_op:cancel:{operation_id}", 300, "1")
        
        # If not yet processing, update status immediately
        if operation.status in [BulkOperationStatus.PENDING, BulkOperationStatus.SCHEDULED]:
            operation.status = BulkOperationStatus.CANCELLED
            await session.commit()
        
        return True
    
    async def rollback_operation(
        self,
        operation_id: str,
        user: User,
        session: AsyncSession
    ) -> bool:
        """Rollback a completed bulk operation."""
        # Get operation
        result = await session.execute(
            select(BulkOperation)
            .options(selectinload(BulkOperation.items))
            .where(BulkOperation.id == operation_id)
        )
        operation = result.scalar_one_or_none()
        
        if not operation:
            return False
        
        # Check permissions
        if operation.created_by_id != user.id and user.role != "super_admin":
            raise PermissionError("You can only rollback your own operations")
        
        # Check if rollbackable
        if not operation.can_rollback:
            raise ValueError("This operation cannot be rolled back")
        
        if operation.status != BulkOperationStatus.COMPLETED:
            raise ValueError("Only completed operations can be rolled back")
        
        # Get rollback handler
        handler = self._rollback_handlers.get(operation.operation_type)
        if not handler:
            raise ValueError(f"No rollback handler for {operation.operation_type}")
        
        try:
            # Start rollback
            operation.status = BulkOperationStatus.PROCESSING
            await session.commit()
            
            # Process rollback
            for item in operation.items:
                if item.status == "success" and item.original_data:
                    try:
                        await handler(
                            item.entity_id,
                            item.original_data,
                            operation.operation_params,
                            session
                        )
                        item.status = "rolled_back"
                    except Exception as e:
                        logger.error(f"Error rolling back item {item.id}: {e}")
                        item.error_message = str(e)
            
            # Complete rollback
            operation.status = BulkOperationStatus.ROLLED_BACK
            await session.commit()
            
            await self._log_operation(
                operation,
                "info",
                "Bulk operation rolled back successfully",
                session
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back operation {operation_id}: {e}")
            operation.status = BulkOperationStatus.FAILED
            operation.error_summary = f"Rollback failed: {str(e)}"
            await session.commit()
            return False
    
    async def get_progress(
        self,
        operation_id: str,
        session: AsyncSession
    ) -> BulkOperationProgress:
        """Get operation progress."""
        result = await session.execute(
            select(BulkOperation).where(BulkOperation.id == operation_id)
        )
        operation = result.scalar_one_or_none()
        
        if not operation:
            raise ValueError(f"Operation {operation_id} not found")
        
        return BulkOperationProgress(
            operation_id=str(operation.id),
            status=operation.status.value,
            progress_percentage=operation.progress_percentage,
            processed_count=operation.processed_count,
            total_count=operation.total_count,
            success_count=operation.success_count,
            failed_count=operation.failed_count,
            current_batch=operation.current_batch,
            total_batches=operation.total_batches,
            message=self._get_progress_message(operation)
        )
    
    async def _check_limits(
        self,
        user: User,
        operation_type: BulkOperationType,
        entity_count: int,
        session: AsyncSession
    ):
        """Check if operation is within limits."""
        # Get limits
        result = await session.execute(
            select(BulkOperationLimit).where(
                or_(
                    and_(
                        BulkOperationLimit.user_id == user.id,
                        BulkOperationLimit.operation_type == operation_type
                    ),
                    and_(
                        BulkOperationLimit.agency_id == user.agency_id,
                        BulkOperationLimit.operation_type == operation_type
                    )
                )
            )
        )
        limit = result.scalar_one_or_none()
        
        if not limit:
            # Use default limits
            limit = BulkOperationLimit(
                max_entities_per_operation=1000,
                max_operations_per_day=100,
                max_operations_per_hour=20
            )
        
        # Check entity count
        if not limit.is_unlimited and entity_count > limit.max_entities_per_operation:
            raise ValueError(
                f"Too many entities: {entity_count} exceeds limit of "
                f"{limit.max_entities_per_operation}"
            )
        
        # Check rate limits
        now = datetime.utcnow()
        if limit.last_reset_hour and limit.last_reset_hour.hour != now.hour:
            limit.operations_this_hour = 0
            limit.last_reset_hour = now
        
        if limit.last_reset_date and limit.last_reset_date.date() != now.date():
            limit.operations_today = 0
            limit.last_reset_date = now
        
        if not limit.is_unlimited:
            if limit.operations_this_hour >= limit.max_operations_per_hour:
                raise ValueError("Hourly operation limit exceeded")
            
            if limit.operations_today >= limit.max_operations_per_day:
                raise ValueError("Daily operation limit exceeded")
        
        # Update counters
        limit.operations_this_hour += 1
        limit.operations_today += 1
        
        if limit.id:
            await session.commit()
    
    async def _validate_operation(
        self,
        operation: BulkOperation,
        session: AsyncSession
    ):
        """Validate operation before processing."""
        validator = self._validation_handlers.get(operation.operation_type)
        if not validator:
            return
        
        for item in operation.items:
            try:
                is_valid, errors = await validator(
                    item.entity_id,
                    operation.operation_params,
                    operation.validation_rules,
                    session
                )
                
                item.validation_passed = is_valid
                if not is_valid:
                    item.validation_errors = errors
                    item.status = "skipped"
                    operation.failed_count += 1
                    
            except Exception as e:
                logger.error(f"Validation error for item {item.id}: {e}")
                item.validation_passed = False
                item.validation_errors = {"error": str(e)}
                item.status = "skipped"
                operation.failed_count += 1
        
        await session.commit()
    
    async def _process_batch(
        self,
        operation: BulkOperation,
        items: List[BulkOperationItem],
        handler: Callable,
        session: AsyncSession
    ):
        """Process a batch of items."""
        for item in items:
            if item.status != "pending":
                continue
            
            try:
                # Mark as processing
                item.status = "processing"
                await session.commit()
                
                # Store original data for rollback
                if operation.can_rollback:
                    item.original_data = await self._get_entity_data(
                        operation.entity_type,
                        item.entity_id,
                        session
                    )
                
                # Process item
                result = await handler(
                    item.entity_id,
                    operation.operation_params,
                    session
                )
                
                # Update item
                item.status = "success"
                item.processed_at = datetime.utcnow()
                if isinstance(result, dict):
                    item.new_data = result.get("data")
                    item.changes = result.get("changes")
                
                operation.success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing item {item.id}: {e}")
                item.status = "failed"
                item.error_message = str(e)
                item.error_details = {"exception": type(e).__name__}
                operation.failed_count += 1
            
            finally:
                await session.commit()
    
    async def _emit_progress(self, operation: BulkOperation):
        """Emit progress update via WebSocket."""
        progress = BulkOperationProgress(
            operation_id=str(operation.id),
            status=operation.status.value,
            progress_percentage=operation.progress_percentage,
            processed_count=operation.processed_count,
            total_count=operation.total_count,
            success_count=operation.success_count,
            failed_count=operation.failed_count,
            current_batch=operation.current_batch,
            total_batches=operation.total_batches,
            message=self._get_progress_message(operation)
        )
        
        # Emit to user
        await sio.emit(
            "bulk_operation_progress",
            progress.dict(),
            room=f"user:{operation.created_by_id}"
        )
        
        # Emit to agency
        await sio.emit(
            "bulk_operation_progress",
            progress.dict(),
            room=f"agency:{operation.agency_id}"
        )
    
    async def _log_operation(
        self,
        operation: BulkOperation,
        level: str,
        message: str,
        session: AsyncSession,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log operation event."""
        log = BulkOperationLog(
            operation_id=operation.id,
            log_level=level,
            message=message,
            details=details,
            batch_number=operation.current_batch
        )
        session.add(log)
        await session.commit()
    
    async def _is_cancelled(self, operation_id: uuid.UUID) -> bool:
        """Check if operation is cancelled."""
        return await self.redis.get(f"bulk_op:cancel:{operation_id}") is not None
    
    async def _get_entity_data(
        self,
        entity_type: str,
        entity_id: str,
        session: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Get entity data for rollback."""
        # This would be implemented based on entity type
        # For now, return None
        return None
    
    def _calculate_batch_size(self, total_count: int) -> int:
        """Calculate optimal batch size."""
        if total_count <= 100:
            return total_count
        elif total_count <= 1000:
            return 100
        elif total_count <= 10000:
            return 500
        else:
            return 1000
    
    def _get_progress_message(self, operation: BulkOperation) -> str:
        """Generate progress message."""
        if operation.status == BulkOperationStatus.PENDING:
            return "Operation pending"
        elif operation.status == BulkOperationStatus.VALIDATING:
            return "Validating items..."
        elif operation.status == BulkOperationStatus.PROCESSING:
            return f"Processing batch {operation.current_batch} of {operation.total_batches}"
        elif operation.status == BulkOperationStatus.COMPLETED:
            return f"Completed: {operation.success_count} succeeded, {operation.failed_count} failed"
        elif operation.status == BulkOperationStatus.FAILED:
            return f"Failed: {operation.error_summary}"
        elif operation.status == BulkOperationStatus.CANCELLED:
            return "Operation cancelled"
        else:
            return operation.status.value
    
    async def _process_operation_async(self, operation_id: str):
        """Process operation asynchronously."""
        async for session in get_db():
            try:
                await self.process_operation(operation_id, session)
            except Exception as e:
                logger.error(f"Error in async processing: {e}")
            finally:
                await session.close()
    
    def _register_default_handlers(self):
        """Register default operation handlers."""
        # These would be implemented based on specific operation types
        pass


# Singleton instance
bulk_processor = BulkProcessor()