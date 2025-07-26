# Debug Instructions for AgencyDark

## Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd /Users/mariuszbudzisz/SourceCode/agency-dark/backend
   ```

2. **Activate virtual environment:**
   ```bash
   source venv/bin/activate
   ```

3. **Start Redis (required):**
   ```bash
   brew services start redis
   ```

4. **Run backend server:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   
   Backend will be available at: `http://localhost:8000`

## Frontend Setup

1. **Navigate to frontend directory (new terminal):**
   ```bash
   cd /Users/mariuszbudzisz/SourceCode/agency-dark/frontend
   ```

2. **Run frontend:**
   ```bash
   npm run dev
   ```
   
   Frontend will be available at: `http://localhost:5173`

## Debugging the Integration

1. **Open browser DevTools (F12)**
   - Console tab: Shows API request/response logs
   - Network tab: Shows all HTTP requests

2. **Test API Connection:**
   - Navigate to: `http://localhost:5173/dashboard/api-test`
   - Enter test credentials
   - Click "Run All Tests"

3. **What to look for in console:**
   - 🚀 = Outgoing API request
   - ✅ = Successful response
   - ❌ = Error response

## Common Issues

- **CORS errors**: Backend is configured to allow frontend origin
- **Connection refused**: Make sure backend is running on port 8000
- **401 Unauthorized**: Check credentials or token issues
- **500 Internal Server Error**: Check backend console for detailed errors

## Test Endpoints

1. **Health check:**
   ```bash
   curl http://localhost:8000/
   ```

2. **Login test:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"password123"}'
   ```

## Environment Variables

Frontend (.env):
```
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=http://localhost:8000
```

Backend (.env):
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000
```