# Super Admin User Manual

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [User Management](#user-management)
5. [Agency Management](#agency-management)
6. [Platform Analytics](#platform-analytics)
7. [Financial Oversight](#financial-oversight)
8. [System Settings](#system-settings)
9. [Troubleshooting](#troubleshooting)

## Introduction

As a Super Admin, you have complete control over the Agency Dark platform. This manual will guide you through all available features and best practices for platform management.

## Getting Started

### First Login
1. Navigate to the platform URL
2. Enter your super admin credentials:
   - Email: admin@agency.com
   - Password: [provided securely]
3. Enable two-factor authentication (recommended)

### Navigation Overview
- **Top Navigation**: Quick access to all modules
- **User Management**: Platform-wide user administration
- **Model Overview**: All models across all agencies
- **Analytics**: Platform-wide metrics
- **Settings**: System configuration

## Dashboard Overview

### Classic View
Your dashboard displays:
- **Total Users**: Platform-wide user count
- **Active Agencies**: Number of active agencies
- **Revenue Overview**: Platform total revenue
- **Recent Activity**: Latest platform events
- **System Health**: Server and service status

### Switching Views
- Click the toggle button (top right of dashboard)
- Choose between Classic and Custom views
- Custom view allows widget customization

## User Management

### Accessing User Management
**Navigation → User Management**

### Features Overview
1. **User Statistics**
   - Total users by role
   - Active vs inactive users
   - User growth trends

2. **View Modes**
   - **By Agency**: Users grouped by their agencies
   - **By Role**: Users grouped by their roles

### Managing Users

#### Creating a New User
1. Click "Add User" button
2. Fill in required fields:
   - Email (required)
   - Full Name (required)
   - Role (required)
   - Agency (if applicable)
3. Set initial password or send invitation
4. Click "Create User"

#### Editing Users
1. Find user via search or browse
2. Click on user row
3. Modify fields as needed:
   - Role changes
   - Agency assignment
   - Active/Inactive status
4. Save changes

#### Bulk Operations
1. Select multiple users (checkbox)
2. Choose action:
   - Activate/Deactivate
   - Change role
   - Export data
   - Delete (use with caution)

### Search and Filters
- **Search bar**: Search by name or email
- **Role filter**: Filter by specific roles
- **Status filter**: Active/Inactive/Verified
- **Agency filter**: Users from specific agencies

## Agency Management

### Accessing Agencies
**Navigation → Agencies**

### Creating New Agency
1. Click "Create Agency"
2. Enter agency details:
   - Agency Name (required)
   - Owner Email (required)
   - Commission Rate
   - Payment Details
3. Configure settings:
   - Branding options
   - Feature access
   - User limits
4. Create agency

### Managing Existing Agencies

#### Agency Overview
Each agency card shows:
- Total users
- Active models
- Monthly revenue
- Status (Active/Suspended)

#### Agency Settings
1. Click on agency name
2. Available options:
   - Edit details
   - Manage owner
   - View analytics
   - Financial settings
   - Suspend/Activate

### Agency Analytics
- User growth
- Revenue trends
- Model performance
- Activity metrics

## Platform Analytics

### Accessing Analytics
**Navigation → Analytics**

### Key Metrics
1. **Platform Overview**
   - Total revenue
   - User growth
   - Active users
   - Engagement rates

2. **Financial Metrics**
   - Revenue by agency
   - Commission earned
   - Payment processing
   - Refund rates

3. **User Metrics**
   - New registrations
   - Active users by role
   - Login frequency
   - Session duration

4. **Performance Metrics**
   - Server response times
   - API usage
   - Error rates
   - System uptime

### Generating Reports
1. Select report type
2. Choose date range
3. Apply filters (optional)
4. Generate report
5. Export options:
   - PDF
   - CSV
   - Excel

## Financial Oversight

### Accessing Financial Module
**Navigation → Financial**

### Platform Financials
1. **Revenue Dashboard**
   - Total platform revenue
   - Revenue by agency
   - Growth trends
   - Forecasting

2. **Commission Management**
   - Platform commission rates
   - Agency-specific rates
   - Automatic calculations
   - Payout schedules

3. **Transaction Monitoring**
   - All platform transactions
   - Filter by agency/user
   - Transaction details
   - Dispute management

### Payout Management
1. **Scheduled Payouts**
   - View upcoming payouts
   - Modify schedules
   - Hold/Release payments
   - Bulk processing

2. **Manual Payouts**
   - Process individual payouts
   - Emergency payments
   - Refunds/Adjustments

## System Settings

### Accessing Settings
**User Menu → Platform Settings**

### Configuration Options

#### General Settings
- Platform name/branding
- Default timezone
- Language options
- Email templates

#### Security Settings
- Password policies
- Session timeouts
- IP restrictions
- 2FA requirements

#### API Management
- Generate API keys
- Set rate limits
- Monitor usage
- Revoke access

#### Integration Settings
- Payment processors
- Email services
- Storage providers
- Analytics tools

### Webhook Configuration
1. Navigate to Settings → Webhooks
2. Add webhook endpoint
3. Select events to monitor
4. Configure authentication
5. Test webhook

## Troubleshooting

### Common Issues

#### User Cannot Login
1. Check user status (active/verified)
2. Verify agency status
3. Check password reset requests
4. Review login attempts

#### Agency Issues
1. Verify agency is active
2. Check owner account
3. Review settings
4. Check payment status

#### Performance Issues
1. Check system health dashboard
2. Review error logs
3. Monitor API usage
4. Check server resources

### System Maintenance

#### Regular Tasks
- Weekly: Review error logs
- Monthly: User audit
- Quarterly: Performance review
- Yearly: Security audit

#### Backup Procedures
1. Automatic backups run daily
2. Access backup history
3. Test restore procedures
4. Document recovery plans

### Getting Help
- **Documentation**: /docs/admin
- **Support Ticket**: support@agencydark.com
- **Emergency**: [24/7 hotline number]

## Best Practices

### Security
1. Use strong passwords
2. Enable 2FA
3. Regular security audits
4. Monitor suspicious activity
5. Keep audit logs

### User Management
1. Regular user audits
2. Remove inactive users
3. Update roles promptly
4. Document changes
5. Communicate updates

### Performance
1. Monitor system metrics
2. Plan for scaling
3. Regular maintenance
4. Update documentation
5. Train agency admins

### Communication
1. Announce planned maintenance
2. Document known issues
3. Provide regular updates
4. Maintain FAQ
5. Gather feedback