# Getting Started with AgencyDark

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL client (optional, for direct DB access)

## Quick Start

1. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd AgencyDark
   ./setup.sh
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start services**
   ```bash
   docker-compose up
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs

## Development Workflow

### Backend Development

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

### Frontend Development

```bash
cd frontend
npm run dev
```

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## Project Structure

- `backend/` - FastAPI application
  - `core/` - Core functionality (config, database, security)
  - `modules/` - Business logic modules
  - `api/` - API endpoints
- `frontend/` - Next.js application
- `docker/` - Docker configurations
- `docs/` - Documentation

## Default Credentials

- Super Admin: `admin@agencydark.com` / `admin123`

## Multi-tenancy

The application uses PostgreSQL Row-Level Security for automatic data isolation:

1. Each request must include the agency context
2. Database queries are automatically filtered by agency_id
3. Cache keys are prefixed with agency_id
4. WebSocket rooms are agency-specific

## Next Steps

1. Create your first agency
2. Add users to the agency
3. Configure Inflow integration
4. Set up white-label domain