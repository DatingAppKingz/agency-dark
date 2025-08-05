# Test Data Guide

This guide contains all test users and data for the Agency Dark platform. Use this to login as different user types and explore the system.

## Important Note
**ALL USERS USE THE SAME PASSWORD: `admin123`**

Passwords are stored in plain text for testing purposes only.

## Test User Credentials

### Platform Level Users

#### Super Admin
- **Email**: admin@agency.com
- **Password**: admin123
- **Role**: SUPER_ADMIN
- **Purpose**: Platform administration, manage all agencies

### Agency 1: Elite Models Agency

#### Agency Owner
- **Email**: owner@elitemodels.com
- **Password**: admin123
- **Role**: AGENCY_OWNER
- **Agency**: Elite Models Agency
- **Purpose**: Complete agency control

#### Agency Admin
- **Email**: admin@elitemodels.com
- **Password**: admin123
- **Role**: AGENCY_ADMIN
- **Agency**: Elite Models Agency
- **Purpose**: Day-to-day agency management

#### Models
1. **Sarah Johnson** (Top Performer)
   - **Email**: sarah@elitemodels.com
   - **Password**: admin123
   - **Stage Name**: SarahJ
   - **Role**: MODEL
   
2. **Emma Davis** (Mid-tier)
   - **Email**: emma@elitemodels.com
   - **Password**: admin123
   - **Stage Name**: EmmaD
   - **Role**: MODEL

3. **Lisa Brown** (New Model)
   - **Email**: lisa@elitemodels.com
   - **Password**: admin123
   - **Stage Name**: LisaB
   - **Role**: MODEL

#### Chatters
1. **John Smith** (Senior Chatter)
   - **Email**: john@elitemodels.com
   - **Password**: admin123
   - **Role**: CHATTER
   - **Assigned to**: Sarah, Emma

2. **Mike Wilson** (Junior Chatter)
   - **Email**: mike@elitemodels.com
   - **Password**: admin123
   - **Role**: CHATTER
   - **Assigned to**: Lisa

#### Agency Member
- **Email**: support@elitemodels.com
- **Password**: admin123
- **Role**: AGENCY_MEMBER
- **Purpose**: Support staff with view-only access

### Agency 2: Premium Talent Management

#### Agency Owner
- **Email**: owner@premiumtalent.com
- **Password**: admin123
- **Role**: AGENCY_OWNER
- **Agency**: Premium Talent Management

#### Models
1. **Jessica White**
   - **Email**: jessica@premiumtalent.com
   - **Password**: admin123
   - **Stage Name**: JessicaW
   - **Role**: MODEL

2. **Ashley Green**
   - **Email**: ashley@premiumtalent.com
   - **Password**: admin123
   - **Stage Name**: AshleyG
   - **Role**: MODEL

#### Chatter
- **Email**: alex@premiumtalent.com
- **Password**: admin123
- **Role**: CHATTER
- **Assigned to**: Jessica, Ashley

### Agency 3: Rising Stars Agency (Small Agency)

#### Agency Owner
- **Email**: owner@risingstars.com
- **Password**: admin123
- **Role**: AGENCY_OWNER
- **Agency**: Rising Stars Agency

#### Model
- **Email**: sophia@risingstars.com
- **Password**: admin123
- **Stage Name**: SophiaR
- **Role**: MODEL

## Test Data Overview

### Agencies
1. **Elite Models Agency**
   - 6 staff members
   - 3 models
   - 2 chatters
   - High revenue agency

2. **Premium Talent Management**
   - 3 staff members
   - 2 models
   - 1 chatter
   - Medium revenue agency

3. **Rising Stars Agency**
   - 2 staff members
   - 1 model
   - Small/startup agency

### Financial Data
- Transaction history for past 6 months
- Various payout records
- Commission structures set up
- Revenue data showing growth trends

### Content & Analytics
- Mock content metrics for models
- Subscriber counts
- Engagement data
- Performance history

### Communication Data
- Sample chat conversations
- Message templates
- Response time metrics

## Quick Login Reference

| Role | Email | Password | Agency |
|------|-------|----------|---------|
| Super Admin | admin@agency.com | admin123 | Platform |
| Agency Owner | owner@elitemodels.com | admin123 | Elite Models |
| Agency Admin | admin@elitemodels.com | admin123 | Elite Models |
| Model | sarah@elitemodels.com | admin123 | Elite Models |
| Chatter | john@elitemodels.com | admin123 | Elite Models |
| Member | support@elitemodels.com | admin123 | Elite Models |

## Testing Scenarios

### As Super Admin
1. View all agencies
2. Check platform-wide analytics
3. Manage users across agencies
4. Review financial overview

### As Agency Owner
1. Manage your agency's models
2. Review agency finances
3. Add new staff
4. Configure agency settings

### As Model
1. View your profile and analytics
2. Check earnings
3. Review performance metrics
4. Access chat messages

### As Chatter
1. Manage assigned model conversations
2. Use chat templates
3. Track response metrics

### As Agency Member
1. View agency dashboard
2. Access limited reports
3. No edit capabilities

## Database Seeding

To populate the database with this test data:

1. Navigate to `/manuals/` directory
2. Run: `psql -U mariuszbudzisz -d agencydark_dev -f seed_test_data.sql`
3. All test users and data will be created

## Notes

- **ALL PASSWORDS ARE `admin123`** - Same password for every user for testing convenience
- Passwords are stored in plain text (not hashed) for testing purposes only
- Financial data uses realistic but fictional amounts
- Dates are relative to maintain relevance
- Email addresses use test domains
- This is TEST DATA ONLY - never use plain text passwords in production!