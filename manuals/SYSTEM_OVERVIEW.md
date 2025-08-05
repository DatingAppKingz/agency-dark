# Agency Dark - Comprehensive System Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [User Roles & Permissions](#user-roles--permissions)
3. [Feature Overview by Role](#feature-overview-by-role)
4. [Module Descriptions](#module-descriptions)
5. [Getting Started](#getting-started)

## System Overview

Agency Dark is a comprehensive platform designed for managing modeling agencies and their talent. It provides tools for user management, model oversight, analytics, financial tracking, and communication - all within a secure, role-based environment.

### Key Features
- **Multi-tenant Architecture**: Supports multiple agencies with isolated data
- **Role-based Access Control**: Six distinct user roles with specific permissions
- **Real-time Analytics**: Track performance metrics and insights
- **Financial Management**: Handle payouts, transactions, and revenue tracking
- **Model Management**: Comprehensive tools for managing model profiles and content
- **Communication Tools**: Built-in chat and messaging systems
- **ML-powered Insights**: Advanced analytics and predictions

## User Roles & Permissions

### 1. Super Admin (Platform Administrator)
**Purpose**: Complete control over the entire platform across all agencies

**Access**:
- ✅ All platform features
- ✅ All agencies' data
- ✅ System configuration
- ✅ User management across all agencies
- ✅ Platform-wide analytics
- ✅ Financial oversight

**Cannot**:
- ❌ Nothing - has full access

### 2. Agency Owner
**Purpose**: Complete control over their specific agency

**Access**:
- ✅ All features within their agency
- ✅ User management for their agency
- ✅ Financial management
- ✅ Model management
- ✅ Agency settings
- ✅ Analytics for their agency

**Cannot**:
- ❌ Access other agencies' data
- ❌ Platform-wide settings
- ❌ Super admin functions

### 3. Agency Admin
**Purpose**: Manage day-to-day operations of the agency

**Access**:
- ✅ User management (except owner)
- ✅ Model management
- ✅ View analytics
- ✅ Manage content
- ✅ Communication tools

**Cannot**:
- ❌ Financial settings
- ❌ Agency configuration
- ❌ Delete agency owner

### 4. Model
**Purpose**: Manage their own profile and content

**Access**:
- ✅ Own profile management
- ✅ Content upload/management
- ✅ View own analytics
- ✅ Chat with assigned chatters
- ✅ View own earnings

**Cannot**:
- ❌ Access other models' data
- ❌ Agency management features
- ❌ User management

### 5. Chatter
**Purpose**: Communicate on behalf of models

**Access**:
- ✅ Chat interface
- ✅ Assigned models' conversations
- ✅ Basic analytics for conversations

**Cannot**:
- ❌ Model profile editing
- ❌ Financial data
- ❌ User management

### 6. Agency Member
**Purpose**: Basic agency access for support staff

**Access**:
- ✅ View agency dashboard
- ✅ Basic reports
- ✅ Limited analytics

**Cannot**:
- ❌ Manage users
- ❌ Edit content
- ❌ Financial access

## Feature Overview by Role

### Super Admin Features

#### User Management
- **Location**: Navigation → User Management
- **Features**:
  - View all users across all agencies
  - Group users by agency or role
  - Search and filter capabilities
  - User statistics dashboard
  - Create/edit/delete any user
  - Assign roles and permissions

#### Agencies Management
- **Location**: Navigation → Agencies
- **Features**:
  - Create new agencies
  - Edit agency settings
  - View agency statistics
  - Manage agency owners
  - Enable/disable agencies

#### Platform Analytics
- **Location**: Navigation → Analytics
- **Features**:
  - Platform-wide metrics
  - Revenue tracking
  - User growth charts
  - Performance indicators
  - Custom report generation

### Agency Owner/Admin Features

#### Model Overview
- **Location**: Navigation → Model Overview
- **Features**:
  - View all models in agency
  - Model performance metrics
  - Profile completion tracking
  - Quick actions (edit, message, view)
  - Add new models

#### Users Management (Agency Level)
- **Location**: Navigation → Users
- **Features**:
  - Manage agency staff
  - Assign chatters to models
  - Role management
  - Activity tracking

#### Financial Dashboard
- **Location**: Navigation → Financial
- **Features**:
  - Revenue overview
  - Payout management
  - Transaction history
  - Commission settings
  - Financial reports

### Model Features

#### Profile Dashboard
- **Location**: Automatic redirect to profile
- **Features**:
  - Profile editing
  - Content management
  - Performance metrics
  - Earnings overview
  - Subscriber management

#### Content Management
- **Features**:
  - Upload photos/videos
  - Schedule posts
  - View engagement metrics
  - Manage pricing

#### Analytics
- **Features**:
  - Earnings trends
  - Subscriber growth
  - Content performance
  - Engagement rates

### Chatter Features

#### Chat Dashboard
- **Location**: Navigation → Chat
- **Features**:
  - Multi-conversation management
  - Quick responses/templates
  - Conversation history
  - Performance tracking

## Module Descriptions

### 1. Dashboard Module
The main landing page after login, customized per user role:
- **Classic View**: Role-specific widgets and metrics
- **Custom View**: Drag-and-drop customizable dashboard

### 2. User Management Module
Comprehensive user administration:
- User creation with email invitation
- Bulk operations (for authorized roles)
- Role assignment
- Activity monitoring
- Access control

### 3. Model Management Module
Complete model lifecycle management:
- Onboarding process
- Profile management
- Content oversight
- Performance tracking
- Earnings management

### 4. Analytics Module
Data-driven insights:
- Real-time metrics
- Historical trends
- Predictive analytics
- Custom reports
- Export capabilities

### 5. Financial Module
Complete financial oversight:
- Revenue tracking
- Payout processing
- Commission management
- Tax reporting
- Transaction history

### 6. Communication Module
Integrated messaging system:
- Direct messages
- Broadcast messages
- Chat management
- Response templates
- Performance metrics

### 7. ML Insights Module
Advanced analytics powered by machine learning:
- Content recommendations
- Optimal posting times
- Subscriber predictions
- Churn analysis
- Revenue forecasting

### 8. Settings Module
System configuration:
- Profile settings
- Agency settings (owners/admins)
- API key management
- Webhook configuration
- Security settings

## Getting Started

### First Login
1. Navigate to the platform URL
2. Enter credentials:
   - Email: [provided by administrator]
   - Password: [provided by administrator]
3. Complete any required profile setup
4. Explore your role-specific dashboard

### Navigation
- **Top Navigation Bar**: Quick access to main modules
- **User Menu** (top right): Profile, settings, logout
- **Dashboard Toggle**: Switch between Classic and Custom views

### Common Tasks

#### For Admins: Adding a New Model
1. Navigate to Model Overview
2. Click "Add New Model"
3. Fill in model details
4. Assign chatters (optional)
5. Set commission rates
6. Send invitation email

#### For Models: Uploading Content
1. From dashboard, access Content Management
2. Click "Upload Content"
3. Select files (photos/videos)
4. Add descriptions and tags
5. Set pricing (if applicable)
6. Schedule or publish immediately

#### For Chatters: Managing Conversations
1. Open Chat Dashboard
2. View assigned models' conversations
3. Respond to messages
4. Use templates for common responses
5. Track response times and metrics

### Best Practices
1. **Security**: Never share login credentials
2. **Data Privacy**: Only access data relevant to your role
3. **Regular Updates**: Keep profile information current
4. **Communication**: Use platform messaging for all work communication
5. **Reporting**: Report any issues to agency admin immediately

### Support
- **Technical Issues**: Contact your agency administrator
- **Platform Issues**: Agency owners can contact platform support
- **Training**: Request role-specific training from your supervisor