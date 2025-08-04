# Test Update Requirements

## Overview

Following the implementation of cookie-based authentication, CSRF protection, and input validation, many tests need to be updated to reflect these security improvements.

## Test Categories Requiring Updates

### 1. Authentication Tests

**Files Affected**:
- `tests/unit/services/authService.test.ts`
- `tests/unit/store/authStore.test.ts`
- `tests/integration/auth.integration.test.tsx`
- `tests/integration/auth-flow.test.tsx`
- `tests/integration/simple-auth.test.tsx`
- `tests/unit/hooks/useAuth.test.ts`

**Required Changes**:
- Remove all `localStorage.getItem('auth_token')` assertions
- Remove all `localStorage.setItem('auth_token', ...)` setup code
- Update tests to verify auth state through the auth store instead
- Mock cookie-based responses from auth endpoints
- Add `withCredentials: true` to all auth-related API calls

**Example Update**:
```typescript
// Before
expect(localStorage.getItem('auth_token')).toBe('mock-token');

// After
const authState = useAuthStore.getState();
expect(authState.isAuthenticated).toBe(true);
```

### 2. API Client Tests

**Files Affected**:
- `tests/unit/services/api/client.test.ts`
- Any test that mocks API calls

**Required Changes**:
- Update to include CSRF token in state-changing requests
- Ensure `withCredentials: true` is set
- Mock CSRF token retrieval

### 3. Protected Route Tests

**Files Affected**:
- Any test that checks authentication status

**Required Changes**:
- Update to use auth store state instead of localStorage
- Mock authenticated state through the store

### 4. Test Utilities

**Files Affected**:
- `tests/utils/enhanced-test-utils.tsx`
- `tests/utils/test-utils.tsx`

**Required Changes**:
- Remove localStorage setup for auth tokens
- Add helper to set authenticated state in auth store
- Add CSRF token mocking utilities

## New Test Requirements

### 1. CSRF Protection Tests

Create new tests to verify:
- CSRF tokens are included in POST/PUT/DELETE requests
- CSRF token refresh works correctly
- Requests fail without valid CSRF token

### 2. Input Validation Tests

Create new tests to verify:
- XSS attempts are blocked
- SQL injection patterns are rejected
- Invalid email formats are caught
- Password complexity is enforced

### 3. Cookie Security Tests

Create new tests to verify:
- Cookies are set with correct security flags
- Token refresh via cookies works
- Logout clears cookies properly

## Test Utilities to Add

### 1. Auth Test Helper
```typescript
export const setupAuthenticatedUser = (user?: Partial<User>) => {
  const mockUser = createMockUser(user);
  useAuthStore.getState().setAuth({
    user: mockUser,
    accessToken: 'mock-access-token',
    refreshToken: 'mock-refresh-token',
  });
  return mockUser;
};
```

### 2. CSRF Test Helper
```typescript
export const mockCSRFToken = () => {
  server.use(
    http.get('/api/v1/auth/csrf-token', () => {
      return HttpResponse.json({ csrf_token: 'mock-csrf-token' });
    })
  );
};
```

### 3. Validation Error Helper
```typescript
export const expectValidationError = (field: string, message: string) => {
  return {
    detail: {
      field,
      error: message,
    },
  };
};
```

## Priority Updates

1. **High Priority**: Auth service and store tests (core functionality)
2. **Medium Priority**: Integration tests (user flows)
3. **Low Priority**: Component tests that use auth

## Testing Strategy

1. **Unit Tests**: Focus on individual function behavior
2. **Integration Tests**: Test complete user flows with mocked backend
3. **E2E Tests**: Test with real backend (requires backend running with test data)

## Common Patterns to Update

### localStorage Access
```typescript
// Remove these patterns:
localStorage.setItem('auth_token', token);
localStorage.getItem('auth_token');
localStorage.removeItem('auth_token');

// Replace with:
// Tokens are now in httpOnly cookies - use auth store state
```

### API Calls
```typescript
// Update all auth-related API calls:
axios.post('/api/v1/auth/login', data, {
  withCredentials: true, // Add this
});
```

### Protected Routes
```typescript
// Instead of checking localStorage:
if (localStorage.getItem('auth_token')) { ... }

// Use auth store:
if (useAuthStore.getState().isAuthenticated) { ... }
```

## Running Updated Tests

```bash
# Run all tests
npm test

# Run specific test file
npm test tests/unit/services/authService.test.ts

# Run with coverage
npm test -- --coverage

# Run in watch mode
npm test -- --watch
```

## Notes

- httpOnly cookies cannot be accessed via JavaScript, so tests cannot directly verify their content
- Focus on testing application state and behavior rather than implementation details
- Consider adding backend integration tests to verify cookie behavior