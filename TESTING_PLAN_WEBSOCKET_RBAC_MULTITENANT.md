# Comprehensive Testing Plan: WebSocket, Multi-Tenant Isolation & RBAC

## Overview
This document outlines a comprehensive plan to test three critical aspects of the AgencyDark platform:
1. WebSocket connections for real-time features
2. Multi-tenant isolation between agencies
3. Full role-based access control (RBAC) permissions

## 1. WebSocket Connections Testing

### 1.1 Test Environment Setup
- **Backend WebSocket endpoint**: `ws://localhost:8000/ws`
- **Frontend WebSocket client**: Already configured in `.env.local`
- **Test users**: Use existing test accounts

### 1.2 WebSocket Features to Test

#### A. Real-time Notifications
- **Test Case 1**: User login notification
  - Login as agency owner
  - Open second browser, login as model
  - Verify owner receives real-time notification
  
- **Test Case 2**: New message notification
  - Send message from fan to model
  - Verify model receives instant notification
  - Verify assigned chatter receives notification

- **Test Case 3**: Financial transaction alerts
  - Create mock subscription purchase
  - Verify real-time revenue update
  - Verify commission calculation notification

#### B. Live Chat Features
- **Test Case 4**: Model-to-chatter handoff
  - Model receives message
  - Model assigns to chatter
  - Verify chatter receives real-time assignment
  
- **Test Case 5**: Typing indicators
  - Chatter starts typing response
  - Verify model sees typing indicator
  - Verify other chatters in agency see status

#### C. Dashboard Updates
- **Test Case 6**: Live metrics updates
  - Generate activity (messages, tips)
  - Verify dashboard updates without refresh
  - Check subscriber count updates

### 1.3 WebSocket Test Implementation
```python
# websocket_test.py
import asyncio
import websockets
import json

async def test_websocket_connection():
    # 1. Authenticate and get token
    # 2. Connect to WebSocket
    # 3. Send test messages
    # 4. Verify responses
    pass
```

### 1.4 Load Testing
- Test concurrent connections (10, 50, 100 users)
- Message throughput testing
- Connection stability over time
- Reconnection handling

## 2. Multi-Tenant Isolation Testing

### 2.1 Database Isolation Tests

#### A. Data Access Isolation
- **Test Case 1**: Cross-agency data access attempt
  ```sql
  -- Verify users can only see their agency's data
  -- Test with different user roles
  ```

- **Test Case 2**: Model profile isolation
  - Login as agency1 owner
  - Attempt to access agency2 model profiles
  - Verify 403/404 response

- **Test Case 3**: Financial data isolation
  - Each agency should only see own transactions
  - Commission rules specific to agency
  - Payout information isolated

#### B. API Endpoint Isolation
- **Test Case 4**: List endpoints with agency filtering
  ```python
  # Test all LIST endpoints return only agency-specific data
  GET /api/v1/models -> only agency models
  GET /api/v1/chatters -> only agency chatters
  GET /api/v1/financial/transactions -> only agency transactions
  ```

### 2.2 Multi-Tenant Test Scenarios

#### Scenario 1: Two Competing Agencies
1. Create second test agency "Competitor Agency"
2. Create users for second agency
3. Create model profiles for both agencies
4. Test complete isolation of:
   - User lists
   - Model profiles
   - Chat messages
   - Financial data
   - Analytics
   - White-label settings

#### Scenario 2: User Switching Agencies
1. Test user leaving one agency
2. Joining another agency
3. Verify historical data access
4. Verify new agency data access

### 2.3 Schema Isolation Testing (if using PostgreSQL schemas)
```sql
-- Test schema isolation
-- Each agency in separate schema
-- Verify cross-schema access denied
```

## 3. Role-Based Access Control (RBAC) Testing

### 3.1 Role Definitions & Permissions Matrix

| Feature/Endpoint | SUPER_ADMIN | AGENCY_OWNER | AGENCY_ADMIN | MODEL | CHATTER | AGENCY_MEMBER |
|-----------------|-------------|--------------|--------------|-------|---------|---------------|
| Platform Settings | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Agency Settings | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| User Management | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Model Profiles | ✅ | ✅ | ✅ | Own only | View | View |
| Chat Messages | ✅ | ✅ | ✅ | Own | Assigned | ❌ |
| Financial Data | ✅ | ✅ | View | Own | ❌ | ❌ |
| Analytics | ✅ | ✅ | ✅ | Own | Limited | ❌ |
| White-label | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

### 3.2 RBAC Test Cases

#### A. Super Admin Tests
```python
def test_super_admin_permissions():
    # Can access all agencies
    # Can modify platform settings
    # Can impersonate users
    # Can access all financial data
```

#### B. Agency Owner Tests
```python
def test_agency_owner_permissions():
    # Full control over own agency
    # Cannot access other agencies
    # Can manage all agency users
    # Full financial access for agency
```

#### C. Agency Admin Tests
```python
def test_agency_admin_permissions():
    # Can manage users except owner
    # Can configure agency settings
    # View-only financial access
    # Cannot delete agency
```

#### D. Model Tests
```python
def test_model_permissions():
    # Can only edit own profile
    # Can view own analytics
    # Can assign chatters
    # Cannot access other models' data
```

#### E. Chatter Tests
```python
def test_chatter_permissions():
    # Can only access assigned chats
    # Cannot modify model profiles
    # Cannot access financial data
    # Limited analytics access
```

### 3.3 Permission Boundary Testing

#### Test Case: Privilege Escalation Attempts
1. Try to modify role via API
2. Attempt to access higher-privilege endpoints
3. Test JWT token manipulation
4. Verify all attempts fail

#### Test Case: Data Leakage
1. Check API responses for excess data
2. Verify filtered fields by role
3. Test GraphQL query depth (if applicable)

## 4. Implementation Plan

### Phase 1: Setup (Day 1)
1. Create test data generator script
2. Set up second test agency
3. Create WebSocket test client
4. Prepare RBAC test matrix

### Phase 2: WebSocket Testing (Day 2-3)
1. Implement WebSocket test suite
2. Test all real-time features
3. Load test WebSocket connections
4. Document performance metrics

### Phase 3: Multi-Tenant Testing (Day 4-5)
1. Create isolation test suite
2. Test all endpoints for isolation
3. Verify database-level isolation
4. Test edge cases

### Phase 4: RBAC Testing (Day 6-7)
1. Implement permission test suite
2. Test all role combinations
3. Security penetration testing
4. Document vulnerabilities

### Phase 5: Integration Testing (Day 8)
1. Combined scenario testing
2. Load test with multiple agencies
3. Performance benchmarking
4. Final report

## 5. Test Automation

### 5.1 Test Framework Structure
```
tests/
├── websocket/
│   ├── test_notifications.py
│   ├── test_chat.py
│   └── test_dashboard.py
├── multitenant/
│   ├── test_isolation.py
│   ├── test_data_access.py
│   └── test_schemas.py
└── rbac/
    ├── test_super_admin.py
    ├── test_agency_owner.py
    ├── test_agency_admin.py
    ├── test_model.py
    └── test_chatter.py
```

### 5.2 CI/CD Integration
```yaml
# .github/workflows/security-tests.yml
name: Security & Isolation Tests
on: [push, pull_request]
jobs:
  test:
    steps:
      - name: Run WebSocket tests
      - name: Run multi-tenant tests
      - name: Run RBAC tests
```

## 6. Success Criteria

### WebSocket Success Metrics
- 100% message delivery rate
- <100ms latency for notifications
- Support 1000+ concurrent connections
- Automatic reconnection working

### Multi-Tenant Success Metrics
- Zero data leakage between agencies
- All endpoints properly filtered
- Database queries include agency filter
- Performance not degraded by filtering

### RBAC Success Metrics
- 100% endpoint coverage with tests
- No privilege escalation possible
- Clear permission denied messages
- Audit trail for all actions

## 7. Tools & Resources

### Testing Tools
- **WebSocket**: `websocket-client`, `pytest-asyncio`
- **API Testing**: `pytest`, `requests`, `httpx`
- **Load Testing**: `locust`, `k6`
- **Security**: `bandit`, `safety`, custom scripts

### Monitoring
- Application logs
- Database query logs
- WebSocket connection metrics
- Performance profiling

## 8. Risk Mitigation

### Identified Risks
1. **WebSocket scalability**: May need Redis pub/sub
2. **Query performance**: Index on agency_id critical
3. **Token security**: JWT expiration and refresh
4. **Audit compliance**: Log all access attempts

### Mitigation Strategies
1. Implement caching layer
2. Database query optimization
3. Regular security audits
4. Comprehensive logging

## 9. Deliverables

1. **Test Suite**: Automated tests for all scenarios
2. **Test Report**: Results, metrics, and findings
3. **Security Report**: Vulnerabilities and fixes
4. **Performance Report**: Benchmarks and optimization recommendations
5. **Documentation**: Updated with security best practices

## 10. Timeline

**Total Duration**: 8 working days

- Days 1-2: Setup and WebSocket testing
- Days 3-4: Multi-tenant isolation testing
- Days 5-6: RBAC comprehensive testing
- Days 7-8: Integration testing and reporting

This comprehensive testing plan ensures the AgencyDark platform meets enterprise security and isolation requirements while maintaining high performance and user experience.