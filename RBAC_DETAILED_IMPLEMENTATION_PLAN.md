# RBAC Detailed Implementation Plan - Granular Steps

## Phase 1: Backend API Security (Priority: CRITICAL)
**Timeline: 2-3 days**

### 1.1 Apply RoleChecker to All Endpoints

#### 1.1.1 Create Role Decorators
- **Step 1: Create base decorator structure**
  * Create `/backend/core/auth/decorators.py` file
  * Import necessary dependencies (functools, FastAPI, HTTPException)
  * Define base decorator class structure
  
- **Step 2: Implement require_roles decorator**
  * Write the `@require_roles(["ROLE1", "ROLE2"])` decorator function
  * Add role validation logic
  * Add proper error handling with 403 responses
  * Write unit tests for the decorator
  
- **Step 3: Implement require_agency_match decorator**
  * Write decorator to check if user's agency matches resource agency
  * Extract agency_id from request path/body
  * Compare with user's agency_id
  * Add bypass for SUPER_ADMIN role
  * Write unit tests
  
- **Step 4: Implement require_self_or_admin decorator**
  * Write decorator for "own data or admin" pattern
  * Check if user_id matches resource owner
  * Allow SUPER_ADMIN/AGENCY_OWNER/AGENCY_ADMIN to bypass
  * Write unit tests
  
- **Step 5: Implement require_model_assignment decorator**
  * Create decorator for chatter-model assignments
  * Query assignment table to verify access
  * Cache assignments for performance
  * Write unit tests

#### 1.1.2 Update User Management Endpoints
- **Step 1: Analyze current user endpoints**
  * List all endpoints in `/backend/api/v1/endpoints/users.py`
  * Document current permission logic
  * Identify gaps in security
  
- **Step 2: Update GET /users endpoint**
  * Add `@require_roles(["SUPER_ADMIN", "AGENCY_OWNER", "AGENCY_ADMIN"])` decorator
  * Ensure agency filtering is applied
  * Test with each role
  * Verify data isolation
  
- **Step 3: Update POST /users endpoint**
  * Add role decorator
  * Validate user can only create in their agency
  * Prevent role elevation attacks
  * Add audit logging
  * Test all scenarios
  
- **Step 4: Update GET /users/:id endpoint**
  * Add `@require_self_or_admin` decorator
  * Test own profile access
  * Test admin access
  * Test cross-agency denial
  
- **Step 5: Update PUT /users/:id endpoint**
  * Add appropriate decorators
  * Limit which fields users can update
  * Prevent role self-elevation
  * Add field-level permissions
  * Test all field updates
  
- **Step 6: Update DELETE /users/:id endpoint**
  * Add `@require_roles(["SUPER_ADMIN", "AGENCY_OWNER"])` decorator
  * Add soft-delete functionality
  * Prevent self-deletion
  * Add confirmation requirement
  * Test deletion scenarios

#### 1.1.3 Update Agency Management Endpoints
- **Step 1: Secure GET /agencies**
  * Add `@require_roles(["SUPER_ADMIN"])` decorator
  * Implement pagination
  * Add filtering options
  * Test access denial for non-super-admins
  
- **Step 2: Secure POST /agencies**
  * Add super admin only decorator
  * Validate agency data
  * Create default roles for new agency
  * Send welcome email to owner
  * Test agency creation
  
- **Step 3: Secure GET /agencies/:id**
  * Add role check for SUPER_ADMIN or own agency
  * Include related statistics
  * Hide sensitive data from non-owners
  * Test data visibility
  
- **Step 4: Secure PUT /agencies/:id**
  * Add decorator for SUPER_ADMIN or AGENCY_OWNER
  * Limit which fields can be updated
  * Add validation for critical fields
  * Log all changes
  * Test update scenarios
  
- **Step 5: Secure DELETE /agencies/:id**
  * Add SUPER_ADMIN only decorator
  * Implement soft delete
  * Archive all related data
  * Send notifications
  * Test deletion process

#### 1.1.4 Update Model Management Endpoints
- **Step 1: Secure GET /models**
  * Add role-based filtering
  * Implement chatter assignment checks
  * Add search functionality
  * Include performance metrics
  * Test visibility rules
  
- **Step 2: Secure POST /models**
  * Add agency admin/owner decorator
  * Validate model data
  * Create user account
  * Set up default permissions
  * Test model creation
  
- **Step 3: Secure GET /models/:id**
  * Check model ownership or admin rights
  * Include analytics data based on role
  * Hide sensitive info from chatters
  * Test data visibility
  
- **Step 4: Secure PUT /models/:id**
  * Add appropriate role checks
  * Allow limited self-updates
  * Validate stage name uniqueness
  * Log profile changes
  * Test update permissions
  
- **Step 5: Secure model analytics endpoints**
  * Add role-based data filtering
  * Limit date ranges by role
  * Aggregate data for privacy
  * Cache results
  * Test data access

#### 1.1.5 Update Financial Endpoints
- **Step 1: Secure GET /financial/overview**
  * Add role decorators
  * Filter data by agency/user
  * Calculate role-specific metrics
  * Hide sensitive amounts from models
  * Test data visibility
  
- **Step 2: Secure GET /financial/transactions**
  * Implement role-based filtering
  * Add date range limits
  * Include export functionality
  * Paginate results
  * Test access patterns
  
- **Step 3: Secure POST /financial/payouts**
  * Add admin-only decorator
  * Validate payout amounts
  * Check available balance
  * Queue for processing
  * Test payout creation
  
- **Step 4: Secure financial export endpoints**
  * Add role checks for exports
  * Limit export size by role
  * Add rate limiting
  * Log all exports
  * Test export permissions

### 1.2 Implement Data Scoping

#### 1.2.1 Create Agency-Scoped Query Filters
- **Step 1: Create base query filter class**
  * Create `/backend/core/filters/agency_filter.py`
  * Define AgencyFilter base class
  * Add get_agency_filter method
  * Handle SUPER_ADMIN exceptions
  
- **Step 2: Implement SQLAlchemy filter mixins**
  * Create filter_by_agency function
  * Add automatic agency_id injection
  * Handle joined queries
  * Write comprehensive tests
  
- **Step 3: Create model-specific filters**
  * Create UserFilter class
  * Create ModelFilter class
  * Create TransactionFilter class
  * Test each filter class

#### 1.2.2 Implement Automatic Agency Filtering
- **Step 1: Modify base repository class**
  * Update BaseRepository in `/backend/core/repositories/base.py`
  * Add automatic agency filtering to queries
  * Make it configurable per model
  * Test with existing queries
  
- **Step 2: Update all repository methods**
  * Update find_all methods
  * Update find_by_id methods
  * Update count methods
  * Update aggregate methods
  * Test each repository
  
- **Step 3: Add filter bypass for system operations**
  * Create system context manager
  * Allow bypassing filters for migrations
  * Add logging for bypass usage
  * Test bypass functionality

#### 1.2.3 Add User-Specific Data Filters
- **Step 1: Implement model ownership checks**
  * Add is_model_owner function
  * Check in all model endpoints
  * Cache ownership for performance
  * Test ownership validation
  
- **Step 2: Implement chatter assignment filters**
  * Create get_assigned_models function
  * Filter chat/message queries
  * Update analytics to respect assignments
  * Test assignment filtering
  
- **Step 3: Add personal data filters**
  * Filter financial data to own records
  * Filter analytics to own performance
  * Filter messages to own conversations
  * Test personal data isolation

### 1.3 Create Permission Middleware

#### 1.3.1 Build Centralized Permission Checking
- **Step 1: Create permission middleware class**
  * Create `/backend/middleware/permissions.py`
  * Define PermissionMiddleware class
  * Add request/response hooks
  * Configure logging
  
- **Step 2: Implement permission check flow**
  * Extract user from request
  * Determine required permissions
  * Check against user permissions
  * Handle special cases
  * Test permission flow
  
- **Step 3: Add to FastAPI app**
  * Register middleware in main.py
  * Configure middleware order
  * Add exception handling
  * Test with existing endpoints

#### 1.3.2 Implement Resource-Based Permissions
- **Step 1: Create resource permission model**
  * Define resource types (user, model, transaction, etc.)
  * Create permission matrix
  * Add to database schema
  * Create migration
  
- **Step 2: Implement permission checking**
  * Create check_resource_permission function
  * Add resource ID extraction
  * Query permission table
  * Cache permissions
  * Test permission checks
  
- **Step 3: Add resource permission API**
  * Create endpoints to manage permissions
  * Add bulk permission updates
  * Include permission templates
  * Test permission management

#### 1.3.3 Add Operation-Based Permissions
- **Step 1: Define operation types**
  * Create OperationType enum (READ, WRITE, DELETE, EXPORT)
  * Map HTTP methods to operations
  * Document operation meanings
  * Add to permission model
  
- **Step 2: Implement operation checking**
  * Extend permission checker
  * Add operation validation
  * Combine with role checks
  * Test operation permissions
  
- **Step 3: Add fine-grained controls**
  * Implement field-level permissions
  * Add conditional permissions
  * Create permission expressions
  * Test complex permissions

#### 1.3.4 Create Permission Caching
- **Step 1: Design cache structure**
  * Choose cache key format
  * Determine TTL values
  * Plan cache invalidation
  * Document cache strategy
  
- **Step 2: Implement Redis caching**
  * Create permission cache class
  * Add get/set methods
  * Implement cache warming
  * Add cache statistics
  * Test cache performance
  
- **Step 3: Add cache invalidation**
  * Listen for permission changes
  * Invalidate affected cache entries
  * Add bulk invalidation
  * Test cache consistency

## Phase 2: WebSocket Security (Priority: HIGH)
**Timeline: 1-2 days**

### 2.1 WebSocket Authentication

#### 2.1.1 Implement JWT Validation
- **Step 1: Create WebSocket auth middleware**
  * Create `/backend/core/websocket/auth.py`
  * Add JWT extraction from connection
  * Handle auth in connection params
  * Support auth in first message
  
- **Step 2: Validate JWT tokens**
  * Decode and verify JWT
  * Check token expiration
  * Validate token signature
  * Extract user claims
  * Test token validation
  
- **Step 3: Handle authentication failures**
  * Send error message to client
  * Close connection gracefully
  * Log failed attempts
  * Implement retry logic
  * Test failure scenarios

#### 2.1.2 Add Connection Authentication Middleware
- **Step 1: Create connection manager**
  * Build WebSocketManager class
  * Track authenticated connections
  * Store user metadata
  * Implement connection pooling
  
- **Step 2: Integrate with existing WebSocket handlers**
  * Update chat WebSocket handler
  * Update notification handler
  * Update analytics handler
  * Test each handler
  
- **Step 3: Add connection lifecycle events**
  * Emit connection event
  * Track connection duration
  * Handle disconnection cleanup
  * Test lifecycle management

#### 2.1.3 Handle Token Refresh
- **Step 1: Implement refresh protocol**
  * Define refresh message format
  * Add refresh handler
  * Validate refresh tokens
  * Issue new access token
  * Test refresh flow
  
- **Step 2: Add automatic refresh**
  * Monitor token expiration
  * Send refresh reminder
  * Handle refresh response
  * Update connection auth
  * Test automatic refresh
  
- **Step 3: Handle refresh failures**
  * Disconnect on refresh failure
  * Send reconnect instruction
  * Clean up resources
  * Log refresh failures
  * Test failure handling

### 2.2 WebSocket Authorization

#### 2.2.1 Add Role-Based Channel Access
- **Step 1: Define channel permissions**
  * Create channel permission map
  * Map roles to allowed channels
  * Document channel purposes
  * Add to configuration
  
- **Step 2: Implement channel authorization**
  * Check role on channel join
  * Validate channel existence
  * Apply agency filters
  * Send authorization errors
  * Test channel access
  
- **Step 3: Add dynamic channel creation**
  * Allow role-based channel creation
  * Validate channel names
  * Set channel permissions
  * Broadcast channel availability
  * Test channel creation

#### 2.2.2 Implement Message Filtering
- **Step 1: Create message filter system**
  * Define filter rules per role
  * Build filter pipeline
  * Add filter configuration
  * Document filter behavior
  
- **Step 2: Apply filters to outgoing messages**
  * Filter by recipient role
  * Remove sensitive fields
  * Apply agency isolation
  * Test message filtering
  
- **Step 3: Add message validation**
  * Validate incoming message format
  * Check message permissions
  * Sanitize message content
  * Log suspicious messages
  * Test validation rules

#### 2.2.3 Create Room/Channel Isolation
- **Step 1: Implement agency-based rooms**
  * Prefix rooms with agency ID
  * Validate room membership
  * Prevent cross-agency access
  * Test room isolation
  
- **Step 2: Add private channels**
  * Create user-specific channels
  * Implement invite system
  * Add channel encryption
  * Test private channels
  
- **Step 3: Implement broadcast controls**
  * Limit broadcast by role
  * Add broadcast permissions
  * Filter broadcast recipients
  * Test broadcast isolation

### 2.3 Real-time Permission Updates

#### 2.3.1 Handle Permission Changes
- **Step 1: Create permission event system**
  * Define permission change events
  * Build event publisher
  * Add event subscribers
  * Test event flow
  
- **Step 2: Listen for permission updates**
  * Subscribe to permission events
  * Update connection permissions
  * Refresh channel access
  * Test permission updates
  
- **Step 3: Apply permission changes**
  * Remove revoked access
  * Add granted access
  * Update message filters
  * Test permission application

#### 2.3.2 Disconnect Users on Role Changes
- **Step 1: Detect role changes**
  * Monitor user updates
  * Compare old/new roles
  * Trigger disconnection
  * Test role change detection
  
- **Step 2: Implement graceful disconnection**
  * Send role change notification
  * Allow data save
  * Close connection
  * Test disconnection flow
  
- **Step 3: Add reconnection instructions**
  * Send new auth requirements
  * Provide reconnect URL
  * Include reason code
  * Test reconnection

## Phase 3: Advanced Security Features (Priority: HIGH)
**Timeline: 2-3 days**

### 3.1 API Key Management

#### 3.1.1 Implement API Key Generation
- **Step 1: Create API key model**
  * Design api_keys table schema
  * Add key metadata fields
  * Create database migration
  * Test schema creation
  
- **Step 2: Build key generation service**
  * Create secure key generation
  * Add key prefix for identification
  * Hash keys for storage
  * Generate key ID
  * Test key generation
  
- **Step 3: Create API key endpoints**
  * POST /api-keys - Create key
  * GET /api-keys - List keys
  * DELETE /api-keys/:id - Revoke key
  * Test all endpoints

#### 3.1.2 Add API Key Permissions
- **Step 1: Design permission model**
  * Create key_permissions table
  * Define permission scopes
  * Add expiration support
  * Test permission storage
  
- **Step 2: Implement scope checking**
  * Parse key permissions
  * Check against request
  * Apply role limits
  * Test scope validation
  
- **Step 3: Add permission inheritance**
  * Inherit from user role
  * Apply additional restrictions
  * Document inheritance rules
  * Test permission inheritance

#### 3.1.3 Create API Key Usage Tracking
- **Step 1: Design tracking schema**
  * Create api_key_usage table
  * Add request metadata
  * Plan data retention
  * Test schema
  
- **Step 2: Implement usage logging**
  * Log each API key use
  * Track endpoint access
  * Record response time
  * Test usage logging
  
- **Step 3: Add usage analytics**
  * Create usage dashboard
  * Add usage alerts
  * Export usage data
  * Test analytics

#### 3.1.4 Implement Rate Limiting
- **Step 1: Design rate limit rules**
  * Define limits per role
  * Create limit configuration
  * Plan limit storage
  * Document limits
  
- **Step 2: Implement rate limiter**
  * Use Redis for counters
  * Add sliding window
  * Handle limit exceeded
  * Test rate limiting
  
- **Step 3: Add rate limit headers**
  * Return limit in headers
  * Show remaining calls
  * Include reset time
  * Test header values

### 3.2 Audit Trail System

#### 3.2.1 Create Comprehensive Audit Logging
- **Step 1: Design audit schema**
  * Create audit_logs table
  * Define log entry format
  * Add indexes for queries
  * Test schema performance
  
- **Step 2: Implement audit logger**
  * Create AuditLogger class
  * Add automatic logging
  * Include request context
  * Test logger functionality
  
- **Step 3: Add audit triggers**
  * Log all auth attempts
  * Log permission checks
  * Log data changes
  * Test audit completeness

#### 3.2.2 Log Permission Checks
- **Step 1: Instrument permission system**
  * Add logging to decorators
  * Log check results
  * Include denial reasons
  * Test permission logging
  
- **Step 2: Create permission reports**
  * Build denial report
  * Add success metrics
  * Create anomaly detection
  * Test reporting
  
- **Step 3: Add real-time monitoring**
  * Stream logs to monitoring
  * Create alerts for failures
  * Add dashboard widgets
  * Test monitoring

#### 3.2.3 Implement Role-Based Audit Access
- **Step 1: Define audit visibility rules**
  * Determine who sees what
  * Create filter rules
  * Document access policy
  * Test visibility rules
  
- **Step 2: Build audit API**
  * Create audit endpoints
  * Add search functionality
  * Implement filters
  * Test API access
  
- **Step 3: Add audit UI**
  * Create audit viewer
  * Add export options
  * Include visualizations
  * Test UI functionality

### 3.3 Session Management

#### 3.3.1 Implement Concurrent Session Limits
- **Step 1: Define session limits**
  * Set limits per role
  * Create limit configuration
  * Plan enforcement strategy
  * Document limits
  
- **Step 2: Track active sessions**
  * Create sessions table
  * Monitor session activity
  * Update last activity
  * Test session tracking
  
- **Step 3: Enforce session limits**
  * Check on login
  * Terminate oldest session
  * Notify user
  * Test enforcement

#### 3.3.2 Add Session Activity Tracking
- **Step 1: Design activity schema**
  * Define activity types
  * Create tracking table
  * Plan data retention
  * Test schema
  
- **Step 2: Implement activity logging**
  * Log page views
  * Track API calls
  * Record interactions
  * Test logging
  
- **Step 3: Create activity reports**
  * Build user timelines
  * Add activity analytics
  * Export activity data
  * Test reporting

## Phase 4: Feature-Specific Permissions (Priority: MEDIUM)
**Timeline: 3-4 days**

### 4.1 Report Access Control

#### 4.1.1 Implement Report Template Permissions
- **Step 1: Add permissions to templates**
  * Update report_templates table
  * Add role restrictions
  * Include agency scoping
  * Test schema updates
  
- **Step 2: Check permissions on access**
  * Validate on template load
  * Filter template list
  * Handle permission errors
  * Test access control
  
- **Step 3: Add sharing functionality**
  * Create sharing system
  * Set share permissions
  * Track share usage
  * Test sharing

#### 4.1.2 Add Report Generation Access
- **Step 1: Define generation rules**
  * Set who can generate
  * Add approval workflow
  * Limit generation frequency
  * Document rules
  
- **Step 2: Implement generation checks**
  * Check before generation
  * Validate parameters
  * Apply data filters
  * Test generation
  
- **Step 3: Add scheduling permissions**
  * Control who can schedule
  * Limit schedule frequency
  * Add approval for schedules
  * Test scheduling

### 4.2 Bulk Operations Security

#### 4.2.1 Add Role Checks for Bulk Operations
- **Step 1: Define bulk operation permissions**
  * List all bulk operations
  * Assign required roles
  * Set size limits
  * Document permissions
  
- **Step 2: Implement permission checks**
  * Check before execution
  * Validate operation scope
  * Apply agency filters
  * Test permission checks
  
- **Step 3: Add approval workflow**
  * Require approval for large ops
  * Send notifications
  * Track approvals
  * Test workflow

#### 4.2.2 Implement Operation Limits
- **Step 1: Define limits by role**
  * Set record count limits
  * Add time-based limits
  * Create exception process
  * Document limits
  
- **Step 2: Enforce limits**
  * Check before operation
  * Split large operations
  * Queue for processing
  * Test enforcement
  
- **Step 3: Add monitoring**
  * Track bulk operations
  * Alert on unusual activity
  * Create usage reports
  * Test monitoring

### 4.3 Financial Operations

#### 4.3.1 Implement Payout Approval Workflow
- **Step 1: Design approval process**
  * Define approval levels
  * Create approval table
  * Set threshold rules
  * Test schema
  
- **Step 2: Build approval system**
  * Create approval requests
  * Route to approvers
  * Handle responses
  * Test workflow
  
- **Step 3: Add notifications**
  * Notify on request
  * Send reminders
  * Alert on approval
  * Test notifications

#### 4.3.2 Add Transaction Visibility Rules
- **Step 1: Define visibility matrix**
  * Who sees which transactions
  * Set filter rules
  * Handle special cases
  * Document rules
  
- **Step 2: Implement filters**
  * Apply in queries
  * Hide sensitive data
  * Aggregate when needed
  * Test filtering
  
- **Step 3: Add audit trail**
  * Log transaction views
  * Track exports
  * Monitor access patterns
  * Test auditing

### 4.4 ML/AI Features

#### 4.4.1 Restrict Prediction Access
- **Step 1: Define ML permissions**
  * List ML features
  * Assign role access
  * Set usage limits
  * Document permissions
  
- **Step 2: Implement access control**
  * Check on prediction request
  * Validate parameters
  * Apply data filters
  * Test access control
  
- **Step 3: Add usage tracking**
  * Log prediction requests
  * Track accuracy
  * Monitor costs
  * Test tracking

## Phase 5: Testing & Hardening (Priority: CRITICAL)
**Timeline: 2-3 days**

### 5.1 Security Testing

#### 5.1.1 Create Permission Test Suite
- **Step 1: Design test structure**
  * Create test categories
  * Plan test scenarios
  * Set up test data
  * Document approach
  
- **Step 2: Write unit tests**
  * Test each decorator
  * Test permission functions
  * Test edge cases
  * Achieve 100% coverage
  
- **Step 3: Create integration tests**
  * Test full request flow
  * Test permission combinations
  * Test failure scenarios
  * Validate error messages

#### 5.1.2 Test All Endpoints
- **Step 1: Create endpoint test matrix**
  * List all endpoints
  * Define test cases per role
  * Plan test execution
  * Document results
  
- **Step 2: Implement automated tests**
  * Write test for each endpoint
  * Test with each role
  * Verify response data
  * Check error handling
  
- **Step 3: Run security scan**
  * Use security tools
  * Test for vulnerabilities
  * Check for data leaks
  * Fix issues found

#### 5.1.3 Verify Data Isolation
- **Step 1: Test agency isolation**
  * Create multi-agency test data
  * Try cross-agency access
  * Verify complete isolation
  * Document test results
  
- **Step 2: Test user isolation**
  * Verify personal data access
  * Test model-chatter isolation
  * Check financial isolation
  * Record test outcomes
  
- **Step 3: Test edge cases**
  * Test with deleted users
  * Test with disabled agencies
  * Test permission changes
  * Verify all scenarios

### 5.2 Performance Testing

#### 5.2.1 Load Test Permission Checks
- **Step 1: Create load test scenarios**
  * Design realistic load patterns
  * Include permission checks
  * Plan test duration
  * Set success criteria
  
- **Step 2: Execute load tests**
  * Run with increasing load
  * Monitor response times
  * Track resource usage
  * Identify bottlenecks
  
- **Step 3: Analyze results**
  * Review performance metrics
  * Identify slow queries
  * Find optimization opportunities
  * Document findings

#### 5.2.2 Optimize Permission Caching
- **Step 1: Profile cache performance**
  * Measure cache hit rate
  * Track cache misses
  * Monitor memory usage
  * Identify patterns
  
- **Step 2: Optimize cache strategy**
  * Adjust TTL values
  * Improve key design
  * Add cache warming
  * Test improvements
  
- **Step 3: Implement cache monitoring**
  * Add cache metrics
  * Create dashboards
  * Set up alerts
  * Document strategy

### 5.3 Integration Testing

#### 5.3.1 Test Frontend-Backend Sync
- **Step 1: Verify route protection**
  * Test protected routes
  * Verify error handling
  * Check redirects
  * Test with each role
  
- **Step 2: Test permission updates**
  * Change user permissions
  * Verify UI updates
  * Test without refresh
  * Check all scenarios
  
- **Step 3: Test error messages**
  * Verify user-friendly errors
  * Check error consistency
  * Test localization
  * Document messages

#### 5.3.2 Test WebSocket Permissions
- **Step 1: Test connection auth**
  * Try invalid tokens
  * Test expired tokens
  * Verify disconnection
  * Check reconnection
  
- **Step 2: Test channel access**
  * Try unauthorized channels
  * Test permission changes
  * Verify message filtering
  * Check all roles
  
- **Step 3: Test real-time updates**
  * Change permissions live
  * Verify immediate effect
  * Test consistency
  * Document behavior

### 5.4 Documentation & Training

#### 5.4.1 Create Developer Guide
- **Step 1: Document architecture**
  * Explain permission system
  * Show component diagram
  * List all decorators
  * Provide examples
  
- **Step 2: Write implementation guide**
  * How to add permissions
  * Best practices
  * Common patterns
  * Troubleshooting
  
- **Step 3: Create API documentation**
  * Document all endpoints
  * Show required permissions
  * Provide curl examples
  * Include error codes

#### 5.4.2 Build Admin UI
- **Step 1: Design permission UI**
  * Create mockups
  * Plan user flow
  * Get feedback
  * Finalize design
  
- **Step 2: Implement permission manager**
  * Build role editor
  * Add user permissions
  * Create audit viewer
  * Test functionality
  
- **Step 3: Add help system**
  * Create tooltips
  * Add documentation links
  * Build search
  * Test usability

---

## Success Metrics
- Zero unauthorized access incidents
- <50ms permission check overhead
- 100% test coverage
- Complete audit trail
- No data leakage between agencies

## This detailed plan breaks down each task into specific, actionable steps that can be tracked and completed incrementally.