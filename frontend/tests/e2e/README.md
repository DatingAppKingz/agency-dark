# E2E Tests

This directory contains end-to-end tests using Playwright.

## Test Structure

- `pages/` - Page Object Model classes for better test organization
- `*.spec.ts` - Test specification files

## Available Tests

1. **Authentication Flow** (`auth.spec.ts`)
   - Login/logout functionality
   - Session persistence
   - Password reset flow
   - Registration flow
   - CSRF protection

2. **Model Onboarding** (`model-onboarding.spec.ts`)
   - Creating new models
   - Complete onboarding workflow
   - Document upload and verification
   - Platform integration
   - Bulk operations

3. **Financial Workflow** (`financial-workflow.spec.ts`)
   - Transaction management
   - Payout requests
   - Payment method management
   - Financial reports
   - Commission management

4. **Chat Interaction** (`chat-interaction.spec.ts`)
   - Real-time messaging
   - File attachments
   - Message editing/deletion
   - Reactions
   - Conversation management

## Running Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run with UI mode (interactive)
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug

# Run specific test file
npm run test:e2e auth.spec.ts

# Use the helper script
./run-e2e-tests.sh
```

## Prerequisites

1. Backend must be running on http://localhost:8000
2. Frontend dev server on http://localhost:5173 (auto-started by tests)
3. Test fixtures in `tests/fixtures/` directory

## Test Data

Default test users:
- Admin: `admin@agency.com` / `admin123`
- Model: `model@example.com` / `model123`

## Debugging

- Screenshots are captured on failure
- Test traces available for failed tests
- View report: `npx playwright show-report`

## Best Practices

1. Use Page Object Model for maintainability
2. Keep tests independent and idempotent
3. Use data-testid attributes for reliable selectors
4. Clean up test data after tests
5. Use proper waits instead of fixed timeouts