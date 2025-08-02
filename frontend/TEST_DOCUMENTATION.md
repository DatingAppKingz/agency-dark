# AgencyDark Frontend Test Documentation

## Overview

This document provides comprehensive documentation for the test suite implemented for the AgencyDark frontend application. The test suite ensures code quality, prevents regressions, and serves as living documentation for the application's behavior.

## Test Infrastructure

### Testing Stack

- **Test Runner**: Jest
- **Testing Library**: React Testing Library
- **API Mocking**: MSW (Mock Service Worker)
- **User Interactions**: @testing-library/user-event
- **Component Testing**: Custom test utilities with all required providers

### Directory Structure

```
src/
├── __tests__/
│   ├── components/
│   │   ├── common/       # Common component tests
│   │   └── ui/           # UI component tests
│   ├── services/         # Service layer tests
│   ├── hooks/            # Custom hook tests
│   ├── store/            # State management tests
│   ├── integration/      # Integration tests
│   └── e2e/              # End-to-end tests
└── test-utils/           # Testing utilities and helpers
    ├── test-server.ts    # MSW server setup
    ├── handlers.ts       # API mock handlers
    ├── mock-factories.ts # Test data factories
    ├── test-helpers.ts   # Common test utilities
    └── enhanced-test-utils.tsx # Custom render with providers
```

## Test Categories

### 1. Unit Tests

#### UI Components
- **Button**: Various states, sizes, variants, loading states, icons
- **Input**: Text input, validation, disabled states, password visibility
- **Badge**: Different variants, sizes, with/without close button
- **Card**: Layout variations, clickable cards, nested cards
- **Select**: Dropdown functionality, keyboard navigation, groups
- **Switch**: Toggle states, form integration, accessibility
- **Tabs**: Tab switching, keyboard navigation, disabled tabs
- **Avatar**: Image loading, fallbacks, different sizes
- **Label**: Form association, accessibility, styling
- **ScrollArea**: Scrolling behavior, content overflow
- **DropdownMenu**: Menu items, checkboxes, radio groups, submenus
- **Toaster**: Toast notifications, auto-dismiss, positioning

#### Services
- **authService**: Login, logout, token management, registration
- **analyticsService**: Dashboard stats, charts, exports, error handling

#### Hooks
- **useAuth**: Authentication state, login/logout flows
- **useDebounce**: Value debouncing with configurable delay
- **useNotification**: Notification management, auto-dismiss

#### State Management
- **authStore**: Zustand store testing, state persistence

### 2. Integration Tests

- **Authentication Flow**: Complete login/logout process, protected routes
- **Media Upload**: File upload, drag & drop, progress tracking

### 3. End-to-End Tests

- **User Journey**: Complete workflow from login to task completion
- **Error Handling Journey**: Network errors, recovery flows
- **Role-Based Journey**: Different features based on user roles

## Testing Patterns

### 1. Component Testing Pattern

```typescript
describe('Component Name', () => {
  describe('Basic Rendering', () => {
    it('renders correctly', () => {
      render(<Component />);
      expect(screen.getByRole('...')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('handles user interaction', async () => {
      const user = userEvent.setup();
      render(<Component />);
      await user.click(screen.getByRole('button'));
      expect(...).toBe(...);
    });
  });

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(<Component />);
      expect(screen.getByRole('...')).toHaveAttribute('aria-label', '...');
    });
  });
});
```

### 2. Service Testing Pattern

```typescript
describe('Service Name', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('makes correct API call', async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: mockData });
    const result = await service.method();
    expect(mockedApiClient.get).toHaveBeenCalledWith('/endpoint');
    expect(result).toEqual(mockData);
  });

  it('handles errors gracefully', async () => {
    mockedApiClient.get.mockRejectedValueOnce(new Error('Network error'));
    await expect(service.method()).rejects.toThrow('Network error');
  });
});
```

### 3. Hook Testing Pattern

```typescript
describe('Hook Name', () => {
  it('returns expected value', () => {
    const { result } = renderHook(() => useHook());
    expect(result.current.value).toBe(expectedValue);
  });

  it('updates on action', () => {
    const { result } = renderHook(() => useHook());
    act(() => {
      result.current.action();
    });
    expect(result.current.value).toBe(newValue);
  });
});
```

## Test Utilities

### Mock Service Worker (MSW)

MSW intercepts network requests and provides consistent mock responses:

```typescript
// test-utils/handlers.ts
export const handlers = [
  rest.post('/api/auth/login', (req, res, ctx) => {
    return res(ctx.json({ token: 'mock-token' }));
  }),
];
```

### Mock Factories

Factories create consistent test data:

```typescript
// test-utils/mock-factories.ts
export const createMockUser = (overrides?: Partial<User>): User => ({
  id: '1',
  email: 'test@example.com',
  role: 'member',
  ...overrides,
});
```

### Enhanced Test Utils

Custom render function with all required providers:

```typescript
// test-utils/enhanced-test-utils.tsx
export const customRender = (ui: ReactElement, options?: CustomRenderOptions) => {
  return render(ui, {
    wrapper: AllTheProviders,
    ...options,
  });
};
```

## Best Practices

### 1. Test Organization
- Group related tests using `describe` blocks
- Use descriptive test names that explain the expected behavior
- Test one thing per test case

### 2. Accessibility Testing
- Always test keyboard navigation
- Verify ARIA attributes
- Check screen reader announcements

### 3. User Interactions
- Use `userEvent` over `fireEvent` for more realistic interactions
- Test complete user workflows, not just individual actions
- Verify visual feedback (loading states, error messages)

### 4. Async Testing
- Use `waitFor` for async operations
- Test loading, success, and error states
- Verify cleanup and cancellation

### 5. Test Data
- Use factories for consistent test data
- Avoid hardcoding values in tests
- Test edge cases (empty data, large datasets)

## Running Tests

### Commands

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm test -- --coverage

# Run specific test file
npm test Button.test.tsx

# Run tests matching pattern
npm test -- --testNamePattern="should handle click"
```

### Coverage Goals

- Statements: 80%+
- Branches: 75%+
- Functions: 80%+
- Lines: 80%+

## Debugging Tests

### 1. Debug Output

```typescript
// Use screen.debug() to see current DOM
screen.debug();

// Log specific elements
screen.debug(screen.getByRole('button'));
```

### 2. Testing Playground

```typescript
// Get query suggestions
screen.logTestingPlaygroundURL();
```

### 3. Async Debugging

```typescript
// Use waitFor with custom timeout
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
}, { timeout: 5000 });
```

## Common Issues and Solutions

### 1. Act Warnings

**Problem**: "Warning: An update to Component inside a test was not wrapped in act(...)"

**Solution**: Wrap state updates in `act()`:
```typescript
act(() => {
  result.current.updateState();
});
```

### 2. Timer Issues

**Problem**: Tests timeout or don't advance timers correctly

**Solution**: Use fake timers:
```typescript
beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

// In test
act(() => {
  jest.advanceTimersByTime(1000);
});
```

### 3. Cleanup Issues

**Problem**: Tests affect each other

**Solution**: Proper cleanup:
```typescript
beforeEach(() => {
  localStorage.clear();
  jest.clearAllMocks();
});
```

## Future Improvements

1. **Performance Testing**
   - Add tests for large data sets
   - Measure render performance
   - Test memory leaks

2. **Visual Regression Testing**
   - Implement screenshot testing
   - Test responsive designs
   - Verify animations

3. **Security Testing**
   - Test XSS prevention
   - Verify input sanitization
   - Test authentication flows

4. **Continuous Integration**
   - Run tests on every commit
   - Generate coverage reports
   - Fail builds on test failures

## Conclusion

This comprehensive test suite ensures the AgencyDark frontend application is reliable, accessible, and maintainable. The tests serve as both quality assurance and documentation, making it easier for developers to understand and modify the codebase with confidence.