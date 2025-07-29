# AgencyDark Development Best Practices and Golden Rules

## Project Context
- **Purpose**: White-label SaaS portal for OnlyFans marketing agencies
- **Architecture**: Multi-tenant with agency isolation
- **Tech Stack**: Python/FastAPI backend, Next.js/React frontend
- **Key Features**: API wrappers (Inflow/OnlyFansAPI), real-time chat, analytics, commission management

## Golden Rules for Development

### 1. Architecture & Design Patterns
- **Multi-tenancy First**: Always consider tenant isolation in every feature
- **Modular Monolith**: Keep modules loosely coupled but in single deployment
- **Domain-Driven Design**: Organize code by business domains (user_management, billing, analytics)
- **API-First**: Design APIs before implementation, document thoroughly

### 2. Security Best Practices
- **JWT Implementation**:
  - Access tokens: 30 minutes expiry
  - Refresh tokens: 7 days, stored in database
  - HTTP-only cookies for refresh tokens
  - Include user role in token claims
- **Password Security**:
  - Use bcrypt with passlib
  - Minimum 8 characters
  - Reset tokens expire in 1 hour
- **Role Hierarchy**:
  - SUPER_ADMIN > AGENCY_OWNER > AGENCY_ADMIN > MODEL > CHATTER
  - Models can override chatter claims on fans
- **Data Isolation**:
  - Use PostgreSQL schemas or row-level security
  - Always filter by agency_id in queries
  - Validate tenant context in middleware

### 3. Database Design Principles
- **UUID Primary Keys**: Use UUID v4 for all tables
- **Soft Deletes**: Implement where data retention is required
- **Audit Trail**: Track all critical actions in audit_logs
- **Timestamps**: Always include created_at, updated_at with triggers
- **Indexes**: Add on foreign keys and frequently queried fields
- **Constraints**: Use unique constraints for business rules (e.g., one active claim per fan)

### 4. API Development Standards
- **RESTful Design**:
  - Consistent naming: /api/v1/resource
  - Proper HTTP methods and status codes
  - Pagination for list endpoints
  - Filtering and sorting support
- **Request/Response**:
  - Use Pydantic for validation
  - Consistent error format with request IDs
  - Include metadata in list responses
- **Authentication Flow**:
  - Public endpoints explicitly listed in middleware
  - Use dependencies for permission checking
  - Return 401 for auth errors, 403 for permission errors

### 5. Code Organization
- **File Structure**:
  ```
  backend/
  ├── api/          # REST endpoints
  ├── core/         # Shared functionality
  │   ├── domain/   # Models and schemas
  │   ├── middleware/
  │   └── dependencies/
  └── modules/      # Business domains
  ```
- **Import Paths**: Always use absolute imports (backend.core.xxx)
- **Naming Conventions**:
  - Snake_case for Python
  - PascalCase for models/classes
  - camelCase for JavaScript/TypeScript

### 6. Development Workflow
- **Environment Setup**:
  - Use virtual environments for Python
  - Docker for services (PostgreSQL, Redis)
  - Environment variables for configuration
- **Migrations**:
  - Always use Alembic for schema changes
  - Test migrations up and down
  - Include both upgrade() and downgrade()
- **Testing**:
  - Write tests for critical paths
  - Mock external API calls
  - Use pytest for Python tests

### 7. Error Handling
- **Consistent Exceptions**:
  - Use HTTPException with proper status codes
  - Include helpful error messages
  - Log errors with context
- **Validation**:
  - Validate at API boundary with Pydantic
  - Business logic validation in service layer
  - Database constraints as last defense

### 8. Performance Considerations
- **Async/Await**: Use throughout for I/O operations
- **Connection Pooling**: Configure for PostgreSQL and Redis
- **Caching Strategy**:
  - Redis for session data
  - Cache frequently accessed data
  - Invalidate on updates
- **Query Optimization**:
  - Use select_related/prefetch_related
  - Avoid N+1 queries
  - Index foreign keys and filters

### 9. Real-time Features
- **Socket.IO Integration**:
  - Separate rooms per model
  - Authentication required
  - Handle reconnection gracefully
- **Notifications**:
  - Queue for offline users
  - Priority levels
  - Read receipts

### 10. External API Integration
- **Wrapper Pattern**:
  - Abstract external APIs behind interfaces
  - Implement retry logic with exponential backoff
  - Log all requests/responses
  - Handle rate limits gracefully
- **Configuration**:
  - Store API keys securely
  - Per-tenant API keys where applicable
  - Failover strategies

## Common Pitfalls to Avoid

1. **Import Errors**: Always check Python path and use correct module prefixes
2. **Missing Dependencies**: Keep requirements.txt updated
3. **Hardcoded Values**: Use environment variables for configuration
4. **Synchronous in Async**: Don't mix sync/async database operations
5. **Tenant Leakage**: Always validate tenant context
6. **Unhandled Exceptions**: Catch and log appropriately
7. **Missing Indexes**: Profile queries and add indexes
8. **Circular Imports**: Use TYPE_CHECKING for type hints
9. **Migration Conflicts**: Coordinate schema changes in team
10. **Security Shortcuts**: Never bypass authentication/authorization

## Development Commands

### Backend
```bash
# Virtual environment
python -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Tests
pytest -v
```

### Docker
```bash
# Start services
docker-compose up -d db redis

# Full stack
docker-compose up -d

# Logs
docker-compose logs -f backend
```

## Commit Standards
- Use descriptive commit messages
- Include phase/module in commit title
- List what was implemented
- Use conventional commits when applicable
- Always test before committing

## Documentation
- Update README for setup changes
- Document API endpoints
- Include type hints
- Write docstrings for complex functions
- Keep deployment docs current

## Monitoring & Debugging
- Use structured logging
- Include request IDs
- Monitor performance metrics
- Set up alerts for errors
- Use profiling in development

Remember: **Security**, **Scalability**, and **Maintainability** are the three pillars of this project. Every decision should consider all three.