# AgencyDark - Working Setup Guide

## ✅ Current Status

Both frontend and backend are now running successfully with proper CORS configuration.

### Running Services
- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000
- **Redis**: localhost:6379

### Fixed Issues
1. ✅ CORS now allows http://localhost:3000
2. ✅ Fixed `process is not defined` error in pushNotifications.ts
3. ✅ Both servers are running and accessible

## 🔍 How to Test

1. **Open Browser DevTools** (F12)
   - Go to Console tab to see API logs
   - Go to Network tab to see requests

2. **Navigate to API Test Page**
   ```
   http://localhost:3000/dashboard/api-test
   ```

3. **What You'll See in Console**
   - 🚀 = Outgoing API requests
   - ✅ = Successful responses
   - ❌ = Error responses

## ⚠️ Current Limitations

The backend login endpoint returns 500 error because:
- Database connection to Supabase is failing
- No test users exist in the database

To see the API integration working (even with errors), check the browser console - you'll see the requests being made with proper CORS headers.

## 📊 API Request Flow

1. Frontend makes request to `http://localhost:8000/api/v1/auth/me`
2. CORS headers are properly set (Origin: http://localhost:3000)
3. Backend responds (currently with 403 because no auth token)
4. Console shows the request/response cycle

## 🛠️ Next Steps

To fully test authentication:
1. Fix the database connection in backend/.env
2. Run `create_test_user.py` to add test credentials
3. Use the API test page to verify login works

The infrastructure is now properly connected and configured!