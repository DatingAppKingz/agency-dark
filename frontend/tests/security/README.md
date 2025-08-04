# Security Testing Suite

This directory contains comprehensive security tests for the Agency Dark platform.

## Test Categories

### 1. SQL Injection Tests (`sql-injection.spec.ts`)
- Tests various SQL injection payloads
- Validates parameterized queries
- Checks error message exposure
- Tests URL parameter injection
- API endpoint injection attempts

### 2. XSS Vulnerability Tests (`xss-vulnerabilities.spec.ts`)
- Tests for reflected XSS
- Tests for stored XSS
- DOM-based XSS prevention
- Content Security Policy validation
- Rich text sanitization

### 3. Authentication Security Tests (`auth-security.spec.ts`)
- Password complexity enforcement
- Brute force protection
- Session management
- CSRF protection
- Session fixation prevention
- Secure headers validation
- Account lockout mechanisms

### 4. API Security Tests (`api-security.spec.ts`)
- Input validation
- Rate limiting
- Access control
- CORS policy
- Content type validation
- File upload security
- API versioning
- Error handling

## Running Security Tests

### Run All Security Tests
```bash
./run-security-tests.sh
```

### Run Individual Test Suites
```bash
# SQL Injection tests
npx playwright test tests/security/sql-injection.spec.ts

# XSS tests
npx playwright test tests/security/xss-vulnerabilities.spec.ts

# Authentication tests
npx playwright test tests/security/auth-security.spec.ts

# API tests
npx playwright test tests/security/api-security.spec.ts
```

## Security Test Payloads

The tests use various security payloads including:
- SQL injection vectors
- XSS attack vectors
- Path traversal attempts
- Command injection attempts
- XXE payloads
- CSRF bypass attempts

## Reports

Security test reports are generated in:
- `test-results/security/` - JSON results
- `security-report/` - HTML report
- HAR files for request analysis

## Security Checklist

### Frontend Security
- [ ] Content Security Policy (CSP)
- [ ] XSS prevention (React escaping)
- [ ] HTTPS everywhere
- [ ] Secure cookie attributes
- [ ] Input validation
- [ ] Output encoding

### API Security
- [ ] Authentication required
- [ ] Authorization checks
- [ ] Rate limiting
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] CORS configuration

### Infrastructure Security
- [ ] Security headers
- [ ] TLS configuration
- [ ] Firewall rules
- [ ] DDoS protection
- [ ] WAF implementation
- [ ] Log monitoring

## OWASP Top 10 Coverage

1. **Injection** - SQL, NoSQL, Command injection tests
2. **Broken Authentication** - Session, password, brute force tests
3. **Sensitive Data Exposure** - HTTPS, encryption tests
4. **XML External Entities** - XXE prevention tests
5. **Broken Access Control** - Authorization tests
6. **Security Misconfiguration** - Headers, CORS tests
7. **Cross-Site Scripting** - XSS prevention tests
8. **Insecure Deserialization** - Input validation tests
9. **Using Components with Known Vulnerabilities** - Dependency checks
10. **Insufficient Logging & Monitoring** - Security event tests

## Best Practices

1. **Regular Testing** - Run security tests in CI/CD pipeline
2. **Dependency Scanning** - Use `npm audit` regularly
3. **Code Reviews** - Focus on security implications
4. **Penetration Testing** - Annual professional testing
5. **Security Training** - Keep team updated on threats
6. **Incident Response** - Have a plan ready

## Tools Integration

Consider integrating:
- OWASP ZAP for dynamic analysis
- SonarQube for static analysis
- Snyk for dependency scanning
- GitGuardian for secret scanning

## Remediation

When security issues are found:
1. Assess severity and impact
2. Create fix with tests
3. Review and test thoroughly
4. Deploy with monitoring
5. Document in security log

## Contact

For security issues, contact: security@agency-dark.com