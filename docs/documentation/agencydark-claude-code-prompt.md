# Claude Code Implementation Prompt: AgencyDark

## Project Context

I'm building AgencyDark, a white-label SaaS portal for OnlyFans marketing agencies. It will start as a wrapper around Inflow's functionality and gradually evolve into a standalone platform. I have a comprehensive technical blueprint (attached) that outlines the entire architecture and tech stack.

## Technical Stack Overview

- **Backend**: FastAPI (Python) with modular monolith architecture
- **Frontend**: React + Next.js with Material-UI components
- **Database**: PostgreSQL with Row-Level Security + Redis caching
- **Real-time**: Socket.IO with Redis adapter
- **Infrastructure**: Docker Compose/Swarm on Hetzner Cloud (NO Kubernetes)
- **Queue**: Redis Queue initially, RabbitMQ later
- **Reverse Proxy**: Caddy for automatic HTTPS

## Implementation Requirements

Please help me implement the foundation of AgencyDark following these priorities:

### Phase 1: Project Setup and Core Structure

1. **Create the project structure** following the modular monolith pattern:
```
AgencyDark/
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
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── store/
│   │   └── utils/
│   └── package.json
├── docker/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Caddyfile
└── .env.example
```

2. **Set up FastAPI backend** with:
   - Proper project structure with routers and dependencies
   - PostgreSQL connection with asyncpg
   - Redis connection for caching
   - JWT authentication with short-lived tokens (15-30 min)
   - Multi-tenant middleware using PostgreSQL RLS
   - Pydantic models for request/response validation
   - CORS configuration for frontend

3. **Configure PostgreSQL with Row-Level Security**:
   - Multi-tenant schema with agency_id isolation
   - Enable RLS on all tables
   - Create proper indexes for performance
   - Set up connection pooling

4. **Create Docker configuration**:
   - Development docker-compose.yml with hot reloading
   - Production docker-compose.prod.yml with proper secrets
   - Caddy configuration for automatic HTTPS
   - Health checks for all services

5. **Implement the Inflow wrapper module**:
   - Service layer abstracting Inflow API calls
   - Proper error handling and retry logic
   - Response caching in Redis
   - Rate limiting to respect API limits

### Phase 2: Frontend Foundation

1. **Set up Next.js with TypeScript**:
   - Configure Material-UI with custom theme
   - Set up Zustand for state management
   - Configure React Query for server state
   - Implement white-label theming system

2. **Create authentication flow**:
   - Login/logout pages
   - JWT token management with refresh
   - Protected route components
   - Role-based access control UI

3. **Build core dashboard layout**:
   - Responsive sidebar navigation
   - Header with user menu
   - Main content area with routing
   - Real-time notification bell

### Phase 3: Real-time Features

1. **Implement Socket.IO integration**:
   - Backend Socket.IO setup with Redis adapter
   - Frontend Socket.IO client with auto-reconnect
   - Namespace separation for different features
   - Room-based isolation per agency

2. **Create real-time analytics dashboard**:
   - Live metrics updates via WebSocket
   - Chart components with Recharts
   - Data aggregation in backend
   - Efficient caching strategy

## Key Implementation Details

### Multi-tenancy
- Every API request must include agency context
- Use PostgreSQL RLS for automatic data isolation
- Cache keys must be prefixed with agency_id
- WebSocket rooms must be agency-specific

### Security
- All passwords hashed with bcrypt
- JWT secrets rotated regularly
- Rate limiting on all endpoints
- Input validation on all user inputs
- CORS properly configured

### Performance
- Use Redis for all frequently accessed data
- Implement pagination on all list endpoints
- Use database indexes strategically
- Lazy load frontend components

### Development Workflow
- Use Git flow with feature branches
- Write tests for critical paths
- Use pre-commit hooks for linting
- Document all API endpoints

## Environment Configuration

Create these environment files:

**.env.development**:
```
DATABASE_URL=postgresql://agencydark:password@localhost:5432/agencydark_dev
REDIS_URL=redis://localhost:6379
JWT_SECRET=development_secret_change_this
INFLOW_API_KEY=your_inflow_api_key
FRONTEND_URL=http://localhost:3000
```

**.env.production**:
```
DATABASE_URL=postgresql://agencydark:secure_password@db:5432/agencydark
REDIS_URL=redis://redis:6379
JWT_SECRET=generate_with_openssl_rand_base64_32
INFLOW_API_KEY=your_production_inflow_key
FRONTEND_URL=https://app.agencydark.com
```

## Getting Started Commands

```bash
# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install fastapi uvicorn asyncpg redis python-jose passlib python-multipart

# Frontend setup
cd frontend
npm init next-app@latest . --typescript --tailwind --app
npm install @mui/material @emotion/react @emotion/styled zustand @tanstack/react-query socket.io-client recharts

# Start development
docker-compose up -d db redis
cd backend && uvicorn main:app --reload
cd frontend && npm run dev
```

## Important Notes

1. **Start simple**: Get basic CRUD working before adding complex features
2. **Test multi-tenancy early**: Ensure data isolation works from day one
3. **Use Docker from the start**: Even for local development
4. **Document as you build**: Especially API endpoints and deployment steps
5. **Avoid over-engineering**: We're using a modular monolith, not microservices

## Questions to Consider

1. Do you have Inflow API documentation or should I create mock services?
2. What's your preferred Git hosting (GitHub, GitLab, Bitbucket)?
3. Do you want to use GitHub Actions for CI/CD or another solution?
4. What's your Hetzner server details for initial deployment?
5. Do you have specific branding requirements for the white-label system?

Please start by creating the foundational project structure and basic FastAPI setup with PostgreSQL integration. Focus on getting the multi-tenant architecture right from the beginning, as it's much harder to add later.

## Reference Architecture

[The full technical blueprint document should be provided here with all the details about the tech stack, architecture decisions, migration strategy, etc.]