# Bulk Operations System Documentation

## Overview

The Bulk Operations system provides a powerful and flexible way to perform operations on multiple entities at once. It supports various operation types, progress tracking, validation, scheduling, and rollback capabilities, making it ideal for managing large-scale data operations in the AgencyDark platform.

## Key Features

- **Multiple Operation Types**: Support for user management, model updates, transaction processing, and more
- **Real-time Progress Tracking**: Monitor operation progress with WebSocket updates
- **Validation Framework**: Pre-flight validation to ensure operations will succeed
- **Batch Processing**: Efficient processing of large datasets in configurable batches
- **Rollback Support**: Ability to undo completed operations when needed
- **Scheduling**: Schedule operations to run at specific times
- **Templates**: Save and reuse common operation configurations
- **Rate Limiting**: Built-in limits to prevent system overload
- **Audit Trail**: Complete logging of all operations and changes

## Architecture

### Components

1. **BulkProcessor**: Core service that orchestrates bulk operations
2. **Operation Handlers**: Type-specific handlers for each operation
3. **Models**: Database models for operations, items, logs, and configuration
4. **API Endpoints**: RESTful API for managing bulk operations
5. **WebSocket Integration**: Real-time progress updates

### Operation Flow

1. **Creation**: User creates a bulk operation with selected entities
2. **Validation**: System validates the operation can be performed
3. **Processing**: Operation is processed in batches
4. **Progress Updates**: Real-time updates sent via WebSocket
5. **Completion**: Operation completes with success/failure summary
6. **Rollback**: Optional rollback if needed

## Supported Operations

### User Management
- **USER_UPDATE**: Update user properties (email, name, role, etc.)
- **USER_ACTIVATE**: Activate multiple users
- **USER_DEACTIVATE**: Deactivate multiple users
- **USER_DELETE**: Delete multiple users (with safeguards)

### Model Management
- **MODEL_UPDATE**: Update model properties (commission, bio, etc.)
- **MODEL_ASSIGN**: Assign models to chatters/managers

### Financial Operations
- **TRANSACTION_EXPORT**: Export transactions to various formats
- **TRANSACTION_RECONCILE**: Mark transactions as reconciled
- **PAYOUT_SCHEDULE**: Schedule pending payouts
- **PAYOUT_CANCEL**: Cancel pending/scheduled payouts

### Communication
- **MESSAGE_SEND**: Send bulk messages to users
- **MESSAGE_DELETE**: Delete messages in bulk

### Data Operations
- **ANALYTICS_EXPORT**: Export analytics data
- **DATA_IMPORT**: Import data from external sources
- **DATA_EXPORT**: Export data in various formats

## API Usage

### Creating a Bulk Operation

```python
POST /api/v1/bulk-operations/
{
    "operation_type": "user_update",
    "entity_type": "users",
    "entity_ids": ["uuid1", "uuid2", "uuid3"],
    "operation_params": {
        "is_active": false,
        "role": "agency_member"
    },
    "validation_rules": {
        "check_email_unique": true
    }
}
```

### Monitoring Progress

```python
GET /api/v1/bulk-operations/{operation_id}/progress

Response:
{
    "operation_id": "uuid",
    "status": "processing",
    "progress_percentage": 45,
    "processed_count": 450,
    "total_count": 1000,
    "success_count": 445,
    "failed_count": 5,
    "current_batch": 5,
    "total_batches": 10,
    "message": "Processing batch 5 of 10"
}
```

### WebSocket Progress Updates

```javascript
socket.on('bulk_operation_progress', (data) => {
    console.log(`Operation ${data.operation_id}: ${data.progress_percentage}%`);
});
```

### Cancelling an Operation

```python
POST /api/v1/bulk-operations/{operation_id}/cancel
```

### Rolling Back an Operation

```python
POST /api/v1/bulk-operations/{operation_id}/rollback
```

## Templates

Templates allow you to save common operation configurations:

```python
POST /api/v1/bulk-operations/templates
{
    "name": "Deactivate Inactive Users",
    "operation_type": "user_deactivate",
    "default_params": {},
    "selection_criteria": {
        "last_login_before": "30_days_ago"
    }
}
```

## Scheduling

Schedule recurring bulk operations:

```python
POST /api/v1/bulk-operations/schedules
{
    "name": "Weekly User Cleanup",
    "template_id": "template_uuid",
    "cron_expression": "0 0 * * 0",  # Every Sunday at midnight
    "entity_selection": {
        "inactive_days": 90
    },
    "notify_on_completion": true,
    "notification_emails": ["admin@agency.com"]
}
```

## Limits and Quotas

Default limits per operation type:
- **Max entities per operation**: 1000
- **Max operations per day**: 100
- **Max operations per hour**: 20
- **Max concurrent operations**: 3

These can be customized per user or agency.

## Best Practices

1. **Test First**: Always test operations on a small subset before running on all entities
2. **Use Templates**: Create templates for common operations to ensure consistency
3. **Monitor Progress**: Use the progress API or WebSocket for real-time monitoring
4. **Plan for Failures**: Some items may fail; review logs for details
5. **Schedule Wisely**: Schedule heavy operations during off-peak hours
6. **Validate Data**: Use validation rules to prevent errors
7. **Keep Logs**: Review operation logs for audit trails

## Error Handling

The system handles various error scenarios:
- **Validation Errors**: Items that fail validation are skipped
- **Processing Errors**: Failed items are logged with error details
- **System Errors**: Operations can be retried or rolled back
- **Rate Limiting**: Operations respect system rate limits

## Security Considerations

- **Role-Based Access**: Operations require appropriate permissions
- **Agency Isolation**: Users can only operate on their agency's data
- **Audit Logging**: All operations are logged for security review
- **Rollback Protection**: Some operations cannot be rolled back for security

## Examples

### Bulk Update User Roles

```python
# Update all agency members to admin role
operation = await bulk_processor.create_operation(
    operation_type=BulkOperationType.USER_UPDATE,
    entity_type="users",
    entity_ids=member_ids,
    params={"role": "agency_admin"},
    user=current_user,
    session=db
)
```

### Export Transactions for Reconciliation

```python
# Export all transactions for last month
operation = await bulk_processor.create_operation(
    operation_type=BulkOperationType.TRANSACTION_EXPORT,
    entity_type="transactions",
    entity_ids=transaction_ids,
    params={
        "format": "csv",
        "include_headers": True,
        "date_format": "ISO"
    },
    user=current_user,
    session=db
)
```

### Schedule Payouts

```python
# Schedule all pending payouts for next Friday
operation = await bulk_processor.create_operation(
    operation_type=BulkOperationType.PAYOUT_SCHEDULE,
    entity_type="payouts",
    entity_ids=pending_payout_ids,
    params={
        "scheduled_date": next_friday.isoformat()
    },
    user=current_user,
    session=db
)
```

## Integration with Other Systems

The bulk operations system integrates with:
- **Fraud Detection**: Operations are monitored for suspicious patterns
- **Rate Limiting**: Respects API rate limits
- **Caching**: Clears relevant caches after operations
- **Webhooks**: Can trigger webhooks on completion
- **Analytics**: Operation metrics are tracked for reporting