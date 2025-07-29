# 28_01_2025 - AgencyDark Remaining Features Implementation Plan

## Executive Summary

This document outlines a comprehensive 12-week implementation plan to complete all remaining features from the original AgencyDark roadmap. The plan is divided into three phases prioritizing critical integrations, enhanced features, and long-term improvements.

**Total Duration**: 12 weeks  
**Start Date**: January 28, 2025  
**Target Completion**: April 22, 2025

---

## Phase Overview

### 🔴 Phase 1: Critical Features (Weeks 1-4)
Focus on completing external API integrations that are essential for platform functionality.

### 🟡 Phase 2: Enhanced Features (Weeks 5-8)
Implement advanced user features and establish robust DevOps practices.

### 🟢 Phase 3: Long-term Enhancements (Weeks 9-12)
Add enterprise features, ML capabilities, and achieve quality targets.

---

## 🔴 Phase 1: Critical Features (January 28 - February 25, 2025)

### Week 1: API Key Management UI
**Objective**: Create secure frontend interface for managing external API keys

**Deliverables**:
- API key settings page with secure input/display
- Key rotation interface with confirmation dialogs
- Usage statistics dashboard showing API call metrics
- Audit log viewer for key access history
- Integration with backend encryption service

**Technical Implementation**:
```typescript
// New files to create:
/frontend/src/pages/settings/ApiKeysPage.tsx
/frontend/src/components/settings/ApiKeyManager.tsx
/frontend/src/components/settings/ApiKeyForm.tsx
/frontend/src/services/api/apiKeys.ts
/frontend/src/types/apiKeys.ts
/frontend/src/hooks/useApiKeys.ts
```

**Success Criteria**:
- Secure key storage with encryption
- Real-time validation of API keys
- Usage tracking visible in UI
- Audit logs accessible to admins

### Week 2-3: Complete Sync Services
**Objective**: Implement full synchronization for Inflow and OnlyFans APIs

**Deliverables**:
- **Inflow Sync**:
  - Subscriber sync with delta updates
  - Message sync with pagination support
  - Content sync including media files
  - Transaction sync with reconciliation
  - Incremental sync logic for efficiency
  
- **OnlyFans Wrapper**:
  - Complete authentication flow
  - All content management endpoints
  - Fan interaction APIs
  - Revenue data synchronization
  - Media upload/download handling

**Technical Implementation**:
```python
# Files to enhance:
/backend/modules/inflow_wrapper/application/sync_service.py
/backend/modules/onlyfans_wrapper/application/sync_service.py
/backend/core/tasks/sync_tasks.py
/backend/api/v1/endpoints/sync_status.py
/backend/core/tasks/sync_scheduler.py
```

**Success Criteria**:
- Automated sync runs every 15 minutes
- Conflict resolution for concurrent updates
- Sync status dashboard showing progress
- Error recovery with retry logic

### Week 4: Webhook Processing System
**Objective**: Build robust webhook handling infrastructure

**Deliverables**:
- Webhook receiver with signature validation
- Async processing queue using Celery
- Retry mechanism with exponential backoff
- Dead letter queue for failed webhooks
- Webhook configuration UI
- Testing tools and debugging interface

**Technical Implementation**:
```python
# Backend components:
/backend/core/webhooks/webhook_processor.py
/backend/core/webhooks/webhook_validator.py
/backend/api/v1/webhooks/receivers.py
/backend/core/tasks/webhook_tasks.py

# Frontend components:
/frontend/src/pages/settings/WebhooksPage.tsx
/frontend/src/components/settings/WebhookTester.tsx
/frontend/src/components/settings/WebhookLogs.tsx
```

**Success Criteria**:
- 99.9% webhook delivery rate
- <1s processing time for webhooks
- Comprehensive logging and debugging
- Easy webhook testing interface

---

## 🟡 Phase 2: Enhanced Features (February 26 - March 25, 2025)

### Week 5: Bulk Operations UI
**Objective**: Enable efficient bulk actions across the platform

**Deliverables**:
- Universal bulk selection component
- Bulk action toolbar with common operations
- Progress tracking for long-running operations
- Undo/rollback functionality
- Integration with all major features

**Technical Implementation**:
```typescript
// Core components:
/frontend/src/components/common/BulkActionBar.tsx
/frontend/src/components/common/BulkProgressDialog.tsx
/frontend/src/hooks/useBulkSelection.ts
/frontend/src/hooks/useBulkOperations.ts
/frontend/src/utils/bulkOperations.ts
```

**Success Criteria**:
- Support for 1000+ item selections
- Real-time progress updates
- Graceful error handling
- Audit trail for bulk operations

### Week 6: Advanced Report Builder
**Objective**: Empower users to create custom reports

**Deliverables**:
- Drag-and-drop report designer
- 20+ pre-built report templates
- Custom field selection and filtering
- Report scheduling system
- Multiple export formats (PDF, Excel, CSV)
- Email delivery integration

**Technical Implementation**:
```typescript
// Frontend components:
/frontend/src/pages/reports/ReportBuilderPage.tsx
/frontend/src/components/reports/ReportDesigner.tsx
/frontend/src/components/reports/ReportScheduler.tsx
/frontend/src/components/reports/ReportTemplates.tsx
/frontend/src/services/reportBuilder.ts
```

**Success Criteria**:
- Intuitive report creation process
- <30s report generation time
- Scheduled reports delivered on time
- Template sharing between users

### Week 7: CI/CD Pipeline
**Objective**: Establish automated build and deployment processes

**Deliverables**:
- Multi-stage GitHub Actions workflows
- Automated testing on all PRs
- Staging deployment pipeline
- Production deployment with approvals
- Rollback mechanisms
- Deployment notifications

**Technical Implementation**:
```yaml
# GitHub Actions workflows:
/.github/workflows/ci.yml
/.github/workflows/cd-staging.yml
/.github/workflows/cd-production.yml
/.github/workflows/security-scan.yml
/scripts/deployment/rollback.sh
/scripts/deployment/health-check.sh
```

**Success Criteria**:
- All tests pass before merge
- <10 min build times
- Zero-downtime deployments
- Automated rollback on failures

### Week 8: Monitoring Stack
**Objective**: Implement comprehensive monitoring and alerting

**Deliverables**:
- Prometheus metrics collection
- Grafana dashboards (system, app, business)
- Alert rules for critical metrics
- Log aggregation with Loki
- Distributed tracing setup
- On-call rotation integration

**Technical Implementation**:
```yaml
# Monitoring configuration:
/prometheus/prometheus.yml
/prometheus/alerts.yml
/grafana/dashboards/system.json
/grafana/dashboards/application.json
/grafana/dashboards/business.json
/docker-compose.monitoring.yml
```

**Success Criteria**:
- <1 min alert response time
- 95% dashboard data accuracy
- 30-day metric retention
- Actionable alert descriptions

---

## 🟢 Phase 3: Long-term Enhancements (March 26 - April 22, 2025)

### Week 9-10: Advanced Analytics & ML
**Objective**: Implement ML-powered features for better insights

**Deliverables**:
- **Recommendation Engine**:
  - Content recommendations
  - Fan matching algorithm
  - Optimal pricing suggestions
  - Best posting times
  
- **User Clustering**:
  - Fan segmentation
  - Behavioral analysis
  - Cohort identification
  - Targeted campaigns
  
- **A/B Testing UI**:
  - Experiment creation wizard
  - Statistical significance calculator
  - Results visualization
  - Experiment history

**Technical Implementation**:
```python
# ML components:
/backend/core/ml_analytics/predictors/recommendation_engine.py
/backend/core/ml_analytics/predictors/user_clustering.py
/backend/core/ml_analytics/services/ab_testing_service.py

# Frontend:
/frontend/src/pages/experiments/ExperimentDashboard.tsx
/frontend/src/components/analytics/RecommendationPanel.tsx
```

**Success Criteria**:
- 15% improvement in engagement from recommendations
- Accurate fan segmentation
- Clear A/B test results
- Real-time ML predictions

### Week 11: Enterprise SSO Integration
**Objective**: Enable enterprise authentication methods

**Deliverables**:
- SAML 2.0 provider support
- OAuth/OIDC integration (Google, Microsoft, Custom)
- SSO configuration interface
- User attribute mapping
- Just-in-time provisioning
- SSO audit logging

**Technical Implementation**:
```python
# SSO components:
/backend/core/auth/sso/saml_provider.py
/backend/core/auth/sso/oauth_provider.py
/backend/core/auth/sso/user_mapper.py
/backend/api/v1/auth/sso.py

# Frontend:
/frontend/src/pages/settings/SSOConfiguration.tsx
/frontend/src/components/auth/SSOLoginButton.tsx
```

**Success Criteria**:
- Support for major IdP providers
- <3s SSO login time
- Seamless user provisioning
- Complete audit trail

### Week 12: Quality & Testing Sprint
**Objective**: Achieve 80% test coverage and quality benchmarks

**Deliverables**:
- Comprehensive test suite expansion
- Performance optimization
- Security vulnerability fixes
- Documentation updates
- Load testing scenarios
- Accessibility improvements

**Technical Implementation**:
```bash
# Test files to create/enhance:
/backend/tests/unit/test_sync_services.py
/backend/tests/integration/test_webhooks.py
/backend/tests/e2e/test_user_flows.py
/frontend/src/__tests__/components/
/frontend/src/__tests__/hooks/
/frontend/cypress/e2e/
```

**Success Criteria**:
- 80% code coverage achieved
- All critical paths tested
- <200ms average API response
- Zero high-severity vulnerabilities

---

## Resource Allocation

### Team Composition
- **Frontend Developer**: 60% allocation throughout
- **Backend Developer**: 60% allocation throughout
- **DevOps Engineer**: 20% (Weeks 1-6), 80% (Weeks 7-8), 20% (Weeks 9-12)
- **QA Engineer**: 20% (Weeks 1-11), 80% (Week 12)
- **Project Manager**: 20% allocation throughout

### Sprint Schedule
- **Sprint 1** (Weeks 1-2): API Integration Foundation
- **Sprint 2** (Weeks 3-4): Sync & Webhooks
- **Sprint 3** (Weeks 5-6): User Features
- **Sprint 4** (Weeks 7-8): Infrastructure
- **Sprint 5** (Weeks 9-10): ML & Analytics
- **Sprint 6** (Weeks 11-12): Enterprise & Quality

---

## Risk Management

### Identified Risks
1. **External API Changes**
   - *Mitigation*: Version locking, adapter pattern
   
2. **Performance Degradation**
   - *Mitigation*: Load testing, caching strategy
   
3. **Security Vulnerabilities**
   - *Mitigation*: Weekly security scans, code reviews
   
4. **Scope Creep**
   - *Mitigation*: Strict change control process

---

## Success Metrics

### Technical KPIs
- API response time: <200ms (p95)
- Test coverage: >80%
- Deployment frequency: Daily
- Mean time to recovery: <30min
- Error rate: <0.1%

### Business KPIs
- User satisfaction: >4.5/5
- Feature adoption: >60% within 30 days
- Support ticket reduction: 25%
- Platform uptime: 99.9%

---

## Communication Plan

### Regular Updates
- Daily standups (dev team)
- Weekly progress reports
- Bi-weekly stakeholder demos
- Monthly steering committee

### Documentation
- API documentation updates
- User guides for new features
- Technical architecture docs
- Runbooks for operations

---

## Post-Implementation

### Handover Activities
- Knowledge transfer sessions
- Operations runbook creation
- Performance baseline establishment
- User training materials

### Maintenance Plan
- Monthly security updates
- Quarterly feature reviews
- Annual architecture assessment
- Continuous monitoring setup

---

## Appendix: Quick Start Commands

```bash
# Week 1: API Key Management
cd frontend && npm install @mui/x-data-grid-pro

# Week 5: Bulk Operations
cd frontend && npm install react-window react-virtualized-auto-sizer

# Week 6: Report Builder
cd frontend && npm install react-beautiful-dnd @tanstack/react-table

# Week 7: CI/CD
git checkout -b feature/github-actions
mkdir -p .github/workflows

# Week 8: Monitoring
docker-compose -f docker-compose.monitoring.yml up -d

# Week 11: SSO
cd backend && pip install python-saml2 authlib
```

---

**Document Version**: 1.0  
**Last Updated**: January 28, 2025  
**Next Review**: February 4, 2025# Plan to Fix 11 Remaining Endpoints

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

After these fixes, all 30 endpoints should be working (100%)!# Plan to Fix All Failed Endpoints

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
7. **Rate Limiting**: No Redis errors in logs# AgencyDark Frontend Implementation Plan

## Overview
Comprehensive plan to build the complete frontend for AgencyDark platform using Next.js 15, TypeScript, Material-UI, and Socket.IO.

## Architecture Overview

### Tech Stack
- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **UI Library**: Material-UI v7
- **State Management**: Zustand
- **Data Fetching**: TanStack Query
- **Real-time**: Socket.IO Client
- **Charts**: Recharts
- **Forms**: React Hook Form + Zod
- **Authentication**: JWT with refresh tokens

### Design Patterns
- Feature-based folder structure
- Atomic design for components
- Container/Presentational pattern
- Custom hooks for business logic
- Service layer for API calls

## Implementation Phases

### Phase 1: Foundation & Authentication (Days 1-3)

#### 1.1 Project Setup
- [x] Configure absolute imports
- [x] Set up environment variables
- [x] Configure Material-UI theme
- [x] Set up global styles
- [x] Configure axios with interceptors
- [x] Set up error boundary

#### 1.2 Authentication System
- [x] Create auth service layer
- [x] Implement JWT token management
- [x] Build login page
- [x] Build registration page
- [x] Implement password reset flow
- [x] Create auth guard HOC
- [x] Set up Zustand auth store
- [x] Handle token refresh

#### 1.3 Layout Components
- [x] Main layout with navigation
- [x] Sidebar component
- [x] Header with user menu
- [x] Role-based navigation
- [x] Responsive mobile menu
- [x] Loading states
- [x] Error pages (404, 500)

### Phase 2: Core Dashboard & User Management (Days 4-6)

#### 2.1 Dashboard Views
- [x] Super Admin dashboard
- [x] Agency Owner dashboard
- [x] Agency Admin dashboard
- [x] Model dashboard
- [x] Chatter dashboard
- [x] Member dashboard
- [x] Analytics widgets
- [x] Quick stats cards

#### 2.2 User Management
- [x] Users list with DataGrid
- [x] User creation form
- [x] User edit modal
- [x] Role assignment
- [x] Bulk actions
- [x] Search and filters
- [x] User profile page

#### 2.3 Agency Management
- [x] Agency settings page
- [x] Agency profile edit
- [x] Subscription management
- [x] Team members view
- [x] Invitation system

### Phase 3: Model Management (Days 7-9)

#### 3.1 Model Profiles
- [x] Models list view
- [x] Model profile creation
- [x] Profile edit form
- [x] Content preferences
- [x] Availability settings
- [x] Earnings dashboard
- [x] Performance metrics

#### 3.2 Model Analytics
- [x] Revenue charts
- [x] Subscriber growth
- [x] Message volume
- [x] Top fans view
- [x] Conversion metrics
- [x] Export functionality

### Phase 4: Chat System (Days 10-12)

#### 4.1 Chat Interface
- [x] Chat list sidebar
- [x] Message thread view
- [x] Message input with attachments
- [x] Emoji picker
- [x] Voice messages
- [x] Image/video preview
- [x] Message search

#### 4.2 Real-time Features
- [x] Socket.IO connection manager
- [x] Typing indicators
- [x] Online status
- [x] Message delivery status
- [x] Push notifications
- [x] Unread counts
- [x] Real-time updates

#### 4.3 Chat Management
- [x] Fan assignment
- [x] Chat filters
- [x] Canned responses
- [x] Chat history
- [x] Export conversations
- [x] Block/report functionality

### Phase 5: Financial Module (Days 13-15)

#### 5.1 Financial Dashboard
- [x] Financial types and API service layer
- [x] Revenue overview
- [x] Payout management
- [x] Transaction history
- [x] Commission calculator
- [x] Invoice generation
- [x] Payment methods

#### 5.2 Reporting
- [x] Financial reports
- [x] Tax documents
- [x] Earnings statements
- [x] Commission breakdown
- [x] Export to CSV/PDF (integrated in components)
- [x] Date range filters (integrated in components)

### Phase 6: Analytics & Insights (Days 16-18)

#### 6.1 Analytics Dashboard
- [x] Platform-wide analytics (Super Admin)
- [x] Agency analytics
- [x] Model performance
- [x] Chatter metrics
- [x] Custom date ranges
- [ ] Comparison views

#### 6.2 Visualization Components
- [x] Line charts (trends)
- [x] Bar charts (comparisons)
- [x] Pie charts (distributions)
- [x] Heat maps (activity)
- [x] Data tables with export
- [ ] Real-time updates

### Phase 7: White-Label & Customization (Days 19-20)

#### 7.1 White-Label Settings
- [x] Theme customization
- [x] Logo upload
- [x] Color scheme editor
- [x] Font selection
- [x] Custom domain setup
- [x] Email templates

#### 7.2 Agency Customization
- [x] Custom branding
- [ ] Personalized dashboard
- [ ] Custom fields
- [ ] Agency-specific features
- [ ] Multi-language support

### Phase 8: Integration & Testing (Days 21-23)

#### 8.1 Integration Testing
- [ ] API integration tests
- [ ] Socket.IO connection tests
- [ ] Authentication flow tests
- [ ] Role-based access tests
- [ ] Multi-tenant isolation tests

#### 8.2 Performance Optimization
- [ ] Code splitting
- [ ] Lazy loading
- [ ] Image optimization
- [ ] Caching strategies
- [ ] Bundle size optimization
- [ ] SEO optimization

### Phase 9: Polish & Deployment (Days 24-25)

#### 9.1 Final Polish
- [ ] Accessibility (a11y)
- [ ] Cross-browser testing
- [ ] Mobile responsiveness
- [ ] Error handling
- [ ] Loading states
- [ ] Empty states

#### 9.2 Deployment Preparation
- [ ] Production build
- [ ] Environment configuration
- [ ] Docker setup
- [ ] CI/CD pipeline
- [ ] Monitoring setup
- [ ] Documentation

## Component Structure

```
frontend/src/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   ├── register/
│   │   └── reset-password/
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── users/
│   │   ├── models/
│   │   ├── chat/
│   │   ├── analytics/
│   │   ├── financial/
│   │   └── settings/
│   └── api/
├── components/
│   ├── common/
│   │   ├── Layout/
│   │   ├── Navigation/
│   │   ├── DataGrid/
│   │   └── Charts/
│   ├── auth/
│   │   ├── LoginForm/
│   │   ├── RegisterForm/
│   │   └── AuthGuard/
│   ├── dashboard/
│   │   ├── StatsCard/
│   │   ├── ActivityFeed/
│   │   └── QuickActions/
│   ├── chat/
│   │   ├── ChatList/
│   │   ├── MessageThread/
│   │   └── MessageInput/
│   └── models/
│       ├── ModelCard/
│       ├── ModelProfile/
│       └── EarningsChart/
├── hooks/
│   ├── useAuth.ts
│   ├── useSocket.ts
│   ├── usePermissions.ts
│   └── useAnalytics.ts
├── services/
│   ├── api/
│   │   ├── auth.ts
│   │   ├── users.ts
│   │   ├── models.ts
│   │   ├── chat.ts
│   │   └── analytics.ts
│   ├── socket/
│   │   ├── connection.ts
│   │   └── events.ts
│   └── storage/
│       └── tokens.ts
├── store/
│   ├── auth.ts
│   ├── user.ts
│   ├── chat.ts
│   └── ui.ts
├── types/
│   ├── api.ts
│   ├── models.ts
│   └── chat.ts
└── utils/
    ├── constants.ts
    ├── validators.ts
    └── formatters.ts
```

## Key Implementation Details

### 1. Authentication Flow
```typescript
// JWT stored in httpOnly cookies
// Refresh token rotation
// Role-based route protection
// Automatic token refresh
```

### 2. API Service Layer
```typescript
// Centralized error handling
// Request/response interceptors
// Automatic retry logic
// Loading state management
```

### 3. Real-time Integration
```typescript
// Socket.IO singleton
// Automatic reconnection
// Event-based updates
// Optimistic UI updates
```

### 4. State Management
```typescript
// Zustand for global state
// React Query for server state
// Local storage persistence
// Middleware for logging
```

## Testing Strategy

### Unit Tests
- Component testing with React Testing Library
- Hook testing
- Service layer testing
- Store testing

### Integration Tests
- API integration tests
- Socket.IO connection tests
- Authentication flow tests
- Multi-step form tests

### E2E Tests
- Critical user journeys
- Role-based scenarios
- Multi-tenant isolation
- Payment flows

## Performance Targets

- **First Contentful Paint**: < 1.5s
- **Time to Interactive**: < 3.5s
- **Lighthouse Score**: > 90
- **Bundle Size**: < 250KB initial
- **API Response Time**: < 200ms avg

## Security Considerations

1. **Authentication**
   - Secure token storage
   - CSRF protection
   - Session management
   - Rate limiting

2. **Data Protection**
   - Input sanitization
   - XSS prevention
   - Content Security Policy
   - HTTPS enforcement

3. **Multi-tenancy**
   - Data isolation
   - Role enforcement
   - Audit logging
   - Permission checks

## Deliverables

### Week 1
- Complete authentication system
- Basic dashboard for all roles
- User management interface

### Week 2
- Model management system
- Chat interface with real-time
- Financial module basics

### Week 3
- Analytics dashboards
- White-label customization
- Testing and optimization

### Week 4
- Final polish
- Documentation
- Deployment setup

## Success Criteria

1. **Functionality**
   - All user roles can perform their tasks
   - Real-time features work reliably
   - Multi-tenant isolation maintained

2. **Performance**
   - Meets all performance targets
   - Smooth animations (60 FPS)
   - Fast page transitions

3. **Quality**
   - 80%+ test coverage
   - Zero critical bugs
   - Accessibility compliant

4. **User Experience**
   - Intuitive navigation
   - Consistent design
   - Mobile responsive

## Risk Mitigation

1. **Technical Risks**
   - Complex state management → Use proven patterns
   - Socket.IO scaling → Implement fallbacks
   - Performance issues → Progressive enhancement

2. **Timeline Risks**
   - Feature creep → Strict MVP scope
   - Integration delays → Parallel development
   - Testing bottlenecks → Continuous testing

## Next Steps

1. **Immediate (Day 1)**
   - Set up development environment
   - Configure Material-UI theme
   - Implement authentication service

2. **Short-term (Week 1)**
   - Complete Phase 1 & 2
   - Begin Phase 3
   - Daily progress reviews

3. **Long-term (Month 1)**
   - Complete all phases
   - Deploy to staging
   - User acceptance testing# AgencyDark Frontend SPA Implementation Plan

## Overview
Comprehensive plan to build a Single Page Application (SPA) frontend for AgencyDark platform using React with Vite, TypeScript, Material-UI, and Socket.IO.

## Architecture Overview

### Tech Stack (SPA Approach)
- **Build Tool**: Vite (instead of Next.js)
- **Framework**: React 18+ 
- **Language**: TypeScript
- **Routing**: React Router v6
- **UI Library**: Material-UI v7
- **State Management**: Zustand + React Query
- **Real-time**: Socket.IO Client
- **Charts**: Recharts
- **Forms**: React Hook Form + Zod
- **Authentication**: JWT with interceptors

### SPA Architecture Benefits
- True single page experience
- Faster navigation between views
- Better state persistence
- Offline capabilities
- Smaller hosting requirements
- Better real-time integration

## Project Setup & Migration

### Migration from Next.js to Vite SPA
```bash
# New project structure
frontend/
├── src/
│   ├── main.tsx          # Entry point
│   ├── App.tsx           # Root component
│   ├── router/           # Route definitions
│   ├── layouts/          # Layout components
│   ├── pages/            # Page components
│   ├── components/       # Reusable components
│   ├── services/         # API services
│   ├── hooks/            # Custom hooks
│   ├── store/            # Zustand stores
│   ├── utils/            # Utilities
│   └── types/            # TypeScript types
├── public/               # Static assets
├── index.html            # SPA entry
├── vite.config.ts        # Vite configuration
└── package.json          # Dependencies
```

## Implementation Phases

### Phase 1: SPA Foundation & Core Setup (Days 1-3)

#### 1.1 Vite Project Setup
- [ ] Initialize Vite with React + TypeScript
- [ ] Configure path aliases
- [ ] Set up environment variables (.env)
- [ ] Configure proxy for API calls
- [ ] Set up hot module replacement
- [ ] Configure build optimization

#### 1.2 Routing Architecture
```typescript
// React Router v6 setup
const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    errorElement: <ErrorBoundary />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" />
      },
      {
        path: "auth",
        element: <AuthLayout />,
        children: [
          { path: "login", element: <LoginPage /> },
          { path: "register", element: <RegisterPage /> },
          { path: "forgot-password", element: <ForgotPasswordPage /> }
        ]
      },
      {
        path: "dashboard",
        element: <ProtectedRoute><DashboardLayout /></ProtectedRoute>,
        children: [
          { index: true, element: <DashboardHome /> },
          { path: "users", element: <UsersPage /> },
          { path: "models", element: <ModelsPage /> },
          { path: "chat", element: <ChatPage /> },
          { path: "analytics", element: <AnalyticsPage /> },
          { path: "financial", element: <FinancialPage /> },
          { path: "settings", element: <SettingsPage /> }
        ]
      }
    ]
  }
]);
```

#### 1.3 Authentication System (SPA-Specific)
- [ ] Token storage in memory + secure refresh
- [ ] Axios interceptors for auth headers
- [ ] Auto-refresh token mechanism
- [ ] Protected route component
- [ ] Persistent login state
- [ ] Logout cleanup

```typescript
// Auth Service for SPA
class AuthService {
  private accessToken: string | null = null;
  
  setToken(token: string) {
    this.accessToken = token;
    // Don't store in localStorage for security
  }
  
  getToken() {
    return this.accessToken;
  }
  
  async refreshToken() {
    // Refresh logic with httpOnly cookie
  }
}
```

### Phase 2: State Management & Data Flow (Days 4-5)

#### 2.1 Zustand Store Structure
```typescript
// Global stores for SPA
const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  permissions: [],
  login: async (credentials) => { /* ... */ },
  logout: () => { /* ... */ },
  checkAuth: async () => { /* ... */ }
}));

const useUIStore = create((set) => ({
  sidebarOpen: true,
  theme: 'light',
  notifications: [],
  toggleSidebar: () => { /* ... */ },
  addNotification: (notification) => { /* ... */ }
}));

const useChatStore = create((set) => ({
  conversations: [],
  activeConversation: null,
  messages: {},
  typingUsers: {},
  sendMessage: async (message) => { /* ... */ }
}));
```

#### 2.2 React Query Configuration
```typescript
// Query client for server state
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 3,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

// Custom hooks for data fetching
export const useUsers = () => {
  return useQuery({
    queryKey: ['users'],
    queryFn: userService.getUsers,
  });
};
```

### Phase 3: Core SPA Components (Days 6-8)

#### 3.1 Layout System
- [ ] App shell with persistent header/sidebar
- [ ] Lazy-loaded route components
- [ ] Breadcrumb navigation
- [ ] Loading progress bar
- [ ] Error boundaries
- [ ] Offline indicator

```typescript
// Main App Layout for SPA
const AppLayout = () => {
  const { isAuthenticated } = useAuthStore();
  
  return (
    <Box sx={{ display: 'flex' }}>
      {isAuthenticated && <Sidebar />}
      <Box component="main" sx={{ flexGrow: 1 }}>
        {isAuthenticated && <Header />}
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </Box>
      <NotificationContainer />
      <SocketIOProvider />
    </Box>
  );
};
```

#### 3.2 Progressive Enhancement
- [ ] Service worker for offline support
- [ ] PWA manifest
- [ ] Cache strategies
- [ ] Background sync
- [ ] Push notifications

### Phase 4: Real-time Integration (Days 9-11)

#### 4.1 Socket.IO Manager
```typescript
// Singleton Socket.IO connection for SPA
class SocketManager {
  private socket: Socket | null = null;
  
  connect(token: string) {
    this.socket = io(import.meta.env.VITE_WS_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
    });
    
    this.setupEventListeners();
  }
  
  private setupEventListeners() {
    this.socket?.on('notification', (data) => {
      useUIStore.getState().addNotification(data);
    });
    
    this.socket?.on('chat:message', (data) => {
      useChatStore.getState().addMessage(data);
    });
  }
}
```

#### 4.2 Optimistic Updates
- [ ] Immediate UI updates
- [ ] Background sync
- [ ] Conflict resolution
- [ ] Retry mechanisms
- [ ] Offline queue

### Phase 5: SPA-Specific Features (Days 12-14)

#### 5.1 Client-Side Routing
- [ ] Route guards with permissions
- [ ] Navigation progress indicator
- [ ] Route transitions
- [ ] Deep linking support
- [ ] Browser history management
- [ ] Query string handling

#### 5.2 Performance Optimization
- [ ] Code splitting by route
- [ ] Dynamic imports
- [ ] Tree shaking
- [ ] Bundle analysis
- [ ] Compression
- [ ] CDN integration

```typescript
// Lazy loading routes
const DashboardPage = lazy(() => import('./pages/Dashboard'));
const UsersPage = lazy(() => import('./pages/Users'));
const ModelsPage = lazy(() => import('./pages/Models'));
```

### Phase 6: Advanced SPA Features (Days 15-17)

#### 6.1 Offline Capabilities
- [ ] IndexedDB for local storage
- [ ] Sync when online
- [ ] Offline mode indicators
- [ ] Queue actions
- [ ] Conflict resolution

#### 6.2 Virtual Scrolling
- [ ] Large list optimization
- [ ] Infinite scroll
- [ ] Virtualized tables
- [ ] Image lazy loading
- [ ] Intersection observer

### Phase 7: Testing & Optimization (Days 18-20)

#### 7.1 SPA Testing Strategy
- [ ] Component testing
- [ ] Integration tests
- [ ] E2E with Playwright
- [ ] Performance testing
- [ ] Bundle size monitoring

#### 7.2 Build Optimization
```typescript
// Vite config for production
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'mui-vendor': ['@mui/material', '@emotion/react'],
          'utils': ['lodash', 'date-fns', 'axios'],
        },
      },
    },
    target: 'esnext',
    minify: 'terser',
  },
});
```

## SPA Deployment Strategy

### Static Hosting Options
1. **Vercel/Netlify**
   - Automatic deployments
   - Edge functions for API
   - Global CDN

2. **AWS S3 + CloudFront**
   - Cost-effective
   - High performance
   - Custom domain

3. **Docker + Nginx**
   - Self-hosted option
   - Full control
   - Kubernetes ready

### Nginx Configuration for SPA
```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  
  # SPA routing - serve index.html for all routes
  location / {
    try_files $uri $uri/ /index.html;
  }
  
  # API proxy
  location /api {
    proxy_pass http://backend:8000;
  }
  
  # WebSocket proxy
  location /socket.io {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```

## Key SPA Implementation Patterns

### 1. Authentication Flow
```typescript
// SPA Auth Flow
1. User enters credentials
2. API returns access token + sets httpOnly refresh cookie
3. Store access token in memory only
4. Add token to all API requests
5. Auto-refresh before expiry
6. Handle 401s globally
```

### 2. Data Caching Strategy
```typescript
// Intelligent caching for SPA
- User data: Cache for session
- Analytics: Cache for 5 minutes
- Chat messages: Cache indefinitely
- Financial data: No cache
- Settings: Cache until change
```

### 3. State Persistence
```typescript
// Selective state persistence
const persist = {
  theme: localStorage,
  language: localStorage,
  filters: sessionStorage,
  auth: memory only,
  sensitive: never persist
};
```

## Development Workflow

### Local Development
```bash
# Start development server
npm run dev

# API proxy configured in vite.config.ts
# Hot reload enabled
# Source maps enabled
```

### Build Process
```bash
# Production build
npm run build

# Preview production build
npm run preview

# Bundle analysis
npm run analyze
```

## Performance Metrics

### SPA-Specific Targets
- **Initial Load**: < 2s (with code splitting)
- **Route Change**: < 100ms
- **API Response**: < 200ms
- **Real-time Latency**: < 50ms
- **Bundle Size**: < 200KB initial chunk

## Security Considerations for SPA

1. **Token Management**
   - Never store sensitive tokens in localStorage
   - Use httpOnly cookies for refresh tokens
   - Implement token rotation
   - Short-lived access tokens

2. **API Security**
   - CORS properly configured
   - Rate limiting per user
   - Request signing
   - Input validation

3. **Content Security**
   - CSP headers
   - XSS protection
   - Sanitize user input
   - Secure CDN usage

## Monitoring & Analytics

### SPA Monitoring
- Route navigation tracking
- API call performance
- Error tracking (Sentry)
- User behavior analytics
- Real-time connection status

## Conclusion

The SPA approach offers several advantages for AgencyDark:
- Better user experience with instant navigation
- Superior real-time capabilities
- Easier state management
- Lower hosting costs
- Better offline support

The migration from Next.js to Vite-based SPA can be completed within the same timeline while providing a more responsive and modern application architecture.# AgencyDark Requirements Questions

# 1. Business Model & Core Features

## What are the primary services agencies provide to OnlyFans models?
- System has to be sort of a wrapper around Inflow and https://onlyfansapi.com functionalities, also with possibility for chatter to claim certain fan and block it in a way that a different chatter will not be able to claim particular user (permanently or during the time of particular chatter's work - that's open to discussion)
## What metrics/KPIs do agencies track (revenue share, content performance, subscriber growth)?
- In AgencyDark, we want to expose for the models and their managers clear indicators metrics and KPIs to grow their business: 1.1) Popularity of film categories, 1.2) Popularity of particular films, 2) Linear charts: 2.1) Amount of subscribers as a linear chart Y axis - subscribers, X axis - time, 2.2) Amount of non-paying fans as a linear chart Y axis - fans, X axis - time, 2.3.1) Income in time - Y axis - money, X axis - time, 2.3.2.) Income from subscriptions in time - Y axis - money, X axis - time, 2.3.3) - Income from tips in time - Y axis money, X axis time, 2.3.4) Income from PPV films in time - Y axis money, X axis time. 3) Income from particular user(s) in time - Y axis - money, X axis - time. Ad. 3) - this chart has to be configurable in a way that user may see up to 10 users on a chart simultaneously (different colors for lines)
## How does billing work (agency subscriptions, model payments, commission structures)?
- We take comissions from the content creators, and our pricing model includes three stages: 1) 0-5000 paying subscribers; we take 70%, 2) 5001 - 10000 paying subscribers; we take 65%, if amount of paying subscribers is above 10000 the we take 60 %.
## What reporting/analytics are critical for agencies and models?
- Can't respond to that question right now, it's up to be discussed.

# 2. Inflow Integration
## What specific Inflow API endpoints will we wrap?
- All of them for now
## Which features remain Inflow-dependent vs built natively?
- All features provided by Inflow will be inflow-dependent
## Which features remain https://onlyfansapi.com/ dependent vs built natively?
- All features provided by onlyfansapi will be onlyfansapi-dependent
## How do we handle API rate limits and data synchronization?
- There are no api rate limits for Inflow or Onlyfansapi as far as i know, so we should simply stick to api calls on request (once particular user is logging in, all data has to be synchronized) - the exception for that is chatter account where chatters has to have option to be notified immediatelly once particular user sends a message - if they claimed that user - if they didn't, they should have notifications about all messages being sent by unclaimed potential fans. 
## What's the migration path from wrapper to standalone?
- There is no such a path for now, the MVP is a wrapper around Inflow and Onlyfansapi.

# 3. User Roles & Permissions
## Beyond the defined roles (super_admin, agency_owner, agency_admin, model, chatter), what specific permissions does each need?
- 1) super_admin - All system functionalities, only they will have readonly access to the chat, 2) agency_owner - All functionalities in a context of the models in their agencies (CRUD), only they will have readonly access to the chat, 3) agency_admin - All functionalities in a context of the models (CRUD), but only they will have readonly access to the chat, 4) Model - All functionalities in context of particlar model's account - CRUD for content, full access to analytics and content creation, inspection of commentaries, and private messages, can claim particular fan (even if chatter did it earlier) and block him from receiving messages from other chatters. 5) Chatter - Full access to the particular model's commentaries and private messages. Can claim particular fan in a way that only they will be able to message them, and a claimed user will be visually distinguished from the others in the comments section for films.

## Can agencies customize role permissions?
- super_admin can decide, that particular agency will be able to customize the role permissions or not.

## How do models interact with multiple agencies?
- Models has many-to-one relation with agency, particular model can be cooperating only with one agency at a time.

## Do we need sub-agencies or team structures?
- Not for now, we just need a space for that in case this will become business requirement. System has to be designed in a modular way which will enable that.

# 4. Model Management
## How are models onboarded to agencies?
- Onboarding is quite simple - signing the contract and creating an account.
## What data is tracked per model (profiles, content, earnings, schedules)?
- In AgencyDark, we want to expose for the models and their managers clear indicators metrics and KPIs to grow their business: 1.1) Popularity of film categories, 1.2) Popularity of particular films, 2) Linear charts: 2.1) Amount of subscribers as a linear chart Y axis - subscribers, X axis - time, 2.2) Amount of non-paying fans as a linear chart Y axis - fans, X axis - time, 2.3.1) Income in time - Y axis - money, X axis - time, 2.3.2.) Income from subscriptions in time - Y axis - money, X axis - time, 2.3.3) - Income from tips in time - Y axis money, X axis time, 2.3.4) Income from PPV films in time - Y axis money, X axis time. 3) Income from particular user(s) in time - Y axis - money, X axis - time. Ad. 3) - this chart has to be configurable in a way that user may see up to 10 users on a chart simultaneously (different colors for lines)

## How is content managed (storage, approval workflows, posting schedules)?
- In a same way as Onlyfans does

## What communication features between agencies and models?
- For MVP there's no need for communication between agencies and models.

# 5. Financial Features
## Payment processing requirements (Stripe, PayPal, crypto)?
- Crypto
## Services downtime period (during the notice period to contract termination)
-  0 < 5000 paying subscribers - 30 days, 1000 - 5001 paying subscribers - 60 days, 10000 paying subscribers and above - 90 days.
## How are commissions calculated and distributed?
- 1) 0-5000 paying subscribers; we take 70%, 2) 5001 - 10000 paying subscribers; we take 65%, if amount of paying subscribers is above 10000 the we take 60 %.
## Invoice generation and expense tracking?
- Invoice generation is desired, but only that for MVP
## Multi-currency support needed?
- Multi Cryptocurrencies support needed.

# 6. White-Label Requirements
## Customization depth (colors, logos, custom domains)?
- Agency's logo, Model's logo, colors: light or dark theme (day & night), no custom domains for now, but support for those can be used in the future.
## Feature toggles per agency?
- Not for MVP
## Custom onboarding flows?
- Not for MVP
## Branded mobile apps planned?
- No

# 7. Technical Constraints
## Expected scale (agencies, models, concurrent users)?
- System has to be as fast as possible, we aim high
## Data retention policies?
- As long as we will cooperate with particular agency we will maintain all data, when cooperation will end (after downtime period), data will be wiped out.
## Compliance requirements (GDPR, age verification, content policies)?
- Only GDPR applicable for MVP
## Third-party integrations beyond Inflow?
- For sure we'll need Onlyfansapi, I don't know how about the rest of them

# 8. Priority Features
## What's the MVP feature set for initial launch?
- All functionalities Inflow and Onlyfansapi exposes has to be implemented, if both will provide certain feature, then Onlyfansapi will be used.
## Which features differentiate from competitors?
- Don't have anything in mind
## Any features explicitly out of scope?
- Don't have anything in mind# AgencyDark MVP Implementation Plan

## Technology Recommendation

**Python with FastAPI is the best choice for your use case.** Here's why:

1. **Already implemented** - Your project already has a solid Python/FastAPI foundation
2. **Excellent for API wrappers** - FastAPI excels at building API wrappers with automatic documentation
3. **Async support** - Critical for handling multiple concurrent API calls to Inflow/OnlyFansAPI
4. **Real-time capabilities** - Socket.IO integration already in place for instant notifications
5. **Strong ecosystem** - Libraries for crypto payments, data analytics, and charting
6. **Performance** - FastAPI is one of the fastest Python frameworks, comparable to Node.js
7. **Type safety** - Pydantic models provide runtime validation crucial for financial data

## Phase 1: Core Infrastructure (Week 1-2)

### 1.1 Authentication & Authorization
- Implement JWT-based auth with role hierarchy (super_admin > agency_owner > agency_admin > model > chatter)
- Create user registration/login endpoints
- Implement tenant isolation middleware
- Add permission decorators for route protection

### 1.2 Database Schema
- Design multi-tenant schema with agency isolation
- Create models for: Users, Agencies, Models, Chatters, Fans, Content, Transactions
- Implement fan claiming system with locking mechanism
- Set up Alembic migrations

### 1.3 External API Integration Framework
- Create abstract base classes for API wrappers
- Implement retry logic and error handling
- Add request/response logging for debugging
- Create configuration management for API keys

## Phase 2: API Wrappers (Week 3-4)

### 2.1 Inflow API Wrapper
- Map all Inflow endpoints to internal routes
- Implement data transformation layers
- Add caching for frequently accessed data
- Create webhook handlers for real-time updates

### 2.2 OnlyFansAPI Wrapper
- Integrate all OnlyFansAPI endpoints
- Handle authentication flow
- Implement content management endpoints
- Add fan interaction endpoints

### 2.3 API Orchestration
- Create service layer to coordinate between APIs
- Implement conflict resolution (when both APIs provide same feature)
- Add data synchronization on login

## Phase 3: Real-time Features (Week 5)

### 3.1 Chat System
- Implement Socket.IO rooms for model-specific chats
- Create fan claiming mechanism with visual indicators
- Add notification system for unclaimed fans
- Implement message queuing for offline chatters

### 3.2 Live Analytics Updates
- Create WebSocket endpoints for real-time metrics
- Implement dashboard data push mechanisms
- Add event streaming for new subscribers/tips

## Phase 4: Analytics & Reporting (Week 6-7)

### 4.1 Data Collection
- Implement background jobs for metrics collection
- Create time-series data storage for charts
- Add data aggregation pipelines

### 4.2 Analytics Endpoints
- Film category popularity metrics
- Individual film performance tracking
- Subscriber growth charts (paying/non-paying)
- Revenue breakdown (subscriptions/tips/PPV)
- Per-fan revenue tracking (configurable up to 10 fans)

### 4.3 Chart Generation
- Create API endpoints for Recharts data format
- Implement date range filtering
- Add export functionality (CSV/JSON)

## Phase 5: Financial Features (Week 8-9)

### 5.1 Commission System
- Implement tiered commission calculation (70%/65%/60%)
- Create billing cycles and payout tracking
- Add commission override capabilities for super_admin

### 5.2 Cryptocurrency Integration
- Integrate crypto payment gateway (e.g., Coinbase Commerce, BitPay)
- Implement multi-currency wallet management
- Create transaction history and reconciliation

### 5.3 Invoice Generation
- Design invoice templates
- Implement PDF generation
- Add automated invoice scheduling

## Phase 6: White-Label Features (Week 10)

### 6.1 Theming System
- Implement theme configuration (light/dark)
- Add logo upload functionality
- Create theme preview system

### 6.2 Agency Customization
- Build agency profile management
- Implement model branding options
- Add customizable email templates

## Phase 7: Testing & Security (Week 11)

### 7.1 Security Hardening
- Implement rate limiting per tenant
- Add input validation and sanitization
- Create audit logging system
- Implement GDPR compliance features

### 7.2 Testing
- Write unit tests for all modules
- Create integration tests for API wrappers
- Add end-to-end tests for critical workflows
- Performance testing for concurrent users

## Phase 8: Deployment & Monitoring (Week 12)

### 8.1 Production Setup
- Configure production Docker environment
- Set up database backups and replication
- Implement zero-downtime deployment

### 8.2 Monitoring
- Configure Prometheus metrics
- Set up alerting for critical issues
- Create operational dashboards
- Implement error tracking (Sentry)

## Key Implementation Details

### Database Design Considerations
- Use PostgreSQL schemas for tenant isolation
- Implement soft deletes for data retention
- Add indexes for performance-critical queries
- Use JSONB for flexible analytics data

### API Design Patterns
- RESTful endpoints with consistent naming
- Pagination for all list endpoints
- Filtering and sorting capabilities
- Bulk operations where applicable

### Security Measures
- Row-level security for multi-tenancy
- API key rotation mechanism
- Encrypted storage for sensitive data
- Regular security audits

### Performance Optimizations
- Redis caching for frequently accessed data
- Background job processing for heavy operations
- Database connection pooling
- CDN for static assets

## Next Steps
1. Set up development environment
2. Create detailed API specifications
3. Design database schema diagrams
4. Set up CI/CD pipeline
5. Create project documentation

This plan provides a solid foundation for building AgencyDark as a scalable, secure, and feature-rich platform for OnlyFans agency management.