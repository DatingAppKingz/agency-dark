# Agency Dark Feature Guides

## Table of Contents
1. [Dashboard Features](#dashboard-features)
2. [User Management System](#user-management-system)
3. [Model Management System](#model-management-system)
4. [Financial System](#financial-system)
5. [Analytics System](#analytics-system)
6. [Communication System](#communication-system)
7. [ML Insights](#ml-insights)
8. [API Integration](#api-integration)

## Dashboard Features

### Classic vs Custom Dashboard

#### Classic Dashboard
**Purpose**: Role-specific, pre-configured layouts optimized for each user type

**Features**:
- Pre-arranged widgets
- Role-specific metrics
- Optimized information hierarchy
- Quick access to common tasks

**Best For**: Users who want a ready-to-use interface

#### Custom Dashboard
**Purpose**: Fully customizable workspace

**Features**:
- Drag-and-drop widgets
- Resizable components
- Add/remove widgets
- Save multiple layouts
- Share layouts (admins)

**How to Customize**:
1. Switch to Custom View
2. Click "Edit Layout"
3. Drag widgets to reposition
4. Click "+" to add widgets
5. Click "x" to remove widgets
6. Save layout

### Dashboard Widgets

#### Available Widgets by Role

**All Roles**:
- Recent Activity
- Quick Stats
- Notifications
- Calendar

**Admin/Owner**:
- User Growth
- Revenue Metrics
- Model Performance
- System Health

**Models**:
- Earnings Today
- New Subscribers
- Content Performance
- Messages

**Chatters**:
- Active Conversations
- Response Time
- Performance Metrics

## User Management System

### User Creation Flow

#### Email Invitation System
1. **Admin initiates**: Add User → Enter email
2. **System sends**: Invitation with temporary credentials
3. **User receives**: Email with setup link
4. **First login**: Set password, complete profile
5. **Activation**: Account becomes active

#### Bulk User Import
1. Prepare CSV file:
   ```
   email,full_name,role,agency_id
   user1@example.com,John Doe,MODEL,agency-123
   user2@example.com,Jane Smith,CHATTER,agency-123
   ```
2. Navigate to Users → Import
3. Upload CSV file
4. Review and confirm
5. System sends invitations

### Permission System

#### Role Hierarchy
```
Super Admin
    ↓
Agency Owner
    ↓
Agency Admin
    ↓
Model / Chatter / Member
```

#### Permission Matrix
| Feature | Super Admin | Owner | Admin | Model | Chatter | Member |
|---------|------------|-------|--------|-------|----------|---------|
| View all agencies | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Manage agency users | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Financial access | ✅ | ✅ | ❌ | Own | ❌ | ❌ |
| Model profiles | ✅ | ✅ | ✅ | Own | View | View |
| Chat system | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |

### User Search and Filters

#### Advanced Search
- **Text Search**: Name, email, username
- **Role Filter**: Single or multiple roles
- **Status Filter**: Active, Inactive, Pending
- **Date Filters**: Created, Last login
- **Agency Filter**: For multi-agency view

#### Saved Searches
1. Apply filters
2. Click "Save Search"
3. Name the search
4. Access from dropdown

## Model Management System

### Model Onboarding Process

#### Step-by-Step Flow
1. **Invitation**
   - Agency sends invite
   - Model receives email
   - Creates account

2. **Profile Setup**
   - Basic information
   - Profile photos
   - Bio and interests
   - Verification documents

3. **Content Guidelines**
   - Review policies
   - Content requirements
   - Pricing guidelines
   - Accept terms

4. **Initial Content**
   - Upload first content
   - Set pricing
   - Learn platform

5. **Activation**
   - Agency reviews
   - Approves profile
   - Model goes live

### Model Performance Tracking

#### Key Metrics
1. **Engagement Metrics**
   - Content views
   - Likes/comments ratio
   - Share rate
   - Save rate

2. **Financial Metrics**
   - Daily earnings
   - Average transaction
   - Revenue per subscriber
   - Growth rate

3. **Activity Metrics**
   - Login frequency
   - Content upload rate
   - Response time
   - Active hours

### Content Management

#### Content Approval Workflow
1. Model uploads content
2. System checks:
   - File format
   - Size limits
   - Basic compliance
3. Agency review (optional)
4. Content goes live
5. Performance tracking begins

#### Bulk Content Operations
- **Bulk Upload**: Up to 100 files
- **Bulk Edit**: Tags, pricing, visibility
- **Bulk Schedule**: Plan content calendar
- **Bulk Archive**: Seasonal content

## Financial System

### Commission Structure

#### Setting Up Commissions
1. **Platform Level** (Super Admin)
   - Base platform fee: X%
   - Payment processing: Y%

2. **Agency Level** (Owner)
   - Agency commission: Z%
   - Model receives: 100-(X+Y+Z)%

3. **Special Rates**
   - Promotional periods
   - Performance bonuses
   - Loyalty rewards

#### Commission Calculation
```
Subscriber pays: $100
Platform fee (5%): -$5
Payment processing (3%): -$3
Agency commission (20%): -$20
Model receives: $72
```

### Payout System

#### Automated Payouts
1. **Schedule Setup**
   - Frequency: Daily/Weekly/Monthly
   - Processing day
   - Minimum threshold
   - Hold period

2. **Processing Flow**
   - Calculate earnings
   - Apply commissions
   - Check minimums
   - Process payment
   - Send confirmation

#### Manual Payouts
- Emergency payments
- Adjustments
- Bonuses
- Refunds

### Financial Reports

#### Available Reports
1. **Revenue Reports**
   - Gross revenue
   - Net revenue
   - By model
   - By content type

2. **Commission Reports**
   - Platform earnings
   - Agency earnings
   - Model earnings
   - Adjustments

3. **Tax Reports**
   - 1099 preparation
   - Income summaries
   - Expense tracking

## Analytics System

### Real-time Analytics

#### Live Dashboard
- Active users now
- Current revenue
- Active conversations
- Content being viewed
- System performance

#### Real-time Alerts
- Revenue milestones
- Unusual activity
- System issues
- Performance drops

### Historical Analytics

#### Trend Analysis
1. **Time Periods**
   - Hourly
   - Daily
   - Weekly
   - Monthly
   - Custom range

2. **Comparison Tools**
   - Period over period
   - Year over year
   - Vs. average
   - Vs. goals

### Custom Reports

#### Report Builder
1. Select metrics
2. Choose dimensions
3. Apply filters
4. Set date range
5. Choose visualization
6. Save/Export

#### Scheduled Reports
- Daily summaries
- Weekly performance
- Monthly financials
- Custom schedules

## Communication System

### Chat System Architecture

#### Message Types
1. **Direct Messages**
   - One-on-one
   - Paid messages
   - Media sharing
   - Read receipts

2. **Broadcast Messages**
   - To all subscribers
   - To segments
   - Scheduled broadcasts
   - Performance tracking

### Chatter Management

#### Assignment System
1. Models assigned to chatters
2. Workload balancing
3. Shift scheduling
4. Performance tracking

#### Chatter Tools
- Response templates
- Quick replies
- Translation tools
- Performance dashboard

### Communication Analytics

#### Metrics Tracked
- Response time
- Conversation length
- Revenue per conversation
- Customer satisfaction
- Chatter performance

## ML Insights

### Predictive Analytics

#### Available Predictions
1. **Revenue Forecasting**
   - Next day/week/month
   - Seasonal trends
   - Growth projections

2. **Churn Prediction**
   - At-risk subscribers
   - Retention probability
   - Intervention recommendations

3. **Content Recommendations**
   - Optimal posting times
   - Content type suggestions
   - Pricing recommendations

### How ML Insights Work

#### Data Collection
- User behavior
- Content performance
- Financial data
- Engagement metrics

#### Model Training
- Continuous learning
- Pattern recognition
- Anomaly detection
- Prediction refinement

#### Actionable Insights
- Specific recommendations
- Confidence scores
- Impact estimates
- A/B test suggestions

## API Integration

### API Key Management

#### Creating API Keys
1. Navigate to Settings → API
2. Click "Generate Key"
3. Set permissions:
   - Read only
   - Write access
   - Specific endpoints
4. Set rate limits
5. Copy key (shown once)

#### API Security
- Keys tied to IP addresses
- Rate limiting
- Request signing
- Audit logging

### Webhook System

#### Setting Up Webhooks
1. Go to Settings → Webhooks
2. Add endpoint URL
3. Select events:
   - User events
   - Financial events
   - Content events
   - System events
4. Configure retry policy
5. Test webhook

#### Webhook Events
- `user.created`
- `user.updated`
- `model.content.uploaded`
- `payment.processed`
- `subscription.created`
- `subscription.cancelled`

### Integration Examples

#### Payment Processor Integration
```javascript
// Webhook handler example
app.post('/webhook/payment', (req, res) => {
  const event = req.body;
  
  switch(event.type) {
    case 'payment.succeeded':
      // Update user balance
      break;
    case 'payment.failed':
      // Notify user
      break;
  }
  
  res.sendStatus(200);
});
```

#### Analytics Integration
- Export to Google Analytics
- Send to data warehouse
- Custom analytics platforms
- Business intelligence tools

## Best Practices Summary

### Performance Optimization
1. Use batch operations
2. Schedule heavy tasks
3. Enable caching
4. Monitor API usage

### Security
1. Regular password updates
2. Enable 2FA
3. Review access logs
4. Audit permissions

### Data Management
1. Regular backups
2. Data retention policies
3. GDPR compliance
4. Export capabilities

### User Experience
1. Responsive design
2. Intuitive navigation
3. Help documentation
4. User feedback