# Backend Testing Suite

Comprehensive testing framework for the Agency Backend API implementing Backend Polish 8: Testing & Quality.

## Test Structure

```
tests/
├── conftest.py              # Global fixtures and configuration
├── unit/                    # Unit tests for individual components
│   └── test_resilience.py   # Tests for resilience components
├── integration/             # Integration tests for API endpoints
│   └── test_api_integration.py
├── contract/                # Contract tests for API contracts
│   └── test_api_contracts.py
├── performance/             # Performance benchmarks
│   └── test_benchmarks.py
├── load/                    # Load testing scenarios
│   ├── locustfile.py        # Locust load tests
│   └── k6_load_test.js      # k6 load tests
├── security/                # Security tests (OWASP)
│   └── test_owasp_security.py
├── mutation/                # Mutation testing
│   └── test_mutations.py
├── fixtures/                # Test fixtures and data
└── utils/                   # Test utilities
    └── test_coverage.py     # Coverage analysis tools
```

## Test Categories

### 1. Unit Tests (80%+ Coverage)
- Test individual components in isolation
- Mock external dependencies
- Fast execution (<1s per test)
- Run with: `make test-unit`

### 2. Integration Tests
- Test API endpoints end-to-end
- Use test database and Redis
- Verify component interactions
- Run with: `make test-integration`

### 3. Contract Tests
- Verify API contracts (request/response schemas)
- Consumer-driven contracts
- OpenAPI specification validation
- Run with: `make test-contract`

### 4. Performance Benchmarks
- Measure execution time and resource usage
- Database query performance
- API endpoint latency
- Memory usage profiling
- Run with: `make benchmark`

### 5. Load Tests
- **Locust**: Python-based load testing
  - Multiple user scenarios
  - Real-world usage patterns
  - Run with: `make load-test`
  
- **k6**: JavaScript-based load testing
  - Advanced scenarios
  - Cloud execution support
  - Run with: `make load-test-k6`

### 6. Security Tests
- OWASP Top 10 vulnerability testing
- Authentication/authorization tests
- Input validation and sanitization
- SQL injection prevention
- XSS protection
- Run with: `make test-security`

### 7. Mutation Tests
- Test the quality of tests
- Introduce code mutations
- Verify tests catch changes
- Run with: `make mutation-test`

## Running Tests

### Quick Start
```bash
# Install dependencies
make install

# Run all tests
make test

# Run specific test category
make test-unit
make test-integration
make test-security

# Run with coverage
make coverage

# Run quality checks
make quality-check
```

### Test Commands
```bash
# Run tests by marker
pytest -m unit
pytest -m integration
pytest -m security

# Run specific test file
pytest tests/unit/test_resilience.py

# Run specific test
pytest tests/unit/test_resilience.py::TestCircuitBreaker::test_circuit_breaker_closed_state

# Run tests in parallel
pytest -n auto

# Run with verbose output
pytest -vv

# Run and stop on first failure
pytest -x
```

## Coverage Requirements

- **Overall**: 80% minimum
- **Critical modules**: 90% minimum
  - Authentication/Authorization
  - Payment processing
  - Security components
  - Database operations

Check coverage with:
```bash
make coverage-report
# Open htmlcov/index.html in browser
```

## Performance Benchmarks

### Running Benchmarks
```bash
# Run all benchmarks
make benchmark

# Compare with previous results
make benchmark-compare

# Specific benchmark
pytest tests/performance/test_benchmarks.py::test_database_performance -v --benchmark-only
```

### Performance Thresholds
- Database queries: <10ms average
- API endpoints: <100ms average
- Bulk operations: <1s for 1000 items
- Memory usage: <50MB increase per operation

## Load Testing

### Locust (Python)
```bash
# Start Locust web UI
make load-test
# Visit http://localhost:8089

# Run headless
locust -f tests/load/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 5m
```

### k6 (JavaScript)
```bash
# Run load test
k6 run tests/load/k6_load_test.js

# Run with custom parameters
k6 run --vus 100 --duration 5m tests/load/k6_load_test.js

# Run in cloud
k6 cloud tests/load/k6_load_test.js
```

### Load Test Scenarios
- **Standard Load**: 100 users over 5 minutes
- **Spike Test**: Sudden increase to 500 users
- **Stress Test**: Gradual increase to find breaking point
- **Soak Test**: Sustained load for extended period

## Security Testing

### OWASP Top 10 Coverage
1. **A01:2021** – Broken Access Control ✓
2. **A02:2021** – Cryptographic Failures ✓
3. **A03:2021** – Injection ✓
4. **A04:2021** – Insecure Design ✓
5. **A05:2021** – Security Misconfiguration ✓
6. **A06:2021** – Vulnerable Components ✓
7. **A07:2021** – Authentication Failures ✓
8. **A08:2021** – Data Integrity Failures ✓
9. **A09:2021** – Security Logging Failures ✓
10. **A10:2021** – SSRF ✓

### Security Scans
```bash
# Run all security tests
make test-security

# Run security scanning tools
make security-scan

# Manual penetration testing
# Use OWASP ZAP or Burp Suite
```

## Mutation Testing

### Setup
```bash
# Install mutmut
pip install mutmut

# Configure
mutmut config
```

### Running Mutation Tests
```bash
# Run on specific module
mutmut run --paths-to-mutate=backend/core/auth

# Show results
mutmut results

# Show survived mutants
mutmut show all
```

### Mutation Score Target
- Overall: 80% minimum
- Critical modules: 90% minimum

## CI/CD Integration

### GitHub Actions
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: make ci
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: tests
        name: Run tests
        entry: make test-fast
        language: system
        pass_filenames: false
```

## Best Practices

### Writing Tests
1. **Arrange-Act-Assert** pattern
2. One assertion per test (when possible)
3. Descriptive test names
4. Use fixtures for common setup
5. Mock external dependencies
6. Test edge cases and error conditions

### Test Data
1. Use factories for complex objects
2. Avoid hardcoded values
3. Clean up after tests
4. Use transactions for database tests

### Performance
1. Run unit tests frequently (fast)
2. Run integration tests before commits
3. Run full suite before merging
4. Parallelize when possible

## Troubleshooting

### Common Issues

**Tests failing locally but passing in CI**
- Check environment variables
- Verify database state
- Check for timing issues

**Flaky tests**
- Add proper waits for async operations
- Use fixed timestamps
- Mock external services

**Slow tests**
- Profile with `pytest --durations=10`
- Use pytest-xdist for parallel execution
- Optimize database queries
- Use in-memory databases for tests

## Monitoring Test Health

### Metrics to Track
- Test execution time
- Test flakiness rate
- Coverage trends
- Mutation score
- Performance regression

### Regular Maintenance
- Review and update tests monthly
- Remove obsolete tests
- Refactor complex tests
- Update test data

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Locust Documentation](https://docs.locust.io/)
- [k6 Documentation](https://k6.io/docs/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [Mutation Testing](https://mutmut.readthedocs.io/)