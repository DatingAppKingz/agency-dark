# AgencyDark Requirements Questions

## 1. Business Model & Core Features

# What are the primary services agencies provide to OnlyFans models?
- System has to be sort of a wrapper around Inflow and https://onlyfansapi.com functionalities, also with possibility for chatter to claim certain fan and block it in a way that a different chatter will not be able to claim particular user (permanently or during the time of particular chatter's work - that's open to discussion)
# What metrics/KPIs do agencies track (revenue share, content performance, subscriber growth)?
- In AgencyDark, we want to expose for the models and their managers clear indicators metrics and KPIs to grow their business: 1.1) Popularity of film categories, 1.2) Popularity of particular films, 2) Linear charts: 2.1) Amount of subscribers as a linear chart Y axis - subscribers, X axis - time, 2.2) Amount of non-paying fans as a linear chart Y axis - fans, X axis - time, 2.3.1) Income in time - Y axis - money, X axis - time, 2.3.2.) Income from subscriptions in time - Y axis - money, X axis - time, 2.3.3) - Income from tips in time - Y axis money, X axis time, 2.3.4) Income from PPV films in time - Y axis money, X axis time. 3) Income from particular user(s) in time - Y axis - money, X axis - time. Ad. 3) - this chart has to be configurable in a way that user may see up to 10 users on a chart simultaneously (different colors for lines)
# How does billing work (agency subscriptions, model payments, commission structures)?
- We take comissions from the content creators, and our pricing model includes three stages: 1) 0-5000 paying subscribers; we take 70%, 2) 5001 - 10000 paying subscribers; we take 65%, if amount of paying subscribers is above 10000 the we take 60 %.
# What reporting/analytics are critical for agencies and models?
- Can't respond to that question right now, it's up to be discussed.

## 2. Inflow Integration
# What specific Inflow API endpoints will we wrap?
- All of them for now
# Which features remain Inflow-dependent vs built natively?
- All features provided by Inflow will be inflow-dependent
# Which features remain https://onlyfansapi.com/ dependent vs built natively?
- All features provided by onlyfansapi will be onlyfansapi-dependent
# How do we handle API rate limits and data synchronization?
- There are no api rate limits for Inflow or Onlyfansapi as far as i know, so we should simply stick to api calls on request (once particular user is logging in, all data has to be synchronized) - the exception for that is chatter account where chatters has to have option to be notified immediatelly once particular user sends a message - if they claimed that user - if they didn't, they should have notifications about all messages being sent by unclaimed potential fans. 
# What's the migration path from wrapper to standalone?
- There is no such a path for now, the MVP is a wrapper around Inflow and Onlyfansapi.

## 3. User Roles & Permissions
# Beyond the defined roles (super_admin, agency_owner, agency_admin, model, chatter), what specific permissions does each need?
- 1) super_admin - All system functionalities, only they will have readonly access to the chat, 2) agency_owner - All functionalities in a context of the models in their agencies (CRUD), only they will have readonly access to the chat, 3) agency_admin - All functionalities in a context of the models (CRUD), but only they will have readonly access to the chat, 4) Model - All functionalities in context of particlar model's account - CRUD for content, full access to analytics and content creation, inspection of commentaries, and private messages, can claim particular fan (even if chatter did it earlier) and block him from receiving messages from other chatters. 5) Chatter - Full access to the particular model's commentaries and private messages. Can claim particular fan in a way that only they will be able to message them, and a claimed user will be visually distinguished from the others in the comments section for films.

# Can agencies customize role permissions?
- super_admin can decide, that particular agency will be able to customize the role permissions or not.

# How do models interact with multiple agencies?
- Models has many-to-one relation with agency, particular model can be cooperating only with one agency at a time.

# Do we need sub-agencies or team structures?
- Not for now, we just need a space for that in case this will become business requirement. System has to be designed in a modular way which will enable that.

## 4. Model Management
# How are models onboarded to agencies?
- Onboarding is quite simple - signing the contract and creating an account.
# What data is tracked per model (profiles, content, earnings, schedules)?
- In AgencyDark, we want to expose for the models and their managers clear indicators metrics and KPIs to grow their business: 1.1) Popularity of film categories, 1.2) Popularity of particular films, 2) Linear charts: 2.1) Amount of subscribers as a linear chart Y axis - subscribers, X axis - time, 2.2) Amount of non-paying fans as a linear chart Y axis - fans, X axis - time, 2.3.1) Income in time - Y axis - money, X axis - time, 2.3.2.) Income from subscriptions in time - Y axis - money, X axis - time, 2.3.3) - Income from tips in time - Y axis money, X axis time, 2.3.4) Income from PPV films in time - Y axis money, X axis time. 3) Income from particular user(s) in time - Y axis - money, X axis - time. Ad. 3) - this chart has to be configurable in a way that user may see up to 10 users on a chart simultaneously (different colors for lines)

# How is content managed (storage, approval workflows, posting schedules)?
- In a same way as Onlyfans does

# What communication features between agencies and models?
- For MVP there's no need for communication between agencies and models.

## 5. Financial Features
# Payment processing requirements (Stripe, PayPal, crypto)?
- Crypto

# How are commissions calculated and distributed?
- 1) 0-5000 paying subscribers; we take 70%, 2) 5001 - 10000 paying subscribers; we take 65%, if amount of paying subscribers is above 10000 the we take 60 %.
# Invoice generation and expense tracking?
- Invoice generation is desired, but only that for MVP
# Multi-currency support needed?
- Multi Cryptocurrencies support needed.

## 6. White-Label Requirements
# Customization depth (colors, logos, custom domains)?
- Agency's logo, Model's logo, colors: light or dark theme (day & night), no custom domains for now, but support for those can be used in the future.
# Feature toggles per agency?
- Not for MVP
# Custom onboarding flows?
- Not for MVP
# Branded mobile apps planned?
- No

## 7. Technical Constraints
# Expected scale (agencies, models, concurrent users)?
- System has to be as fast as possible, we aim high
# Data retention policies?
- As long as we will cooperate with particular agency we will maintain all data, when cooperation will end (after downtime period), data will be wiped out.
# Compliance requirements (GDPR, age verification, content policies)?
- Only GDPR applicable for MVP
# Third-party integrations beyond Inflow?
- For sure we'll need Onlyfansapi, I don't know how about the rest of them

## 8. Priority Features
# What's the MVP feature set for initial launch?
- All functionalities Inflow and Onlyfansapi exposes has to be implemented, if both will provide certain feature, then Onlyfansapi will be used.
# Which features differentiate from competitors?
- Don't have anything in mind
# Any features explicitly out of scope?
- Don't have anything in mind