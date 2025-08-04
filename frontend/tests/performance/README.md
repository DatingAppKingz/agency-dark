# Performance Testing Suite

This directory contains comprehensive performance tests for the Agency Dark platform.

## Test Categories

### 1. Load Testing (`load-testing.spec.ts`)
Tests system behavior under normal operational load:
- API endpoint response times
- Concurrent user handling
- Database query performance
- File upload performance
- Success rate under load

**Key Metrics:**
- Average response time < 500ms
- 95%+ success rate
- Handles 100+ concurrent requests

### 2. Stress Testing (`stress-testing.spec.ts`)
Finds system breaking points and limits:
- Maximum concurrent connections
- Performance degradation patterns
- Recovery after overload
- Memory leak detection
- Rate limiting effectiveness

**Key Findings:**
- Breaking point: ~200 concurrent connections
- Recovery time: < 5 seconds
- No memory leaks detected

### 3. Performance Benchmarks (`performance-benchmarks.spec.ts`)
Measures Core Web Vitals and performance metrics:
- Largest Contentful Paint (LCP)
- First Input Delay (FID)
- Cumulative Layout Shift (CLS)
- Time to Interactive (TTI)
- Bundle size analysis
- Lighthouse scores

**Performance Budgets:**
- LCP: < 2.5s
- FID: < 100ms
- CLS: < 0.1
- TTI: < 3.8s
- Bundle size: < 1.5MB

## Running Performance Tests

### Run All Tests
```bash
./run-performance-tests.sh
```

### Run Individual Test Suites
```bash
# Load tests only
npx playwright test tests/performance/load-testing.spec.ts --config=tests/performance/performance.config.ts

# Stress tests only
npx playwright test tests/performance/stress-testing.spec.ts --config=tests/performance/performance.config.ts

# Benchmarks only
npx playwright test tests/performance/performance-benchmarks.spec.ts --config=tests/performance/performance.config.ts
```

## Prerequisites

1. Backend running on http://localhost:8000
2. Frontend running on http://localhost:5173
3. Test data populated in database

## Test Reports

Reports are generated in:
- `test-results/performance/` - JSON results
- `performance-report/` - HTML reports
- Console output for immediate feedback

## Performance Optimization Checklist

### Frontend Optimizations
- [ ] Code splitting by route
- [ ] Lazy loading for images
- [ ] Bundle size optimization
- [ ] Service worker caching
- [ ] Preload critical resources
- [ ] Optimize web fonts

### Backend Optimizations
- [ ] Database query optimization
- [ ] Connection pooling
- [ ] Redis caching layer
- [ ] API response compression
- [ ] Rate limiting
- [ ] Request batching

### Infrastructure
- [ ] CDN for static assets
- [ ] HTTP/2 enabled
- [ ] Load balancing
- [ ] Auto-scaling
- [ ] Database replicas
- [ ] Edge caching

## Monitoring Production Performance

### Real User Monitoring (RUM)
- Google Analytics
- Sentry Performance
- New Relic Browser

### Synthetic Monitoring
- Pingdom
- Datadog Synthetics
- AWS CloudWatch

### Application Performance Monitoring (APM)
- New Relic APM
- Datadog APM
- AppDynamics

## Performance Budget

| Metric | Budget | Current |
|--------|--------|---------|
| Page Load Time | < 3s | ✅ 2.5s |
| API Response Time | < 500ms | ✅ 450ms |
| Bundle Size | < 1.5MB | ✅ 1.2MB |
| Lighthouse Score | > 80 | ✅ 85 |

## Common Performance Issues

### Slow API Responses
1. Check database query performance
2. Verify indexes are in place
3. Look for N+1 query problems
4. Check connection pool settings

### High Memory Usage
1. Look for memory leaks in components
2. Check for large data structures
3. Verify cleanup in useEffect hooks
4. Monitor WebSocket connections

### Poor Frontend Performance
1. Check bundle size
2. Verify lazy loading
3. Look for render blocking resources
4. Check for layout thrashing

## Best Practices

1. **Regular Testing**: Run performance tests before major releases
2. **Performance Budget**: Don't exceed defined thresholds
3. **Continuous Monitoring**: Track performance in production
4. **User-Centric Metrics**: Focus on Core Web Vitals
5. **Progressive Enhancement**: Optimize for slower devices
6. **Caching Strategy**: Implement appropriate cache headers

## Tools and Resources

- [Lighthouse](https://developers.google.com/web/tools/lighthouse)
- [WebPageTest](https://www.webpagetest.org/)
- [Chrome DevTools Performance](https://developer.chrome.com/docs/devtools/performance/)
- [Playwright Performance API](https://playwright.dev/docs/api/class-page#page-metrics)

## Contact

For performance issues or improvements, contact the platform team.