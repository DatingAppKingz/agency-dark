# AgencyDark Full Setup Plan

## Overview
This document outlines a comprehensive plan to transform the minimal working prototype into a fully functional AgencyDark application with all features operational.

## Current State
- ✅ Frontend: React + Vite application running on port 3000
- ✅ Backend: Minimal FastAPI with basic auth endpoints on port 8000
- ✅ Docker: PostgreSQL and Redis containers running
- ❌ Database: No schema or models implemented
- ❌ Features: Most API endpoints return placeholders or errors

## Goal
Create a fully functional white-label SaaS platform for OnlyFans marketing agencies with:
- Multi-tenant architecture
- Role-based access control
- Real-time chat functionality
- Analytics and reporting
- Financial tracking
- Content management
- API integrations

## Phase 1: Database Foundation

### 1.1 Database Schema Design
Create comprehensive database schema including:
- **Users & Authentication**
  - users (id, email, username, password_hash, created_at, updated_at, is_active, etc.)
  - sessions (id, user_id, token, expires_at)
  - password_resets (id, user_id, token, expires_at)
  
- **Multi-tenancy**
  - agencies (id, name, domain, settings, created_at)
  - agency_users (agency_id, user_id, role, permissions)
  - user_roles (id, name, permissions)
  
- **Models & Content**
  - models (id, agency_id, name, platform_id, stats, created_at)
  - content (id, model_id, type, url, metadata)
  - content_schedule (id, content_id, scheduled_at, status)
  
- **Chat & Messaging**
  - conversations (id, model_id, fan_id, status, created_at)
  - messages (id, conversation_id, sender_id, content, sent_at)
  - message_templates (id, agency_id, name, content)
  
- **Financial**
  - transactions (id, agency_id, amount, type, status, created_at)
  - payouts (id, model_id, amount, status, paid_at)
  - commissions (id, transaction_id, amount, rate)
  
- **Analytics**
  - analytics_events (id, type, data, created_at)
  - model_performance (model_id, date, metrics)
  - revenue_tracking (agency_id, date, amount, source)

### 1.2 Implementation Steps
1. Create SQLAlchemy models in `/backend/models/`
2. Set up proper relationships and constraints
3. Add indexes for performance
4. Create Alembic migration files

## Phase 2: Core Backend Development

### 2.1 Authentication & Authorization
- Implement proper JWT authentication with refresh tokens
- Add role-based access control (RBAC)
- Create middleware for tenant isolation
- Add API key management for external integrations

### 2.2 API Endpoints Implementation
Implement all required endpoints:

**Authentication** (`/api/v1/auth/`)
- POST /register - User registration with email verification
- POST /login - Login with 2FA support
- POST /logout - Logout and token invalidation
- POST /refresh - Refresh access token
- POST /forgot-password - Password reset flow
- POST /verify-email - Email verification

**Users** (`/api/v1/users/`)
- GET / - List users (with pagination, filtering)
- GET /{id} - Get user details
- PUT /{id} - Update user
- DELETE /{id} - Delete user
- GET /me - Current user profile
- PUT /me - Update profile

**Agencies** (`/api/v1/agencies/`)
- GET / - List agencies
- POST / - Create agency
- GET /{id} - Get agency details
- PUT /{id} - Update agency
- DELETE /{id} - Delete agency
- GET /{id}/users - List agency users
- POST /{id}/invite - Invite user to agency

**Models** (`/api/v1/models/`)
- GET / - List models
- POST / - Add model
- GET /{id} - Get model details
- PUT /{id} - Update model
- DELETE /{id} - Remove model
- GET /{id}/performance - Get performance metrics
- POST /{id}/sync - Sync with platform

**Chat** (`/api/v1/chat/`)
- GET /conversations - List conversations
- GET /conversations/{id} - Get conversation
- GET /conversations/{id}/messages - Get messages
- POST /conversations/{id}/messages - Send message
- PUT /messages/{id} - Update message
- DELETE /messages/{id} - Delete message

**Analytics** (`/api/v1/analytics/`)
- GET /overview - Dashboard overview
- GET /revenue - Revenue analytics
- GET /performance - Performance metrics
- GET /trends - Trend analysis
- POST /export - Export reports

**Financial** (`/api/v1/financial/`)
- GET /transactions - List transactions
- GET /payouts - List payouts
- POST /payouts - Create payout
- GET /commissions - Commission breakdown
- GET /statements - Financial statements

### 2.3 Business Logic Implementation
- User registration with agency assignment
- Model onboarding workflow
- Chat message routing and assignment
- Commission calculation engine
- Analytics data aggregation
- Report generation

## Phase 3: Database Setup & Migration

### 3.1 Local Database Setup
```bash
# Create database
CREATE DATABASE agencydark;
CREATE USER agencydark_user WITH PASSWORD 'agencydark_pass';
GRANT ALL PRIVILEGES ON DATABASE agencydark TO agencydark_user;
```

### 3.2 Migration Steps
1. Initialize Alembic: `alembic init alembic`
2. Configure database URL in alembic.ini
3. Create initial migration: `alembic revision --autogenerate -m "Initial schema"`
4. Apply migrations: `alembic upgrade head`

### 3.3 Seed Data
Create seed data for development:
- Sample agencies
- Test users with different roles
- Sample models
- Test conversations and messages
- Sample transactions

## Phase 4: Integration & Services

### 4.1 Redis Integration
- Session management
- Caching layer for frequently accessed data
- Real-time message queue
- Rate limiting

### 4.2 Celery Tasks
- Email sending
- Report generation
- Data synchronization
- Scheduled tasks (daily analytics, payouts)
- Webhook processing

### 4.3 WebSocket Implementation
- Real-time chat updates
- Live notifications
- Dashboard updates
- Presence indicators

### 4.4 External Integrations
- OnlyFans API wrapper
- Payment processors
- Email service (SendGrid/AWS SES)
- File storage (S3/CloudFlare R2)
- Analytics services

## Phase 5: Frontend Integration

### 5.1 API Client Updates
- Update API client to match new endpoints
- Add proper error handling
- Implement request/response interceptors
- Add retry logic

### 5.2 State Management
- Update Zustand stores with real data
- Implement proper data fetching with React Query
- Add optimistic updates
- Cache management

### 5.3 Feature Implementation
- Complete authentication flows
- Dashboard with real data
- Chat interface with WebSocket
- Analytics visualizations
- Financial management
- Settings and configuration

## Phase 6: Testing & Quality

### 6.1 Backend Testing
- Unit tests for all models
- Integration tests for API endpoints
- Performance testing
- Security testing

### 6.2 Frontend Testing
- Component testing
- Integration testing
- E2E testing with Cypress
- Performance optimization

### 6.3 Documentation
- API documentation with OpenAPI
- Developer setup guide
- Deployment guide
- User documentation

## Phase 7: Production Readiness

### 7.1 Security Hardening
- Input validation
- SQL injection prevention
- XSS protection
- CSRF protection
- Rate limiting
- API key rotation

### 7.2 Performance Optimization
- Database query optimization
- Caching strategy
- CDN configuration
- Image optimization
- Code splitting

### 7.3 Monitoring & Logging
- Application monitoring (Sentry)
- Performance monitoring
- Log aggregation
- Health checks
- Alerts

### 7.4 Deployment
- Docker optimization
- CI/CD pipeline
- Environment configuration
- Backup strategy
- Scaling plan

## Implementation Priority

### High Priority (Week 1-2)
1. Database schema and models
2. User authentication system
3. Basic CRUD operations
4. Agency multi-tenancy

### Medium Priority (Week 3-4)
1. Chat functionality
2. Analytics endpoints
3. Financial tracking
4. WebSocket support

### Low Priority (Week 5-6)
1. External integrations
2. Advanced analytics
3. Reporting system
4. Performance optimization

## Next Steps
1. Start with Phase 1: Database Foundation
2. Create all SQLAlchemy models
3. Set up Alembic migrations
4. Implement core authentication
5. Build out API endpoints incrementally

## Success Criteria
- All frontend features have working backend endpoints
- No placeholder data or hardcoded responses
- Proper error handling throughout
- Performance targets met (response times < 200ms)
- Security best practices implemented
- Comprehensive test coverage (>80%)