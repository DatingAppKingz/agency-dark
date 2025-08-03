# Quick Start: Test Improvements

## Immediate Actions (Day 1)

### Frontend: Migrate to Vitest

```bash
cd frontend

# 1. Install Vitest
npm install -D vitest @vitest/ui @vitest/coverage-v8 @testing-library/jest-dom jsdom

# 2. Create vitest.config.ts
cat > vitest.config.ts << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/utils/setup.ts',
    css: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/tests': path.resolve(__dirname, './tests'),
    },
  },
})
EOF

# 3. Update package.json
npm pkg set scripts.test="vitest"
npm pkg set scripts.test:ui="vitest --ui"
npm pkg set scripts.test:run="vitest run"
npm pkg set scripts.test:coverage="vitest run --coverage"

# 4. Test it works
npm test
```

### Backend: Fix Dependencies

```bash
cd backend

# 1. Install missing dependencies
poetry add --group dev xgboost scikit-learn aiosmtplib
poetry add --group dev pytest-mock pytest-benchmark factory-boy

# 2. Create test environment file
cat > .env.test << 'EOF'
DATABASE_URL=postgresql://postgres:postgres@localhost/agencydark_test
REDIS_URL=redis://localhost:6379/1
SECRET_KEY=test-secret-key
TESTING=true
ML_MODELS_ENABLED=false
EMAIL_ENABLED=false
EOF

# 3. Create minimal test runner
cat > run_tests_minimal.py << 'EOF'
import subprocess
import os

# Set minimal environment
os.environ['TESTING'] = 'true'
os.environ['ML_MODELS_ENABLED'] = 'false'

# Run only unit tests
subprocess.run([
    "poetry", "run", "pytest", 
    "tests/unit/",
    "-v",
    "--tb=short",
    "-k", "not integration"
])
EOF

# 4. Run minimal tests
python run_tests_minimal.py
```

## Day 2: Create Test Utilities

### Frontend Test Utils

```typescript
// frontend/tests/utils/test-helpers.ts
export const waitForLoadingToFinish = () => 
  waitFor(() => {
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
  })

export const loginUser = async (user = { email: 'test@example.com' }) => {
  const loginButton = screen.getByRole('button', { name: /login/i })
  await userEvent.click(loginButton)
  await waitForLoadingToFinish()
  return user
}
```

### Backend Test Factories

```python
# backend/tests/factories.py
from datetime import datetime
import factory
from factory.alchemy import SQLAlchemyModelFactory
from models.user import User
from models.agency import Agency

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = 'commit'
    
    id = factory.Faker('uuid4')
    email = factory.Faker('email')
    username = factory.Faker('user_name')
    created_at = factory.LazyFunction(datetime.utcnow)

class AgencyFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Agency
    
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    subdomain = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
```

## Day 3: CI/CD Setup

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      
      - name: Install and test
        working-directory: frontend
        run: |
          npm ci
          npm run test:run
          npm run test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          directory: frontend/coverage

  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: agencydark_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Poetry
        uses: snok/install-poetry@v1
      
      - name: Install and test
        working-directory: backend
        run: |
          poetry install --with dev
          poetry run pytest tests/unit/ -v --cov=./ --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          directory: backend
```

## Verification Commands

After implementing each step:

```bash
# Frontend - verify Vitest works
cd frontend && npm test -- --run

# Backend - verify tests run
cd backend && poetry run pytest tests/unit/test_api_key_manager_isolated.py -v

# Check coverage
cd frontend && npm run test:coverage
cd backend && poetry run pytest --cov --cov-report=html
```

## Next Steps

1. **Week 1**: Complete migration to Vitest and fix all import issues
2. **Week 2**: Add test factories and improve test data management  
3. **Week 3**: Set up visual regression and performance testing
4. **Week 4**: Implement mutation testing and advanced test strategies

## Success Indicators

- ✅ All tests run without configuration errors
- ✅ Test execution time < 2 minutes for frontend
- ✅ Test execution time < 5 minutes for backend
- ✅ Coverage > 80% for both frontend and backend
- ✅ CI/CD pipeline runs on every commit