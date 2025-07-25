# Plan to Fix All Failed Endpoints

## Overview
17 out of 30 endpoints are failing. This plan addresses each issue systematically.

## Phase 1: Infrastructure Fixes (Priority: CRITICAL)

### 1.1 Fix Database Pool Monitoring
**Issue**: `'AsyncAdaptedQueuePool' object has no attribute 'checked_out_connections'`
**Impact**: Health endpoint shows "degraded" status
**Fix**:
- Update health check to use correct SQLAlchemy pool attributes
- File: `backend/api/health.py`
- Replace `checked_out_connections` with `checkedout()` method

### 1.2 Fix Redis Client Expire Method
**Issue**: `'RedisClient' object has no attribute 'expire'`
**Impact**: Rate limiting middleware failing
**Fix**:
- Add missing `expire` method to RedisClient class
- File: `backend/core/infrastructure/redis_client.py`
- Implement async expire method

## Phase 2: Data Setup (Priority: HIGH)

### 2.1 Create Complete Test Data Structure
**Goal**: Set up proper test data hierarchy
**Steps**:
1. Create an agency with proper settings
2. Create users with all 6 roles:
   - Super Admin
   - Agency Owner (linked to agency)
   - Agency Admin (linked to agency)
   - Agency Member (linked to agency)
   - Model (linked to agency)
   - Chatter (linked to agency and model)
3. Create model profiles for Model users
4. Create initial financial data (commission rules, billing cycles)

### 2.2 Database Seed Script
**Create**: `scripts/seed_test_data.py`
**Contents**:
- Agency creation with white-label settings
- Users for each role with proper relationships
- Model profiles with Inflow/OnlyFans configurations
- Sample fans and financial data
- Initial analytics data

## Phase 3: Endpoint Fixes by Module

### 3.1 Analytics Module (3 endpoints failing)
**Issues**:
- Missing model profiles
- Missing required query parameters

**Fixes**:
1. Update test script to include required params:
   - `period_start` and `period_end` for categories
   - `start_date` and `end_date` for charts
2. Ensure model profiles exist before testing
3. Add default date ranges in test script

### 3.2 Financial Module (2 endpoints failing)
**Issues**:
- Internal server errors (500) for invoices and commission rules
- Likely missing agency context

**Fixes**:
1. Debug the exact errors in backend logs
2. Ensure agency_id is set in user context
3. Create default commission rules for test agency
4. Fix any missing database relationships

### 3.3 API Orchestration Module (3 endpoints failing)
**Issues**:
- Model profile not found
- Missing query parameters

**Fixes**:
1. Create model profiles in seed data
2. Add required query params to test script
3. Ensure Inflow/OnlyFans configs exist

### 3.4 Integration Modules (4 endpoints failing)
**Issues**:
- Permission errors (need MODEL role)
- Model profile not found
- Missing query parameters

**Fixes**:
1. Test with MODEL role user instead of AGENCY_MEMBER
2. Ensure model has Inflow/OnlyFans API keys configured
3. Add date parameters to analytics endpoints

### 3.5 Webhooks Module (2 endpoints failing)
**Issues**:
- Model not found or service not configured

**Fixes**:
1. Create model with proper API configurations
2. Add Inflow/OnlyFans settings to model profile

## Phase 4: Enhanced Test Script

### 4.1 Multi-Role Testing
**Update**: `scripts/test_api_endpoints.py`
**Features**:
- Test each endpoint with appropriate user role
- Create users for all 6 roles
- Switch authentication context based on endpoint requirements

### 4.2 Query Parameter Handling
**Add**:
- Default date ranges for analytics endpoints
- Required IDs and parameters for each endpoint
- Proper request body structures

### 4.3 Test Data Dependencies
**Ensure**:
- Create agency before users
- Create model profiles before testing model endpoints
- Set up financial data before testing financial endpoints

## Phase 5: Implementation Order

### Step 1: Fix Infrastructure (30 mins)
```python
# 1. Fix database pool monitoring
# 2. Fix Redis expire method
# 3. Restart backend
```

### Step 2: Create Seed Script (45 mins)
```python
# 1. Write comprehensive seed_test_data.py
# 2. Run seed script to populate database
# 3. Verify data creation
```

### Step 3: Update Test Script (30 mins)
```python
# 1. Add role-based authentication
# 2. Add required query parameters
# 3. Test with different user contexts
```

### Step 4: Fix Remaining Issues (1 hour)
```python
# 1. Debug any remaining 500 errors
# 2. Fix permission configurations
# 3. Ensure all relationships are proper
```

## Expected Outcome

After implementing this plan:
- ✅ 30/30 endpoints should return successful responses
- ✅ Health endpoint shows "healthy" status
- ✅ All roles can access their permitted endpoints
- ✅ Rate limiting works correctly
- ✅ Full API functionality verified

## Quick Commands

```bash
# Run seed script
python scripts/seed_test_data.py

# Test with enhanced script
python scripts/test_api_endpoints_enhanced.py

# Check specific role access
python scripts/test_role_permissions.py

# Monitor backend logs
docker-compose logs -f backend
```

## Success Metrics

1. **Health Check**: Returns "healthy" not "degraded"
2. **Auth Endpoints**: Work for all 6 roles
3. **Analytics**: Return data with proper date ranges
4. **Financial**: No 500 errors, proper commission calculations
5. **Integrations**: MODEL role can access all endpoints
6. **Webhooks**: Process events correctly
7. **Rate Limiting**: No Redis errors in logs