"""
Bulk operations module.
"""
from .bulk_processor import bulk_processor, BulkOperationProgress
from .models import (
    BulkOperation, BulkOperationItem, BulkOperationLog,
    BulkOperationTemplate, BulkOperationSchedule, BulkOperationLimit,
    BulkOperationType, BulkOperationStatus
)
from .handlers import register_bulk_handlers

# Register handlers on module import
register_bulk_handlers()

__all__ = [
    "bulk_processor",
    "BulkOperationProgress",
    "BulkOperation",
    "BulkOperationItem",
    "BulkOperationLog",
    "BulkOperationTemplate",
    "BulkOperationSchedule",
    "BulkOperationLimit",
    "BulkOperationType",
    "BulkOperationStatus",
    "register_bulk_handlers"
]