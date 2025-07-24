# AgencyDark Local Setup Guide

## Prerequisites
- Docker Desktop installed and running
- Git
- At least 4GB of free RAM

## Quick Start with Docker

1. **Clone and navigate to the project** (if not already done):
```bash
cd /Users/mariuszbudzisz/SourceCode/agency-dark
```

2. **Create environment file**:
```bash
cp .env.example .env
```

3. **Start all services**:
```bash
docker-compose up -d
```

This will start:
- PostgreSQL database (port 5433)
- Redis cache (port 6379)
- Backend API (port 8000)

4. **Check if services are running**:
```bash
docker-compose ps
```

5. **View logs**:
```bash
docker-compose logs -f backend
```

6. **Access the application**:
- API Documentation: http://localhost:8000/api/docs
- Health Check: http://localhost:8000/health
- API Base URL: http://localhost:8000

## First Time Setup

1. **Create a test agency and admin user**:
```bash
# Access the backend container
docker-compose exec backend bash

# Run Python shell
python
```

Then in Python:
```python
import asyncio
from backend.core.database import create_tables, get_db
from backend.modules.auth.domain.models import Agency, User, UserRole
from backend.core.security import get_password_hash
import uuid

async def setup():
    # Create tables
    await create_tables()
    
    # Create test agency
    async for db in get_db():
        agency = Agency(
            id=uuid.uuid4(),
            name="Test Agency",
            domain="test-agency"
        )
        db.add(agency)
        
        # Create admin user
        admin = User(
            id=uuid.uuid4(),
            email="admin@test.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            agency_id=agency.id,
            role=UserRole.AGENCY_ADMIN,
            is_active=True,
            is_verified=True
        )
        db.add(admin)
        
        await db.commit()
        print(f"Created agency: {agency.name}")
        print(f"Created admin user: admin@test.com / admin123")
        break

asyncio.run(setup())
```

Exit Python shell with `Ctrl+D` and then `exit` to leave container.

## Testing the API

1. **Login to get access token**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

2. **Use the token to access protected endpoints**:
```bash
TOKEN="<your-access-token>"
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## Optional: Development Tools

To use pgAdmin and Redis Commander:
```bash
docker-compose --profile tools up -d
```

Access:
- pgAdmin: http://localhost:5050 (admin@agencydark.com / admin)
- Redis Commander: http://localhost:8081

## Stopping the Application

```bash
docker-compose down
```

To also remove volumes (database data):
```bash
docker-compose down -v
```

## Troubleshooting

1. **Port already in use**:
```bash
# Check what's using the port
lsof -i :8000
# Kill the process if needed
kill -9 <PID>
```

2. **Database connection issues**:
```bash
# Check PostgreSQL logs
docker-compose logs postgres
```

3. **Reset everything**:
```bash
docker-compose down -v
docker-compose up -d --build
```
EOF < /dev/null