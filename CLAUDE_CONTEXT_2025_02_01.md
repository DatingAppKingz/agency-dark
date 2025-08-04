# Claude Context for February 1, 2025

## Project Overview
Agency Dark - A multi-tenant SaaS platform for talent agencies with model management, chat, media library, and financial features.

## Yesterday's Progress (Jan 31, 2025)

### Test Infrastructure Overhaul
- Fixed 241 test failures, bringing passing tests from 235 to 476
- Discovered and fixed 284 additional tests that were being skipped due to import errors
- Total test count increased from 285 to 569 tests
- Test pass rate improved from 82% to 84%

### Key Technical Fixes
1. **Import Path Migration**: Converted all test imports from `@/__tests__` to `@/tests`
2. **Mock Infrastructure**: Created comprehensive MUI icon mocks and fixed localStorage/sessionStorage
3. **API Integration**: Updated financial service tests to match actual backend API
4. **Vitest Migration**: Converted remaining Jest references to Vitest
5. **DOM Polyfills**: Added missing browser APIs (pointer capture methods)

## Current Project State

### ✅ Working
- Frontend development server (Vite)
- Backend API server (FastAPI) 
- Authentication system with JWT
- PostgreSQL database with migrations
- Redis for caching/sessions
- 476 out of 569 tests passing

### ⚠️ Issues Remaining
- 93 failing tests (mostly UI component edge cases)
- Some async timing issues in complex components
- Radix UI component attribute expectations
- WebSocket integration tests need verification

## Today's Priorities

### 1. Complete Test Suite Fixes (High Priority)
```bash
# Start here - fix remaining 93 tests
cd frontend
npm test -- --run

# Focus areas:
# - Toaster component (needs act() wrappers)
# - MessageThread async issues  
# - UI component attribute tests
```

### 2. Integration Testing (Medium Priority)
- Verify frontend-backend API integration
- Test authentication flow end-to-end
- Ensure media upload works
- Test WebSocket connections

### 3. Documentation (Low Priority)
- Update setup instructions
- Document test procedures
- Create troubleshooting guide

## Technical Context

### Project Structure
```
agency-dark/
├── backend/          # FastAPI backend
│   ├── api/         # API endpoints
│   ├── core/        # Core utilities
│   ├── models/      # SQLAlchemy models
│   └── services/    # Business logic
├── frontend/        # React + Vite frontend
│   ├── src/         # Source code
│   └── tests/       # Test files (NEW location)
└── docs/            # Documentation
```

### Key Technologies
- **Frontend**: React, TypeScript, Vite, MUI, Zustand, React Query
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, Redis
- **Testing**: Vitest, React Testing Library, MSW
- **Auth**: JWT tokens, role-based access control

### Environment Setup
```bash
# Backend
export DATABASE_URL="postgresql://mariuszbudzisz@localhost/agencydark_dev"
export REDIS_URL="redis://localhost:6379"
export DISABLE_ML="true"  # Important for tests
export JWT_SECRET_KEY="your-secret-key-here"

# Start backend
cd backend
python main_auth.py  # Use this instead of main.py

# Frontend
cd frontend
npm install
npm run dev
```

### Testing Commands
```bash
# Run all tests
npm test -- --run

# Run specific test file
npm test tests/unit/components/common/Toaster.test.tsx -- --run

# Run with coverage
npm test -- --coverage

# Watch mode
npm test
```

### Important Files to Know
- `/frontend/tests/utils/setup.ts` - Global test setup with mocks
- `/frontend/tests/utils/enhanced-test-utils.tsx` - Custom render utilities
- `/frontend/tests/utils/mui-icon-mocks.tsx` - MUI icon mocks
- `/backend/main_auth.py` - Main backend entry point with auth
- `/docs/development-logs/` - Daily progress logs

### Git Information
- Branch: main
- Remote: https://github.com/mariuszbyahoo/agency-dark.git
- New location: https://github.com/DatingAppKingz/agency-dark.git

## Quick Wins for Today
1. Fix Toaster tests - wrap state updates in act()
2. Update MessageThread tests - fix async timing
3. Skip or adjust Radix UI attribute tests
4. Run full integration test of auth flow
5. Document any new issues found

## Notes
- Always use `vi.fn()` not `jest.fn()` (we use Vitest)
- Mock LanguageProvider to avoid translation loading
- Use `DISABLE_ML=true` for backend tests
- The financial API uses `financialApi` not `financialService`
- Toaster uses Zustand, not react-hot-toast

This context should help you continue where we left off. Focus on getting the test suite to 100% passing first, then move on to integration testing.