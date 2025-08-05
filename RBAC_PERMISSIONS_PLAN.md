# Role-Based Access Control (RBAC) Permissions Plan

## Overview
This document defines the comprehensive permissions structure for the Agency Dark platform. Each route, endpoint, and feature is mapped to specific user roles that are allowed to access it.

## User Roles
1. **SUPER_ADMIN** - Platform administrator with full system access
2. **AGENCY_OWNER** - Owner of an agency with full control over their agency
3. **AGENCY_ADMIN** - Agency administrator with management capabilities
4. **MODEL** - Content creator with access to their own data and performance
5. **CHATTER** - Chat operator managing conversations for assigned models
6. **AGENCY_MEMBER** - Basic agency staff with view-only access

## Frontend Routes & Permissions

### Dashboard Routes

#### `/dashboard` - Main Dashboard
- **Allowed Roles**: ALL ROLES
- **Description**: Role-specific dashboard view
- **Behavior**: Each role sees a customized dashboard

#### `/dashboard/agencies` - Agencies Management
- **Allowed Roles**: SUPER_ADMIN
- **Description**: Manage all agencies on the platform
- **Features**: Create, edit, delete agencies, view agency analytics

#### `/dashboard/users` - Users List
- **Allowed Roles**: AGENCY_OWNER, AGENCY_ADMIN
- **Description**: View and manage users within their agency
- **Features**: List users, filter by role, search, pagination

#### `/dashboard/models` - Model Overview
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL
- **Description**: Overview of models
- **Behavior**: 
  - SUPER_ADMIN: See all models across agencies
  - AGENCY_OWNER/ADMIN: See models in their agency
  - MODEL: Redirects to their own profile

#### `/dashboard/models/:modelId` - Model Details
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (own profile only)
- **Description**: Detailed model information and analytics
- **Features**: Performance metrics, earnings, content stats

#### `/dashboard/models/pending` - Pending Model Approvals
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Review and approve new model registrations
- **Features**: Approve/reject models, KYC verification

#### `/dashboard/models/onboarding` - Model Onboarding
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Manage model onboarding process
- **Features**: Track onboarding steps, assign chatters

#### `/dashboard/chat` - Chat Interface
- **Allowed Roles**: MODEL, CHATTER
- **Description**: Messaging interface for fan communication
- **Features**: Real-time chat, templates, media sharing

#### `/dashboard/analytics` - Analytics Dashboard
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL, CHATTER
- **Description**: Performance analytics and insights
- **Behavior**:
  - SUPER_ADMIN: Platform-wide analytics
  - AGENCY_OWNER/ADMIN: Agency-wide analytics
  - MODEL: Personal analytics only
  - CHATTER: Performance metrics for assigned models

#### `/dashboard/ml-insights` - ML Insights
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Machine learning predictions and insights
- **Features**: Churn predictions, revenue forecasts, trend analysis

#### `/dashboard/financial` - Financial Overview
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL
- **Description**: Financial dashboard
- **Behavior**:
  - SUPER_ADMIN: Platform-wide financials
  - AGENCY_OWNER/ADMIN: Agency financials
  - MODEL: Personal earnings only

#### `/dashboard/financial/payouts` - Payouts Management
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL
- **Description**: Manage and view payouts
- **Features**: 
  - SUPER_ADMIN/AGENCY_OWNER/ADMIN: Process payouts, view all
  - MODEL: View own payouts only

#### `/dashboard/financial/transactions` - Transaction History
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL
- **Description**: View transaction history
- **Behavior**: Filtered by role and agency scope

#### `/dashboard/settings` - General Settings
- **Allowed Roles**: ALL ROLES
- **Description**: User profile and preferences
- **Features**: Update profile, change password, preferences

#### `/dashboard/settings/api-keys` - API Keys Management
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: Manage API keys for integrations
- **Features**: Create, revoke, monitor API keys

#### `/dashboard/settings/webhooks` - Webhooks Configuration
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: Configure webhook endpoints
- **Features**: Add webhooks, test endpoints, view logs

#### `/dashboard/bulk-operations` - Bulk Operations
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Perform bulk actions on data
- **Features**: Bulk user updates, mass messaging, data exports

#### `/dashboard/admin/users` - User Management (Admin)
- **Allowed Roles**: SUPER_ADMIN
- **Description**: Platform-wide user administration
- **Features**: Create users, manage roles, suspend accounts

#### `/dashboard/sync` - Data Synchronization
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Sync data with external platforms
- **Features**: OnlyFans sync, data imports, sync status

#### `/dashboard/reports` - Reports Center
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL, CHATTER
- **Description**: Access various reports
- **Behavior**: Role-based report filtering

#### `/dashboard/reports/builder` - Report Builder
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Create custom reports
- **Features**: Drag-drop builder, save templates

#### `/dashboard/reports/view/:templateId` - View Report
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL, CHATTER
- **Description**: View generated reports
- **Behavior**: Access limited to relevant reports

#### `/dashboard/profile` - User Profile
- **Allowed Roles**: ALL ROLES
- **Description**: View and edit own profile
- **Features**: Update info, upload avatar, view activity

#### `/dashboard/agency` - Agency Settings
- **Allowed Roles**: AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Manage agency configuration
- **Features**: Update agency info, billing, team settings

## Backend API Endpoints & Permissions

### Authentication Endpoints

#### `POST /api/v1/auth/login`
- **Allowed Roles**: PUBLIC
- **Description**: User login

#### `POST /api/v1/auth/logout`
- **Allowed Roles**: ALL AUTHENTICATED
- **Description**: User logout

#### `GET /api/v1/auth/me`
- **Allowed Roles**: ALL AUTHENTICATED
- **Description**: Get current user info

#### `POST /api/v1/auth/refresh`
- **Allowed Roles**: ALL AUTHENTICATED
- **Description**: Refresh access token

### User Management Endpoints

#### `GET /api/v1/users`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: List users
- **Behavior**: Filtered by agency for non-super admins

#### `POST /api/v1/users`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Create new user
- **Restrictions**: Can only create users for own agency

#### `GET /api/v1/users/:userId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, SELF
- **Description**: Get user details
- **Behavior**: Own profile always accessible

#### `PUT /api/v1/users/:userId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, SELF (limited)
- **Description**: Update user
- **Restrictions**: Self can only update profile fields

#### `DELETE /api/v1/users/:userId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: Delete user

### Agency Management Endpoints

#### `GET /api/v1/agencies`
- **Allowed Roles**: SUPER_ADMIN
- **Description**: List all agencies

#### `POST /api/v1/agencies`
- **Allowed Roles**: SUPER_ADMIN
- **Description**: Create new agency

#### `GET /api/v1/agencies/:agencyId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own), AGENCY_ADMIN (own)
- **Description**: Get agency details

#### `PUT /api/v1/agencies/:agencyId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own)
- **Description**: Update agency

#### `DELETE /api/v1/agencies/:agencyId`
- **Allowed Roles**: SUPER_ADMIN
- **Description**: Delete agency

### Model Management Endpoints

#### `GET /api/v1/models`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, CHATTER (assigned only)
- **Description**: List models
- **Behavior**: Filtered by permissions

#### `POST /api/v1/models`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Create model profile

#### `GET /api/v1/models/:modelId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (self), CHATTER (assigned)
- **Description**: Get model details

#### `PUT /api/v1/models/:modelId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (limited self)
- **Description**: Update model profile

#### `GET /api/v1/models/:modelId/analytics`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (self)
- **Description**: Get model analytics

#### `GET /api/v1/models/:modelId/earnings`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (self)
- **Description**: Get earnings data

### Chat/Messaging Endpoints

#### `GET /api/v1/chats`
- **Allowed Roles**: MODEL, CHATTER
- **Description**: List conversations
- **Behavior**: MODEL sees own, CHATTER sees assigned

#### `GET /api/v1/chats/:chatId/messages`
- **Allowed Roles**: MODEL (own), CHATTER (assigned)
- **Description**: Get chat messages

#### `POST /api/v1/chats/:chatId/messages`
- **Allowed Roles**: MODEL (own), CHATTER (assigned)
- **Description**: Send message

#### `GET /api/v1/chat-templates`
- **Allowed Roles**: AGENCY_OWNER, AGENCY_ADMIN, MODEL, CHATTER
- **Description**: Get message templates

### Analytics Endpoints

#### `GET /api/v1/analytics/platform`
- **Allowed Roles**: SUPER_ADMIN
- **Description**: Platform-wide analytics

#### `GET /api/v1/analytics/agency/:agencyId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own), AGENCY_ADMIN (own)
- **Description**: Agency analytics

#### `GET /api/v1/analytics/model/:modelId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (self)
- **Description**: Model analytics

#### `GET /api/v1/analytics/chatter/:chatterId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, CHATTER (self)
- **Description**: Chatter performance

### Financial Endpoints

#### `GET /api/v1/financial/overview`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Financial overview
- **Behavior**: Scoped by role

#### `GET /api/v1/financial/transactions`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (own)
- **Description**: Transaction history

#### `GET /api/v1/financial/payouts`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN, MODEL (own)
- **Description**: Payout history

#### `POST /api/v1/financial/payouts`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Process payout

#### `GET /api/v1/financial/invoices`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: View invoices

### Settings/Configuration Endpoints

#### `GET /api/v1/settings/agency/:agencyId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own), AGENCY_ADMIN (own)
- **Description**: Get agency settings

#### `PUT /api/v1/settings/agency/:agencyId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own)
- **Description**: Update agency settings

#### `GET /api/v1/api-keys`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: List API keys

#### `POST /api/v1/api-keys`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: Create API key

#### `DELETE /api/v1/api-keys/:keyId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own)
- **Description**: Revoke API key

#### `GET /api/v1/webhooks`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: List webhooks

#### `POST /api/v1/webhooks`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: Create webhook

#### `DELETE /api/v1/webhooks/:webhookId`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER (own)
- **Description**: Delete webhook

### Sync/Import Endpoints

#### `POST /api/v1/sync/onlyfans`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Trigger OnlyFans sync

#### `GET /api/v1/sync/status`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Get sync status

#### `POST /api/v1/import/data`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER
- **Description**: Import bulk data

### Reports Endpoints

#### `GET /api/v1/reports/templates`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: List report templates

#### `POST /api/v1/reports/templates`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Create report template

#### `GET /api/v1/reports/generate/:templateId`
- **Allowed Roles**: Based on template permissions
- **Description**: Generate report

#### `GET /api/v1/reports/export/:reportId`
- **Allowed Roles**: Based on report permissions
- **Description**: Export report

### ML/AI Endpoints

#### `GET /api/v1/ml/predictions/churn`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Get churn predictions

#### `GET /api/v1/ml/predictions/revenue`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Revenue predictions

#### `GET /api/v1/ml/insights/trends`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Trend analysis

## WebSocket Endpoints

#### `WS /api/v1/ws/chat`
- **Allowed Roles**: MODEL, CHATTER
- **Description**: Real-time chat

#### `WS /api/v1/ws/notifications`
- **Allowed Roles**: ALL AUTHENTICATED
- **Description**: Real-time notifications

#### `WS /api/v1/ws/analytics`
- **Allowed Roles**: SUPER_ADMIN, AGENCY_OWNER, AGENCY_ADMIN
- **Description**: Real-time analytics updates

## Special Permissions & Rules

### Cross-Agency Access
- SUPER_ADMIN can access data across all agencies
- Other roles are restricted to their own agency

### Model-Chatter Assignment
- Chatters can only access models they are assigned to
- Assignment managed by AGENCY_OWNER/ADMIN

### Financial Permissions
- Models can only view their own financial data
- Agency roles can view agency-wide financials
- Only SUPER_ADMIN can view platform financials

### Data Export Permissions
- SUPER_ADMIN: Can export all data
- AGENCY_OWNER: Can export agency data
- AGENCY_ADMIN: Can export agency data (limited)
- Others: Can only export own data

### Audit Trail Access
- SUPER_ADMIN: Full audit trail access
- AGENCY_OWNER: Agency audit trail
- Others: Own actions only

## Implementation Status

### Completed
- [x] Frontend route protection with RoleProtectedRoute
- [x] Navigation menu filtering by role
- [x] Basic RoleChecker in backend
- [x] User endpoint role filtering

### To Be Implemented
- [ ] Complete backend endpoint role checks
- [ ] WebSocket authentication and role checks
- [ ] API key scoping by role
- [ ] Audit trail role filtering
- [ ] Report access control
- [ ] ML endpoint restrictions
- [ ] Bulk operation permissions
- [ ] Cross-agency data isolation

## Security Considerations

1. **Default Deny**: All endpoints should deny access by default
2. **Explicit Allow**: Permissions must be explicitly granted
3. **Least Privilege**: Users get minimum required permissions
4. **Agency Isolation**: Strict data isolation between agencies
5. **Audit Everything**: All access attempts should be logged
6. **Token Scoping**: JWT tokens should include role and agency
7. **Regular Review**: Permissions should be reviewed quarterly

## Testing Matrix

Each role should be tested for:
1. Can access allowed endpoints
2. Cannot access forbidden endpoints
3. Data is properly filtered by agency/role
4. UI shows only permitted features
5. Bulk operations respect permissions
6. Reports show only allowed data
7. WebSocket connections are properly authenticated

---

This plan serves as the authoritative source for all permission decisions in the Agency Dark platform.