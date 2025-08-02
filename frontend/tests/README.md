# AgencyDark Frontend Test Suite

## Test Structure

The test suite is organized into the following categories:

```
tests/
├── unit/                    # Unit tests for individual components and functions
│   ├── components/         # Component tests
│   │   ├── common/        # Common component tests (Toaster, etc.)
│   │   └── ui/            # UI component tests (Button, Input, Card, etc.)
│   ├── hooks/             # Custom hook tests
│   ├── services/          # Service layer tests
│   └── store/             # State management tests
├── integration/            # Integration tests for feature flows
├── e2e/                   # End-to-end tests for complete user journeys
└── utils/                 # Test utilities and helpers
    ├── setup.ts           # Jest setup and global mocks
    ├── test-server.ts     # MSW server configuration
    ├── handlers.ts        # API mock handlers
    ├── factories.ts       # Test data factories
    ├── test-utils.tsx     # Testing library utilities
    └── enhanced-test-utils.tsx  # Enhanced test utilities with providers
```

## Running Tests

### Run All Tests
```bash
npm test
```

### Run Tests in Watch Mode
```bash
npm test -- --watch
```

### Run Tests with Coverage
```bash
npm test -- --coverage
```

### Run Specific Test Files
```bash
# Run a specific test file
npm test -- tests/unit/components/ui/button.test.tsx

# Run all component tests
npm test -- tests/unit/components

# Run all integration tests
npm test -- tests/integration
```

### Run Sample Tests
```bash
./run-sample-tests.sh
```

## Test Categories

### Unit Tests
- **Components**: Test individual UI components in isolation
- **Hooks**: Test custom React hooks
- **Services**: Test service layer functions (API calls, utilities)
- **Store**: Test state management (Zustand stores)

### Integration Tests
- **Auth Flow**: Test complete authentication workflows
- **Media Upload**: Test file upload functionality
- **RBAC**: Test role-based access control
- **Multi-tenant**: Test multi-tenancy features
- **WebSocket**: Test real-time communication

### E2E Tests
- **User Journey**: Test complete user workflows from start to finish

## Test Utilities

### MSW (Mock Service Worker)
Used for mocking API endpoints during tests. Handlers are defined in `tests/utils/handlers.ts`.

### Test Data Factories
Located in `tests/utils/factories.ts`, these provide consistent test data generation.

### Enhanced Test Utils
The `enhanced-test-utils.tsx` file provides render functions with all necessary providers pre-configured.

## Writing New Tests

1. **Component Tests**: Use `enhanced-test-utils` for rendering with providers
2. **Service Tests**: Mock API calls using MSW
3. **Hook Tests**: Use `renderHook` from testing library
4. **Integration Tests**: Test complete features with real user interactions

## Known Limitations

- Full Vite compatibility requires using Vitest instead of Jest
- Some import.meta references are mocked in the setup file
- WebSocket tests may require additional setup for real-time features