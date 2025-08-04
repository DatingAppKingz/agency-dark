# Phase 1: Security Implementation Tasks

## Quick Start Checklist

### Day 1-2: JWT Cookie Migration
```bash
# Backend tasks
1. [ ] Create `backend/core/auth/cookie_utils.py`
   - Implement set_auth_cookies()
   - Implement clear_auth_cookies()
   - Add cookie security settings

2. [ ] Update `backend/core/auth/jwt.py`
   - Modify create_access_token() to return cookie-compatible format
   - Update token validation to check cookies

3. [ ] Modify `backend/api/v1/endpoints/auth.py`
   - Update login endpoint to set cookies
   - Update logout to clear cookies
   - Modify refresh endpoint for cookie handling

# Frontend tasks
4. [ ] Update `frontend/src/services/auth/authService.ts`
   - Remove localStorage usage
   - Add credentials: 'include' to all requests
   - Update token refresh logic

5. [ ] Modify `frontend/src/services/api/apiClient.ts`
   - Remove Authorization header logic
   - Ensure credentials: 'include' is default
```

### Day 3-4: CSRF Protection
```bash
# Backend implementation
6. [ ] Install python-jose[csrf]: pip install python-jose[cryptography]

7. [ ] Create `backend/core/security/csrf.py`
   - Implement generate_csrf_token()
   - Create validate_csrf_token()
   - Add CSRF middleware class

8. [ ] Update `backend/main.py`
   - Add CSRF middleware
   - Configure CSRF exemptions

# Frontend implementation
9. [ ] Create `frontend/src/utils/csrf.ts`
   - Add getCsrfToken() function
   - Create csrf header utility

10. [ ] Update all forms and API calls
    - Add CSRF token to headers
    - Handle CSRF validation errors
```

### Day 5-7: Input Validation
```bash
# Create validation schemas
11. [ ] Create `backend/schemas/validators/`
    - user_validators.py
    - model_validators.py
    - chat_validators.py
    - financial_validators.py

12. [ ] Implement validation decorators
    - @validate_request_body
    - @validate_query_params
    - @validate_file_upload

13. [ ] Add to all endpoints:
    - POST /api/v1/users
    - PUT /api/v1/users/{id}
    - POST /api/v1/models
    - POST /api/v1/chat/messages
    - POST /api/v1/financial/payouts
```

### Day 8-10: API Security
```bash
# Rate limiting
14. [ ] Create `backend/core/security/rate_limit.py`
    - Implement Redis-based rate limiter
    - Create rate limit decorators

15. [ ] Apply rate limits:
    - Login: 5 attempts per 15 minutes
    - API: 100 requests per minute
    - File upload: 10 per hour

# API key improvements
16. [ ] Complete `backend/services/api_key_service.py`
    - Fix TODO: validate_api_key_format() line 307
    - Fix TODO: check_api_key_permissions() line 316
    - Fix TODO: rotate_api_key() line 325

# Audit logging
17. [ ] Create `backend/core/logging/audit.py`
    - Log all authentication attempts
    - Log all data modifications
    - Log all admin actions
```

### Day 11-14: Security Hardening
```bash
# Remove vulnerabilities
18. [ ] Search and remove hardcoded credentials
    grep -r "password123" --include="*.py" --include="*.ts"
    grep -r "secret" --include="*.env*"

19. [ ] Update all test files
    - Use environment variables
    - Create test fixtures

20. [ ] Security headers
    - Add Helmet.js to frontend
    - Configure security headers in backend

21. [ ] Final security scan
    - Run bandit for Python
    - Run npm audit
    - Check OWASP top 10
```

## Verification Checklist

### JWT Cookie Migration ✓
- [ ] No tokens in localStorage
- [ ] Cookies are httpOnly and secure
- [ ] Token refresh works with cookies
- [ ] Logout clears cookies properly

### CSRF Protection ✓
- [ ] All state-changing endpoints protected
- [ ] CSRF token generated on session start
- [ ] Forms include CSRF token
- [ ] API rejects requests without valid CSRF

### Input Validation ✓
- [ ] All endpoints have Pydantic validation
- [ ] File uploads are validated
- [ ] SQL injection impossible
- [ ] XSS inputs are sanitized

### API Security ✓
- [ ] Rate limiting active
- [ ] API keys properly validated
- [ ] Audit logs capturing events
- [ ] No hardcoded secrets

## Testing Commands

```bash
# Test JWT cookies
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  -c cookies.txt -v

# Test CSRF protection
curl -X POST http://localhost:8000/api/v1/users \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: invalid" \
  -d '{"name":"Test"}' \
  -b cookies.txt

# Test rate limiting
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}' &
done

# Security scan
cd backend && bandit -r . -f json -o bandit-report.json
cd frontend && npm audit --json > npm-audit.json
```

## Definition of Done

Phase 1 is complete when:
1. ✅ All authentication uses secure HTTP-only cookies
2. ✅ CSRF protection is active on all state-changing endpoints  
3. ✅ 100% of endpoints have input validation
4. ✅ API rate limiting is active and tested
5. ✅ Zero hardcoded credentials in codebase
6. ✅ Security scan shows no high/critical issues
7. ✅ All tests pass with new security measures
8. ✅ Documentation updated with security changes

---

Estimated Timeline: 14 days
Required Team: 2-3 developers
Priority: CRITICAL - Must complete before any other phases