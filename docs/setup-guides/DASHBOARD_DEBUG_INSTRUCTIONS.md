# Dashboard Debug Instructions

## The Issue
The dashboard is showing zeros even though the backend APIs are returning data correctly.

## What I've Done

### 1. Verified Backend is Working
- Created test script that confirms all analytics endpoints return data
- Backend returns mock data mixed with real user counts
- Authentication is working correctly

### 2. Added Debug Tools
I've created several debug tools to help identify the issue:

#### A. Debug Pages
1. **Dashboard Debug Page**: http://localhost:3000/dashboard/dashboard-debug
   - Shows current user info
   - Shows React Query hook results
   - Has button to test direct API calls
   - All console logs visible in browser DevTools

2. **Analytics Debug Page**: http://localhost:3000/dashboard/debug-analytics
   - Tests analytics service directly
   - Shows auth token status
   - Direct API call testing

3. **HTML Test Page**: http://localhost:3000/test-analytics.html
   - Plain HTML/JS test (no React)
   - Tests login and analytics endpoints
   - Shows exactly what the browser sees

#### B. Added Console Logging
Open your browser's Developer Console (F12) to see:
- 🚀 API Request logs (shows all API calls)
- ✅ API Response logs (shows all responses)
- 📊 Dashboard data logs
- 🎣 Hook execution logs

## How to Debug

1. **Open Browser DevTools** (F12)
   - Go to Console tab
   - Clear console
   - Navigate to http://localhost:3000/dashboard

2. **Check Console for:**
   - Are API calls being made?
   - What responses are coming back?
   - Any errors?

3. **Visit Debug Pages:**
   - http://localhost:3000/dashboard/dashboard-debug
   - Click "Test Direct API Call" button
   - Check what data is displayed

4. **Try the HTML Test:**
   - http://localhost:3000/test-analytics.html
   - Click Login, then Test Dashboard Stats
   - This bypasses React entirely

## Possible Issues

1. **Caching**: React Query might be caching old empty data
   - Try hard refresh (Ctrl+Shift+R)
   - Clear localStorage: `localStorage.clear()` in console

2. **Auth Token**: Token might be expired or invalid
   - Check localStorage: `localStorage.getItem('access_token')`
   - Try logging out and back in

3. **Wrong User Role**: User might not have permission
   - Check user object in debug page
   - Verify role is AGENCY_OWNER or similar

## Next Steps

Please:
1. Open browser console (F12)
2. Navigate to the dashboard
3. Take a screenshot of the console logs
4. Visit http://localhost:3000/dashboard/dashboard-debug
5. Click "Test Direct API Call"
6. Share what you see

This will help identify exactly where the data flow is breaking.