# AgencyDark Setup Guide

This guide provides instructions for setting up the AgencyDark platform for development and production environments.

## Prerequisites

- Python 3.11+ (3.13 recommended)
- Node.js 18+ and npm/yarn
- PostgreSQL 14+
- Redis 6+
- Docker and Docker Compose (optional)

## Quick Start

### Option 1: Docker Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/agency-dark.git
cd agency-dark

# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Local Development Setup

#### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Required environment variables:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agencydark
# REDIS_URL=redis://localhost:6379/0
# SECRET_KEY=<generate-secure-key>
# ENCRYPTION_KEY=<generate-with-fernet>

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the development server
npm run dev

# Access at http://localhost:5173
```

## Database Setup

1. Create PostgreSQL database:
```sql
CREATE DATABASE agencydark;
CREATE USER agencydark_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE agencydark TO agencydark_user;
```

2. Run migrations:
```bash
cd backend
alembic upgrade head
```

## Redis Setup

Install and start Redis:
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

## Environment Configuration

### Backend (.env)
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agencydark

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-fernet-key-here

# API Keys (optional)
INFLOW_API_KEY=your-inflow-api-key
ONLYFANS_API_KEY=your-onlyfans-api-key

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
VITE_WEBSOCKET_URL=ws://localhost:8000
```

## Verification

1. Check backend health:
```bash
curl http://localhost:8000/health
```

2. Access API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

3. Test frontend connection:
- Open http://localhost:5173
- Check browser console for any errors

## Common Issues

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000
# Kill the process
kill -9 <PID>
```

### Database Connection Error
- Verify PostgreSQL is running
- Check DATABASE_URL format
- Ensure database exists and user has permissions

### Redis Connection Error
- Verify Redis is running: `redis-cli ping`
- Check REDIS_URL format
- For macOS: Disable socket keepalive if needed

### Migration Errors
- Drop and recreate database if needed
- Check for conflicting migrations
- Run `alembic history` to see migration status

## Production Deployment

See [Deployment Guide](guides/DEPLOYMENT.md) for production setup instructions.

## Development Tools

- API Documentation: http://localhost:8000/docs
- Database Admin: Use pgAdmin or TablePlus
- Redis Monitoring: Use RedisInsight or redis-cli

## Next Steps

1. Create a superuser account
2. Configure platform integrations
3. Set up monitoring and logging
4. Review security settings

For more detailed information, see:
- [API Reference](API_REFERENCE.md)
- [Database Setup Guide](guides/DATABASE_SETUP_GUIDE.md)
- [Error Handling Guide](guides/ERROR_HANDLING_GUIDE.md)