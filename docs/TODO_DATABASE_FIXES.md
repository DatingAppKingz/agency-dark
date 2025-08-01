# Phase 1: Database & Foundation Fixes

This document tracks all database, model system, and error handling tasks that form the foundation of the platform.

## Database Issues (Priority: 🔴 High)

### 1. Fix Database Migration Naming Consistency
**Status:** ✅ COMPLETED  
**Description:** Alembic migrations have inconsistent naming (some use hashes, some use numbers)
**Location:** `/backend/alembic/versions/`
**Tasks:**
- [x] Rename all migration files to use consistent numbering scheme
- [x] Update migration dependencies to reference correct parent migrations
- [ ] Test full migration sequence from scratch
- [ ] Document migration naming convention

**Completed Actions:**
- Created backup at `/backend/alembic/versions_backup`
- Renamed 20 migration files to use 001-020 numbering
- Fixed all dependency references
- Created migration analysis scripts in `/backend/scripts/`

### 2. Create Missing Database Tables Properly
**Status:** ✅ COMPLETED  
**Description:** Several tables were manually created and need proper migrations
**Missing Tables:**
- chat_messages
- financial_transactions
- fan_profiles
- webhook_logs
**Tasks:**
- [x] Create proper Alembic migrations for missing tables
- [x] Add appropriate indexes and constraints
- [x] Ensure foreign key relationships are correct
- [ ] Test rollback functionality

**Completed Actions:**
- Created migration `021_add_missing_core_tables.py`
- Added `chat_messages` and `chat_conversations` tables for messaging
- Added `financial_transactions` table with proper indexes
- Added `fan_profiles` table for extended fan data
- Added `webhook_logs` table for webhook processing
- All tables include proper foreign keys and indexes

### 3. Add Indexes for Multi-Tenant Queries
**Status:** ✅ COMPLETED  
**Description:** Performance optimization for agency-filtered queries
**Tasks:**
- [x] Add agency_id index to all tenant-scoped tables
- [x] Create composite indexes for common query patterns
- [x] Add indexes for timestamp-based queries
- [ ] Benchmark query performance improvements

**Completed Actions:**
- Created migration `022_add_comprehensive_multi_tenant_indexes.py`
- Added agency_id indexes to: sessions, fans, fan_claims, model_chatters
- Added composite indexes for common patterns (agency + status/date/type)
- Added BRIN indexes for time-series data (financial_transactions, chat_messages, webhook_logs)
- Added GIN indexes for JSONB columns (custom_fields, payload, metadata)
- Created covering indexes for frequently accessed column combinations

### 4. Fix Database Pool Monitoring Issue
**Status:** ✅ COMPLETED  
**Error:** `'AsyncAdaptedQueuePool' object has no attribute 'checked_out_connections'`
**Location:** Health check endpoint
**Tasks:**
- [x] Update pool monitoring code to use correct SQLAlchemy 2.0 API
- [x] Fix health endpoint to properly report database status
- [x] Add connection pool metrics
- [ ] Test under load conditions

**Completed Actions:**
- Fixed `core/monitoring.py` to parse pool status string instead of calling methods
- Fixed `core/monitoring/collectors/database_collector.py` to use same approach
- Now properly extracts pool size, connections in pool, overflow, and checked out connections
- Added regex parsing for AsyncAdaptedQueuePool status string format

## Model Profile System (Priority: 🔴 High)

### 5. Create Model Profile Creation Flow
**Status:** ❌ Not Started  
**Description:** Models need profiles separate from user accounts
**Tasks:**
- [ ] Design model profile database schema
- [ ] Create API endpoint POST /api/v1/models
- [ ] Add model profile creation to user onboarding
- [ ] Implement model profile validation

### 6. Link Users to Model Profiles Correctly
**Status:** ❌ Not Started  
**Description:** Establish proper relationship between users and model profiles
**Tasks:**
- [ ] Add user_id foreign key to model_profiles table
- [ ] Create one-to-one relationship in SQLAlchemy models
- [ ] Update authentication to include model profile in JWT
- [ ] Add model profile to user response objects

### 7. Fix Endpoints Expecting model_id vs user_id
**Status:** ❌ Not Started  
**Affected Endpoints:**
- /api/v1/analytics/*
- /api/v1/chat/messages
- /api/v1/financial/commissions
**Tasks:**
- [ ] Audit all endpoints for model_id usage
- [ ] Update endpoints to accept both model_id and user_id
- [ ] Add proper parameter validation
- [ ] Update API documentation

### 8. Add Model Profile Management UI
**Status:** ❌ Not Started  
**Priority:** 🟡 Medium  
**Location:** `/frontend/src/pages/models/`
**Tasks:**
- [ ] Create ModelProfilePage component
- [ ] Add model profile form with validation
- [ ] Implement profile picture upload
- [ ] Add OnlyFans account linking UI

## Error Handling (Priority: 🔴 High)

### 9. Fix 500 Errors in Financial Module
**Status:** ❌ Not Started  
**Affected Endpoints:**
- /api/v1/financial/invoices
- /api/v1/financial/commission-rules
**Tasks:**
- [ ] Debug specific error causes
- [ ] Add proper error handling in financial services
- [ ] Implement transaction rollback on errors
- [ ] Add comprehensive error logging

### 10. Add Proper Error Responses
**Status:** ❌ Not Started  
**Priority:** 🟡 Medium  
**Description:** Replace generic 404/500 with meaningful error messages
**Tasks:**
- [ ] Create standardized error response format
- [ ] Implement custom exception classes
- [ ] Add error code system for frontend handling
- [ ] Update all endpoints with proper error responses

### 11. Fix Redis Rate Limiting Expire Issue
**Status:** ❌ Not Started  
**Priority:** 🟡 Medium  
**Error:** `'RedisClient' object has no attribute 'expire'`
**Tasks:**
- [ ] Update Redis client to use correct method names
- [ ] Fix rate limiting middleware
- [ ] Add rate limit headers to responses
- [ ] Test rate limiting functionality

### 12. Improve Error Messages for Debugging
**Status:** ❌ Not Started  
**Priority:** 🟢 Low  
**Tasks:**
- [ ] Add request ID to all error responses
- [ ] Include stack traces in development mode
- [ ] Create error message style guide
- [ ] Implement error translation system

## Testing Checklist

Before marking any task complete:
- [ ] Unit tests written and passing
- [ ] Integration tests updated
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] Code reviewed

## Notes

- Database changes require careful migration planning
- Always backup database before running migrations
- Test migrations on staging before production
- Model profile system is blocking many other features