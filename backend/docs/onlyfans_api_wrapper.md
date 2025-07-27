# OnlyFans API Wrapper Documentation

## Overview

The OnlyFans API wrapper provides comprehensive integration with OnlyFans platform, enabling automated synchronization of financial data, subscriber information, content, and messaging. This module is designed to work seamlessly with the financial and analytics systems.

## Architecture

### Components

1. **OnlyFansService** (`modules/onlyfans_wrapper/application/service.py`)
   - Core service for OnlyFans API operations
   - Manages API client connections per model
   - Provides high-level operations (profile, fans, messages, posts)

2. **OnlyFansSyncService** (`modules/onlyfans_wrapper/application/sync_service.py`)
   - Enhanced sync service for financial data integration
   - Creates FinancialTransaction records with commission calculations
   - Syncs to analytics system for reporting
   - Handles billing cycle management

3. **API Endpoints** (`modules/onlyfans_wrapper/api/endpoints.py`)
   - RESTful endpoints for OnlyFans operations
   - Permission-based access control
   - Background task support for long-running syncs

## Key Features

### 1. Full Data Synchronization

Sync all OnlyFans data with a single endpoint:

```http
POST /api/v1/onlyfans/sync/{model_id}/all
```

Parameters:
- `start_date` (optional): Start date for transaction sync
- `end_date` (optional): End date for transaction sync  
- `sync_messages` (default: true): Whether to sync messages
- `force` (default: false): Force resync even if recently synced

This syncs:
- Profile information
- Fans/subscribers with subscription records
- Financial transactions with commission calculations
- Posts as content records
- Messages (including PPV sales)
- Statistics

### 2. Financial Transaction Integration

All OnlyFans transactions are automatically:
- Converted to FinancialTransaction records
- Calculated with proper commission rates
- Associated with billing cycles
- Synced to analytics for reporting

Transaction types mapped:
- `subscription` → Revenue
- `tip` → Revenue
- `ppv_message` → Revenue
- `ppv_post` → Revenue
- `refund` → Refund
- `chargeback` → Refund

### 3. Subscriber Management

Fan sync creates/updates:
- Fan profiles with OnlyFans user IDs
- Subscription records with pricing and dates
- Spending statistics (tips, PPV purchases)
- Activity tracking

### 4. Content Tracking

Posts are synced as Content records:
- Automatic content type detection (photo/video/text)
- PPV pricing information
- Engagement metrics (likes, comments)
- Media preview URLs

### 5. PPV Message Tracking

PPV messages are converted to financial transactions:
- Automatic transaction creation
- Linked to fan records
- Included in revenue calculations

## Usage Examples

### 1. Initial Setup

```python
# Add OnlyFans API key to model profile
model_profile.onlyfans_api_key = "your_api_key"
await db.commit()
```

### 2. Full Sync

```python
# Sync all data for last 30 days
response = await client.post(
    f"/api/v1/onlyfans/sync/{model_id}/all",
    params={"force": True}
)
```

### 3. Transaction Sync Only

```python
# Sync specific date range transactions
response = await client.post(
    f"/api/v1/onlyfans/sync/{model_id}/transactions",
    params={
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
)
```

### 4. Check Sync Status

```python
# Get sync status and recent stats
response = await client.get(
    f"/api/v1/onlyfans/sync/{model_id}/status"
)
```

## Rate Limiting

To prevent API abuse:
- Syncs are rate-limited to once per 5 minutes per model
- Use `force=true` to override rate limiting
- Background tasks handle long-running syncs

## Error Handling

The sync service includes comprehensive error handling:
- Individual transaction failures don't stop the sync
- Rollback on critical errors
- Detailed error logging
- API error responses with context

## Permissions

Sync operations require appropriate permissions:
- **Full sync**: MODEL, AGENCY_OWNER, AGENCY_MEMBER, SUPER_ADMIN
- **View data**: All authenticated users with model access
- **Send messages**: Users with messaging permissions

## Integration Points

### Financial System
- Creates FinancialTransaction records
- Calculates commissions automatically
- Associates with billing cycles

### Analytics System  
- Syncs revenue transactions
- Updates metric snapshots
- Provides real-time reporting data

### Content Management
- Creates Content records from posts
- Tracks PPV content pricing
- Stores engagement metrics

## Best Practices

1. **Regular Syncing**
   - Set up automated daily syncs
   - Use date ranges for specific periods
   - Monitor sync status endpoint

2. **Error Monitoring**
   - Check logs for sync failures
   - Monitor transaction creation
   - Verify commission calculations

3. **Performance**
   - Use `sync_messages=false` for faster syncs
   - Implement pagination for large datasets
   - Cache frequently accessed data

## Testing

The module includes comprehensive tests:
- Unit tests for sync logic
- Integration tests for endpoints
- Mock OnlyFans API responses
- Commission calculation verification

Run tests:
```bash
pytest tests/unit/test_onlyfans_sync_service.py
pytest tests/integration/test_onlyfans_sync_endpoints.py
```