# Security_v2 Deployment Guide

## Prerequisites

Before deploying the AgencyDark platform with security_v2, ensure you have:

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Node.js 18+
- npm or yarn

## Backend Deployment

### 1. Environment Setup

Create a `.env` file with the following configuration:

```bash
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/agencydark

# Redis
REDIS_URL=redis://localhost:6379

# JWT Configuration
JWT_SECRET_KEY=generate-a-secure-random-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Security Features
ENABLE_RBAC=true
ENABLE_RATE_LIMITING=true
ENABLE_SESSION_MANAGEMENT=true
ENABLE_AUDIT_LOGGING=true

# Password Policy
PASSWORD_MIN_LENGTH=8
PASSWORD_HASH_ROUNDS=12

# CORS
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3002"]

# Application
DEBUG=false
PORT=8000
```

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Database Setup

```bash
# Create database
createdb agencydark

# Run migrations (if using Alembic)
alembic upgrade head

# Or create tables directly
python -c "from core.database import create_tables; import asyncio; asyncio.run(create_tables())"
```

### 4. Initialize Admin User

```bash
python hash_passwords.py
```

This will hash the password for the admin user (admin@agency.com).

### 5. Start Backend Services

#### Development
```bash
# Use the simplified version for testing
python main_v2_simple.py

# Or use the full version with all middleware
python main_clean.py
```

#### Production
```bash
# Using Uvicorn directly
uvicorn main_clean:app --host 0.0.0.0 --port 8000 --workers 4

# Or using Gunicorn with Uvicorn workers
gunicorn main_clean:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Frontend Deployment

### 1. Environment Configuration

Create `frontend/.env.local`:

```bash
# API Configuration
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws

# Features
VITE_USE_SECURITY_V2=true

# App Info
VITE_APP_NAME=AgencyDark
VITE_APP_VERSION=2.0.0
```

### 2. Install Dependencies

```bash
cd frontend
npm install
```

### 3. Build Frontend

#### Development
```bash
npm run dev
```

#### Production Build
```bash
npm run build
npm run preview  # To test the production build
```

## Docker Deployment (Optional)

### Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main_clean:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:18-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Docker Compose

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: agencydark
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/agencydark
      REDIS_URL: redis://redis:6379
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
```

## Production Considerations

### 1. Security

- **Generate secure JWT secret**: Use a cryptographically secure random key
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- **Use HTTPS**: Always use HTTPS in production
- **Update CORS origins**: Set specific allowed origins, not wildcards
- **Enable all security features**: Ensure RBAC, rate limiting, and audit logging are enabled

### 2. Performance

- **Database Indexing**: Add indexes for frequently queried fields
  ```sql
  CREATE INDEX idx_users_email ON users(email);
  CREATE INDEX idx_users_role ON users(role);
  ```

- **Redis Configuration**: Configure Redis for persistence
  ```
  save 900 1
  save 300 10
  save 60 10000
  ```

- **Connection Pooling**: Configure database connection pools appropriately

### 3. Monitoring

- **Health Checks**: Monitor the `/health` endpoint
- **Logging**: Configure structured logging to a centralized system
- **Metrics**: Track authentication failures, token refreshes, and API usage

### 4. Backup

- **Database Backups**: Regular PostgreSQL backups
  ```bash
  pg_dump agencydark > backup_$(date +%Y%m%d).sql
  ```

- **Redis Persistence**: Enable AOF or RDB persistence
- **Configuration Backups**: Version control all configuration files

## Verification Steps

After deployment, verify the system is working:

### 1. Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "security": "security_v2"
}
```

### 2. Test Authentication
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@agency.com", "password": "admin123"}'
```

### 3. Test Frontend
- Navigate to http://localhost:3000 (or your configured port)
- Try logging in with admin@agency.com / admin123
- Verify dashboard loads after authentication

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check DATABASE_URL is correct
   - Ensure PostgreSQL is running
   - Verify database exists and user has permissions

2. **Redis Connection Failed**
   - Check REDIS_URL is correct
   - Ensure Redis is running
   - Test with `redis-cli ping`

3. **Frontend Can't Connect to Backend**
   - Check VITE_API_URL is correct
   - Ensure backend is running on expected port
   - Check CORS configuration

4. **Authentication Failures**
   - Verify JWT_SECRET_KEY is set
   - Check passwords are hashed in database
   - Ensure bcrypt is installed

### Debug Mode

For troubleshooting, enable debug mode:

```bash
DEBUG=true python main_v2_simple.py
```

This will provide detailed error messages and logging.

## Rollback Procedure

If issues occur, you can rollback to the previous version:

1. **Stop current services**
2. **Restore database backup** (if schema changed)
3. **Switch to previous code version**
4. **Restart services**

The old security code is archived in `backend/archive/old_security_backup_phase7/` if needed for reference.

## Support

For deployment issues:
- Check logs in `backend_v2_simple.log`
- Review test results with `python test_security_v2_complete.py`
- Consult the API documentation in `SECURITY_V2_API_DOCUMENTATION.md`