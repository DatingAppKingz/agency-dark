# Plan to Fix 11 Remaining Endpoints

## Overview
11 endpoints are failing due to 4 main issues:
1. Users have wrong roles (all are "agency_member")
2. Model profiles don't exist
3. Date format validation errors
4. Missing agency context for financial endpoints

## Phase 1: Fix User Roles (30 mins)

### Option A: Direct Database Update (Quickest)
Create SQL script to update existing users:

```sql
-- Update user roles to match their intended purpose
UPDATE users SET role = 'AGENCY_OWNER' WHERE email = 'owner@testagency.com';
UPDATE users SET role = 'AGENCY_ADMIN' WHERE email = 'admin@testagency.com';
UPDATE users SET role = 'MODEL' WHERE email = 'model@testagency.com';
UPDATE users SET role = 'CHATTER' WHERE email = 'chatter@testagency.com';
UPDATE users SET role = 'AGENCY_OWNER' WHERE email = 'owner@competitor.com';

-- Also need to create/update agencies and link users
INSERT INTO agencies (id, name, slug, domain, subscription_status, created_at, updated_at)
VALUES 
  (gen_random_uuid(), 'Test Agency Premium', 'test-agency-premium', 'testagency.com', 'ACTIVE', NOW(), NOW()),
  (gen_random_uuid(), 'Competitor Agency', 'competitor-agency', 'competitor.com', 'ACTIVE', NOW(), NOW())
ON CONFLICT (slug) DO NOTHING;

-- Link users to agencies
UPDATE users SET agency_id = (SELECT id FROM agencies WHERE slug = 'test-agency-premium')
WHERE email IN ('owner@testagency.com', 'admin@testagency.com', 'model@testagency.com', 'chatter@testagency.com');

UPDATE users SET agency_id = (SELECT id FROM agencies WHERE slug = 'competitor-agency')
WHERE email = 'owner@competitor.com';
```

### Option B: Add Admin Endpoint (Better long-term)
Create new endpoint: `PUT /api/v1/admin/users/{user_id}/role`
- Requires SUPER_ADMIN role
- Updates user role and agency assignment
- Validates role transitions

## Phase 2: Create Model Profiles (30 mins)

### SQL Script for Model Profiles
```sql
-- Create model profile for model@testagency.com
INSERT INTO model_profiles (
    id, user_id, agency_id, stage_name, onlyfans_username,
    bio, subscription_price, is_active,
    inflow_api_key, inflow_account_id,
    onlyfans_api_key, onlyfans_user_id,
    created_at, updated_at
)
SELECT 
    gen_random_uuid(),
    u.id,
    u.agency_id,
    'Emma Rose',
    'emmarose_of',
    'Premium content creator | DM for customs',
    9.99,
    true,
    'test_inflow_key_' || u.id,
    'inflow_account_' || u.id,
    'test_of_key_' || u.id,
    'of_user_' || u.id,
    NOW(),
    NOW()
FROM users u
WHERE u.email = 'model@testagency.com' AND u.role = 'MODEL';

-- Link chatter to model
INSERT INTO model_chatters (model_id, chatter_id, created_at)
SELECT 
    mp.id,
    u.id,
    NOW()
FROM model_profiles mp
CROSS JOIN users u
WHERE mp.stage_name = 'Emma Rose' 
AND u.email = 'chatter@testagency.com';
```

## Phase 3: Fix Date Format Issues (45 mins)

### Update Endpoints to Handle Date Formats
The issue: Endpoints expect `date` type but receive `datetime` strings.

**Files to update:**
1. `backend/modules/analytics/api/endpoints.py`
   - Update date parameters to use `date` type
   - Add validators to convert datetime to date

2. `backend/modules/api_orchestration/api/endpoints.py`
   - Same date parameter fixes

3. `backend/modules/integrations/inflow/api/endpoints.py`
   - Fix date validation

**Example fix:**
```python
from datetime import date, datetime
from pydantic import field_validator

class DateRangeParams(BaseModel):
    start_date: date
    end_date: date
    
    @field_validator('start_date', 'end_date', mode='before')
    def parse_date(cls, v):
        if isinstance(v, str):
            # Handle both date and datetime strings
            if 'T' in v:
                return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
            return date.fromisoformat(v)
        return v
```

## Phase 4: Fix Financial Context (45 mins)

### Create Financial Base Data
```sql
-- Create commission rules for each agency
INSERT INTO commission_rules (
    id, agency_id, name, tier, percentage,
    min_subscribers, max_subscribers, is_active,
    created_at, updated_at
)
SELECT 
    gen_random_uuid(),
    a.id,
    'Tier ' || tier_num || ' - ' || tier_name,
    CASE tier_num 
        WHEN 1 THEN 'TIER_1'
        WHEN 2 THEN 'TIER_2'
        WHEN 3 THEN 'TIER_3'
    END,
    CASE tier_num
        WHEN 1 THEN 70.00
        WHEN 2 THEN 65.00
        WHEN 3 THEN 60.00
    END,
    CASE tier_num
        WHEN 1 THEN 0
        WHEN 2 THEN 5001
        WHEN 3 THEN 10001
    END,
    CASE tier_num
        WHEN 1 THEN 5000
        WHEN 2 THEN 10000
        WHEN 3 THEN NULL
    END,
    true,
    NOW(),
    NOW()
FROM agencies a
CROSS JOIN (
    VALUES 
        (1, 'Starter'),
        (2, 'Growth'),
        (3, 'Premium')
) AS tiers(tier_num, tier_name)
WHERE a.slug IN ('test-agency-premium', 'competitor-agency');

-- Create current billing cycle
INSERT INTO billing_cycles (
    id, agency_id, start_date, end_date, is_closed,
    total_revenue, total_commission, total_payout,
    created_at, updated_at
)
SELECT
    gen_random_uuid(),
    a.id,
    date_trunc('month', CURRENT_DATE),
    date_trunc('month', CURRENT_DATE) + interval '1 month' - interval '1 day',
    false,
    0.00,
    0.00,
    0.00,
    NOW(),
    NOW()
FROM agencies a
WHERE a.slug IN ('test-agency-premium', 'competitor-agency');
```

### Fix Agency Context in Middleware
Update `backend/core/middleware/tenant.py` to properly set agency context from user's agency_id.

## Phase 5: Implementation Steps

### Step 1: Create and Run SQL Migration Script
```bash
# Create comprehensive SQL script
cat > scripts/fix_user_roles_and_data.sql << 'EOF'
-- All SQL from phases 1, 2, and 4 above
EOF

# Run via psql or database client
```

### Step 2: Update Date Handling in API
1. Find all endpoints with date parameters
2. Update to use proper date type
3. Add validators for date parsing
4. Test with updated format

### Step 3: Create Test Verification Script
```python
# scripts/verify_fixes.py
# 1. Check user roles are correct
# 2. Verify model profiles exist
# 3. Test date parameters work
# 4. Confirm financial endpoints respond
```

### Step 4: Run Enhanced Tests
```bash
# After all fixes
python scripts/test_api_endpoints_enhanced.py
```

## Expected Results After Fixes

### Endpoints That Will Be Fixed:

1. **Analytics (3 endpoints)**
   - `/analytics/dashboard/{model_id}` ✅
   - `/analytics/categories/{model_id}` ✅
   - `/analytics/charts/subscriber-growth` ✅

2. **Financial (2 endpoints)**
   - `/financial/invoices` ✅
   - `/financial/commission/rules` ✅

3. **API Orchestration (4 endpoints)**
   - `/orchestration/fans/{model_id}` ✅
   - `/orchestration/sync/{model_id}/status` ✅
   - `/orchestration/analytics/{model_id}` ✅
   - `/orchestration/messages/{model_id}` ✅

4. **Integrations (4 endpoints)**
   - `/integrations/inflow/test-connection/{model_id}` ✅
   - `/integrations/inflow/models/{model_id}/analytics` ✅
   - `/integrations/onlyfans/profile/{model_id}` ✅
   - `/integrations/onlyfans/fans/{model_id}` ✅

5. **Admin Endpoints (2 endpoints)**
   - `/financial/commission/rules` (POST) ✅
   - `/financial/billing-cycles` (POST) ✅

## Total Time Estimate

- Phase 1 (Roles): 30 minutes
- Phase 2 (Profiles): 30 minutes  
- Phase 3 (Dates): 45 minutes
- Phase 4 (Financial): 45 minutes
- Testing: 30 minutes

**Total: ~3 hours**

## Quick Start Commands

```bash
# 1. Fix database data
psql $DATABASE_URL < scripts/fix_user_roles_and_data.sql

# 2. Update date handling (manual code changes)

# 3. Restart backend
docker-compose restart backend

# 4. Run verification
python scripts/verify_fixes.py

# 5. Test all endpoints
python scripts/test_api_endpoints_enhanced.py
```

After these fixes, all 30 endpoints should be working (100%)!