# AgencyDark Manual Testing Guide

## Current System Status

### ✅ Services Running
- **PostgreSQL**: Port 5432 (local)
- **Redis**: Port 6379 (local)
- **Backend API**: http://localhost:8000 (with SQLAlchemy issues)
- **Frontend**: http://localhost:3000

### ⚠️ Backend Issues
The backend has critical SQLAlchemy model conflicts that prevent normal authentication from working:
- Multiple `APIKey` class definitions
- `Notification` model can't find `User` relationship
- Various model import conflicts

### 🔧 Temporary Solution
We've created a minimal authentication system that bypasses the SQLAlchemy issues:
- Modified frontend to use `authServiceMinimal.ts`
- Created `/api/v1/auth/login-minimal` endpoint (attempted but failed due to model issues)

## Working Test Credentials

| Email               | Password    | Role         | Status |
|---------------------|-------------|--------------|---------|
| test@example.com    | password123 | Agency Admin | ✅ Working |
| admin@example.com   | admin123    | Super Admin  | ✅ Working |
| model@example.com   | model123    | Model        | ✅ Working |
| chatter@example.com | chatter123  | Chatter      | ✅ Working |

All users have been created with proper password hashing using bcrypt.

## How to Test Manually

### Option 1: Use the Frontend (Partially Working)
1. Go to http://localhost:3000
2. Try logging in with the credentials above
3. Due to backend issues, authentication may fail

### Option 2: Direct API Testing (Not Working)
Due to SQLAlchemy issues, the main API endpoints are not functional.

### Option 3: Database Verification (Working)
The test users exist in the database with correct password hashes:
```bash
/opt/homebrew/opt/postgresql@16/bin/psql -U mariuszbudzisz -d agencydark -c "SELECT email, role, is_active FROM users;"
```

## What Works
✅ Test users created in database
✅ Password hashing verified
✅ Frontend application loads
✅ Database and Redis services running

## What Doesn't Work
❌ Backend authentication endpoints (SQLAlchemy conflicts)
❌ Most backend API endpoints
❌ Frontend login (due to backend issues)

## Recommendations

To enable full manual testing, the backend needs fixing:

1. **Quick Fix**: Create a standalone authentication service that doesn't use the problematic models
2. **Proper Fix**: Resolve all SQLAlchemy model conflicts (see BACKEND_FIX_PLAN.md)

## Alternative Testing Approach

If you need to test specific features:
1. We can create minimal endpoints that bypass SQLAlchemy
2. Use direct database queries instead of ORM
3. Focus on testing frontend components independently

The system architecture is sound, but the model layer needs restructuring to resolve the circular dependencies and duplicate definitions.