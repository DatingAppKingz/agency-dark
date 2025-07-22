# Phase 1: Project Initialization and Foundation

## Date: July 22, 2025

## Project Overview

AgencyDark is a white-label SaaS portal for OnlyFans marketing agencies. The project is designed to start as a wrapper around Inflow's functionality and gradually evolve into a standalone platform.

## Key Assumptions and Decisions

### Architecture
1. **Modular Monolith Pattern** - Chosen for easier initial development and maintenance compared to microservices
2. **Multi-tenancy via PostgreSQL RLS** - Row-Level Security for automatic data isolation at the database level
3. **No Kubernetes** - Using Docker Compose/Swarm for simpler operations on Hetzner Cloud
4. **API-First Design** - FastAPI backend with separate React frontend for flexibility

### Technology Stack
- **Backend**: FastAPI (Python 3.11) with async/await patterns
- **Frontend**: Next.js 15 with TypeScript and Material-UI (planned)
- **Database**: PostgreSQL 16 with Row-Level Security
- **Cache**: Redis for session management and caching
- **Real-time**: Socket.IO (planned)
- **Reverse Proxy**: Caddy for automatic HTTPS
- **Infrastructure**: Docker Compose for development, Docker Swarm for production

### Security Considerations
1. JWT authentication with short-lived access tokens (15-30 minutes)
2. Refresh tokens stored in secure sessions table
3. All passwords hashed with bcrypt
4. Multi-tenant isolation enforced at database level
5. CORS configured for frontend-backend communication

## Work Completed in Phase 1

### 1. Project Structure Creation
```
agency-dark/
├── backend/
│   ├── core/
│   │   ├── domain/
│   │   ├── application/
│   │   └── infrastructure/
│   ├── modules/
│   │   ├── inflow_wrapper/
│   │   ├── analytics/
│   │   ├── user_management/
│   │   ├── billing/
│   │   └── notifications/
│   ├── api/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── store/
│   │   └── utils/
├── docker/
├── claude-history/
└── docs/
```

### 2. Backend Implementation

#### Core Components Created:
- **main.py** - FastAPI application with lifespan management
- **core/config.py** - Settings management with Pydantic
- **core/database.py** - SQLAlchemy async engine with connection pooling
- **core/redis.py** - Redis client wrapper for caching
- **core/security.py** - JWT token creation and password hashing utilities
- **core/middleware/** - Tenant isolation and logging middleware

#### Domain Models:
- **Agency** - Top-level tenant model
- **User** - User accounts with role-based permissions
- **Session** - Refresh token management
- **Notification** - In-app notifications
- **AuditLog** - Activity tracking

#### Database Schema:
- PostgreSQL with UUID primary keys
- Custom ENUM types for roles and statuses
- Row-Level Security policies for multi-tenancy
- Automatic timestamp triggers
- Comprehensive indexes for performance

### 3. Frontend Setup
- Next.js 15 with App Router
- TypeScript configuration
- Basic project structure
- Package.json with required dependencies

### 4. Infrastructure

#### Docker Configuration:
- Development docker-compose.yml with hot reloading
- Production docker-compose.prod.yml with security hardening
- Separate Dockerfiles for dev and prod environments
- Health checks for all services

#### Services Configured:
- PostgreSQL 16 Alpine with init script
- Redis 7 Alpine with persistence
- Backend with uvicorn auto-reload
- Frontend with Next.js dev server
- Caddy reverse proxy (configured, not yet active)

### 5. Environment Configuration
- .env.example for development setup
- .env.production.example for production deployment
- Secure defaults with clear documentation

## Technical Challenges Resolved

1. **Python 3.13 Compatibility** - Downgraded dependencies to compatible versions
2. **SQLAlchemy Async Configuration** - Fixed pool_class parameter issue
3. **Database Naming** - Ensured consistency between init script and connection string
4. **Frontend Build** - Added missing Next.js scripts and configuration
5. **Docker Compose Version** - Removed deprecated version attribute

## Current State

✅ All services running successfully:
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

✅ Foundation ready for feature development:
- Multi-tenant architecture in place
- Authentication structure prepared
- Modular codebase for easy extension
- Docker-based development environment

## Next Steps

### Immediate Priorities:
1. Implement JWT authentication endpoints
2. Create user registration and login flows
3. Build agency management CRUD operations
4. Integrate Material-UI components
5. Set up API client in frontend

### Medium-term Goals:
1. Inflow API wrapper implementation
2. Real-time features with Socket.IO
3. Analytics dashboard
4. Billing integration
5. White-label customization system

## Development Notes

### Commands for Development:
```bash
# Start all services
docker-compose up

# Rebuild after dependency changes
docker-compose build --no-cache

# View logs
docker logs -f agencydark-backend
docker logs -f agencydark-frontend

# Database access
docker exec -it agencydark-db psql -U agencydark -d agencydark_dev
```

### Default Credentials:
- Super Admin: admin@agencydark.com / admin123

### Important Considerations:
1. Always ensure tenant context is included in API requests
2. Cache keys must be prefixed with agency_id
3. WebSocket rooms must be agency-specific
4. Test multi-tenancy thoroughly before production

## Repository Information
- Main development folder: `/Users/mariuszbudzisz/SourceCode/agency-dark`
- Python version: 3.11
- Node.js version: 18
- Docker Compose version: 2.x

---

This foundation provides a solid base for building a scalable, multi-tenant SaaS platform for OnlyFans marketing agencies.