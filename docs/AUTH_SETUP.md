# Authentication Setup

## Overview
The application uses JWT-based authentication with a PostgreSQL backend for user storage.

## Default Admin Credentials
- **Email**: `admin@agency.com`
- **Password**: `admin123`
- **Role**: `super_admin`

## Backend Setup

### Running the Auth Backend
For development, you can use the simplified auth backend:

```bash
cd /path/to/agency-dark
python3 backend/auth_test.py
```

This will start the backend on `http://localhost:8000`

### Environment Variables
The backend requires these environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection URL (for caching)
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time (default: 30)

### API Endpoints
- `POST /api/v1/auth/login` - Login with email/password
- `GET /api/v1/auth/me` - Get current user info (requires JWT token)
- `POST /api/v1/auth/logout` - Logout (not implemented in test backend)
- `POST /api/v1/auth/refresh` - Refresh token (not implemented in test backend)

## Frontend Setup

The frontend expects the backend to be running on `http://localhost:8000`. You can override this by setting:
```bash
VITE_API_URL=http://your-backend-url/api/v1
```

## Creating Additional Users

To create new users, use the `create_admin.py` script as a template:

```python
python3 create_admin.py
```

Modify the script to create users with different roles and credentials as needed.

## Troubleshooting

### "Invalid email or password" error
- Ensure the user exists in the database
- Check that the password hash was created correctly
- Verify the backend is connected to the correct database

### 404 errors on auth endpoints
- Make sure the backend is running on port 8000
- Check that no other process is using port 8000
- Verify the backend logs for any startup errors

### Frontend can't connect to backend
- Check CORS settings in the backend
- Ensure the backend URL is correct in frontend config
- Check browser console for specific error messages