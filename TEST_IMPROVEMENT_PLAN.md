# Test Infrastructure Improvement Plan

## Executive Summary
This plan outlines comprehensive improvements for the AgencyDark test infrastructure, addressing current issues and establishing best practices for long-term maintainability.

## Frontend Testing Improvements

### Phase 1: Migration to Vitest (Priority: HIGH)
**Timeline: 1-2 days**

#### Why Vitest?
- Native Vite support (no import.meta issues)
- Faster execution (uses Vite's transform pipeline)
- Better TypeScript support out of the box
- Compatible with existing Jest assertions

#### Implementation Steps:
1. **Install Vitest and dependencies**
   ```bash
   npm install -D vitest @vitest/ui @vitest/coverage-v8 jsdom
   ```

2. **Create vitest.config.ts**
   ```typescript
   import { defineConfig } from 'vitest/config'
   import react from '@vitejs/plugin-react'
   import path from 'path'

   export default defineConfig({
     plugins: [react()],
     test: {
       environment: 'jsdom',
       globals: true,
       setupFiles: './tests/utils/setup.ts',
       coverage: {
         reporter: ['text', 'json', 'html'],
         exclude: ['node_modules/', 'tests/']
       }
     },
     resolve: {
       alias: {
         '@': path.resolve(__dirname, './src'),
         '@/tests': path.resolve(__dirname, './tests')
       }
     }
   })
   ```

3. **Update package.json scripts**
   ```json
   {
     "test": "vitest",
     "test:ui": "vitest --ui",
     "test:coverage": "vitest run --coverage"
   }
   ```

4. **Migrate test files**
   - Remove Jest-specific globals if any
   - Update imports to use vi instead of jest mocks

### Phase 2: Enhanced Test Structure (Priority: MEDIUM)
**Timeline: 2-3 days**

1. **Create test fixtures and factories**
   ```typescript
   // tests/fixtures/user.fixtures.ts
   export const createUserFixture = (overrides = {}) => ({
     id: '123',
     email: 'test@example.com',
     role: 'user',
     ...overrides
   })
   ```

2. **Implement custom test utilities**
   ```typescript
   // tests/utils/custom-queries.ts
   export const getByTestId = (testId: string) => 
     screen.getByTestId(testId)
   ```

3. **Add visual regression testing**
   ```bash
   npm install -D @storybook/test-runner playwright
   ```

### Phase 3: Test Quality Improvements (Priority: MEDIUM)
**Timeline: 3-4 days**

1. **Add accessibility testing**
   ```bash
   npm install -D @testing-library/jest-dom jest-axe
   ```

2. **Implement performance testing**
   ```typescript
   // tests/performance/render-performance.test.ts
   import { measureRenderTime } from '@/tests/utils/performance'
   
   test('Dashboard renders within performance budget', async () => {
     const renderTime = await measureRenderTime(<Dashboard />)
     expect(renderTime).toBeLessThan(100) // ms
   })
   ```

3. **Add mutation testing**
   ```bash
   npm install -D stryker-mutator
   ```

## Backend Testing Improvements

### Phase 1: Dependency Management (Priority: HIGH)
**Timeline: 1 day**

1. **Install missing dependencies**
   ```bash
   poetry add --group dev xgboost scikit-learn aiosmtplib
   poetry add --group dev pytest-mock pytest-benchmark factory-boy
   ```

2. **Create test-specific requirements**
   ```toml
   # pyproject.toml
   [tool.poetry.group.test.dependencies]
   pytest = "^7.4.0"
   pytest-asyncio = "^0.21.0"
   pytest-cov = "^4.1.0"
   httpx = "^0.24.1"
   factory-boy = "^3.3.0"
   ```

### Phase 2: Test Isolation (Priority: HIGH)
**Timeline: 2-3 days**

1. **Create minimal test configuration**
   ```python
   # tests/test_config.py
   import os
   os.environ['TESTING'] = 'true'
   os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
   os.environ['REDIS_URL'] = 'redis://localhost:6379/1'
   ```

2. **Implement test factories**
   ```python
   # tests/factories/user_factory.py
   import factory
   from models.user import User
   
   class UserFactory(factory.Factory):
       class Meta:
           model = User
       
       email = factory.Faker('email')
       username = factory.Faker('user_name')
       role = 'user'
   ```

3. **Create isolated test fixtures**
   ```python
   # tests/fixtures/database.py
   @pytest.fixture
   async def isolated_db():
       # Create isolated database for each test
       async with create_async_engine(TEST_DB_URL) as engine:
           async with engine.begin() as conn:
               await conn.run_sync(Base.metadata.create_all)
           yield engine
           async with engine.begin() as conn:
               await conn.run_sync(Base.metadata.drop_all)
   ```

### Phase 3: Test Coverage Enhancement (Priority: MEDIUM)
**Timeline: 3-4 days**

1. **Add integration test suite**
   ```python
   # tests/integration/test_auth_flow.py
   @pytest.mark.integration
   async def test_complete_auth_flow(client, db):
       # Test registration -> login -> token refresh -> logout
   ```

2. **Implement contract testing**
   ```python
   # tests/contract/test_api_contracts.py
   from pydantic import ValidationError
   
   def test_user_response_contract():
       # Verify API responses match expected schemas
   ```

3. **Add performance benchmarks**
   ```python
   # tests/benchmarks/test_query_performance.py
   @pytest.mark.benchmark
   def test_user_query_performance(benchmark):
       result = benchmark(get_users_with_agencies)
       assert result.total_seconds() < 0.1
   ```

## Cross-Platform Improvements

### Phase 1: CI/CD Integration (Priority: HIGH)
**Timeline: 1-2 days**

1. **GitHub Actions workflow**
   ```yaml
   # .github/workflows/test.yml
   name: Test Suite
   on: [push, pull_request]
   
   jobs:
     frontend-tests:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - uses: actions/setup-node@v3
         - run: cd frontend && npm ci
         - run: cd frontend && npm test
     
     backend-tests:
       runs-on: ubuntu-latest
       services:
         postgres:
           image: postgres:15
         redis:
           image: redis:7
       steps:
         - uses: actions/checkout@v3
         - uses: actions/setup-python@v4
         - run: cd backend && poetry install
         - run: cd backend && poetry run pytest
   ```

2. **Pre-commit hooks**
   ```yaml
   # .pre-commit-config.yaml
   repos:
     - repo: local
       hooks:
         - id: frontend-tests
           name: Frontend Tests
           entry: cd frontend && npm test
           language: system
           pass_filenames: false
   ```

### Phase 2: Test Documentation (Priority: MEDIUM)
**Timeline: 2 days**

1. **Create testing guidelines**
   ```markdown
   # TESTING_GUIDELINES.md
   - Test naming conventions
   - When to write unit vs integration tests
   - Mocking strategies
   - Performance benchmarks
   ```

2. **Generate test reports**
   ```bash
   # Frontend coverage report
   npm run test:coverage
   
   # Backend coverage report
   poetry run pytest --cov-report=html
   ```

## Implementation Timeline

### Week 1: Critical Fixes
- Day 1-2: Migrate frontend to Vitest
- Day 3: Install backend dependencies
- Day 4-5: Create test isolation for backend

### Week 2: Enhancement
- Day 1-2: Implement test factories and fixtures
- Day 3-4: Add CI/CD integration
- Day 5: Create documentation

### Week 3: Advanced Features
- Day 1-2: Add visual regression testing
- Day 3-4: Implement performance benchmarks
- Day 5: Add mutation testing

## Success Metrics

### Coverage Goals
- Frontend: 80% code coverage
- Backend: 85% code coverage
- Critical paths: 100% coverage

### Performance Goals
- Frontend test suite: < 2 minutes
- Backend test suite: < 5 minutes
- CI pipeline: < 10 minutes total

### Quality Goals
- Zero flaky tests
- All tests pass in CI
- Test documentation complete

## Maintenance Strategy

### Weekly
- Review test failures
- Update test data
- Check coverage reports

### Monthly
- Review and update test strategies
- Performance benchmark review
- Update testing documentation

### Quarterly
- Evaluate new testing tools
- Refactor test utilities
- Team training on testing best practices

## Risk Mitigation

### Risks
1. **Migration complexity**: Vitest migration might break existing tests
   - Mitigation: Gradual migration, maintain Jest temporarily

2. **Dependency conflicts**: New test dependencies might conflict
   - Mitigation: Use separate test environments

3. **Performance degradation**: More tests = slower CI
   - Mitigation: Parallel test execution, test splitting

## Conclusion

This improvement plan addresses immediate issues while establishing a robust testing infrastructure for long-term success. The phased approach allows for incremental improvements without disrupting development.