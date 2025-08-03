# AgencyDark - Login Credentials

## Test User Credentials

The following test users have been created in the database:

### 1. Agency Admin
- **Email**: `test@example.com`
- **Password**: `password123`
- **Role**: Agency Admin
- **Description**: Main test user with agency admin privileges

### 2. Super Admin
- **Email**: `admin@example.com`
- **Password**: `admin123`
- **Role**: Super Admin
- **Description**: User with full system access

### 3. Model User
- **Email**: `model@example.com`
- **Password**: `model123`
- **Role**: Model
- **Description**: Content creator/model account

### 4. Chatter User
- **Email**: `chatter@example.com`
- **Password**: `chatter123`
- **Role**: Chatter
- **Description**: Chat support account

## System Access Points

- **Frontend Application**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Login Instructions

1. Go to http://localhost:3000 in your browser
2. You'll see the login page
3. Enter one of the credentials above
4. Click "Sign In"

## API Login Test

You can test the login via API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

## Known Issues

The backend API currently has some SQLAlchemy initialization warnings that may affect authentication. If login fails, check the backend logs for specific errors.

## Running Services

Make sure all services are running:
- PostgreSQL (port 5432)
- Redis (port 6379)  
- Backend API (port 8000)
- Frontend (port 3000)