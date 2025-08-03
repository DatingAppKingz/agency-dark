# Comprehensive Test Coverage Plan - AgencyDark

## Executive Summary
Current test coverage is critically low:
- Backend: ~23% coverage (65/285+ files)
- Frontend: ~12% coverage (30/248+ files)

**Goal**: Achieve 90%+ coverage for critical paths and 80%+ overall coverage.

## Coverage Targets by Priority

### 🔴 Priority 1: Critical Business Logic (Target: 100% Coverage)
**Timeline: Week 1-2**

#### Backend - Financial Operations
```
models/financial.py          → tests/unit/models/test_financial.py
services/financial/          → tests/unit/services/financial/
├── commission_service.py    → test_commission_service.py
├── payout_service.py        → test_payout_service.py
├── earnings_service.py      → test_earnings_service.py
└── tip_processing.py        → test_tip_processing.py
```

**Test Cases Required:**
- Commission calculations with all edge cases
- Payout generation and validation
- Currency conversion accuracy
- Transaction integrity
- Tip processing with platform fees
- Financial reporting accuracy

#### Frontend - Financial Components
```
src/services/api/financial.ts    → tests/unit/services/financial.test.ts
src/components/financial/         → tests/unit/components/financial/
├── PayoutCalculator.tsx          → PayoutCalculator.test.tsx
├── CommissionSettings.tsx        → CommissionSettings.test.tsx
└── EarningsDisplay.tsx           → EarningsDisplay.test.tsx
```

### 🟠 Priority 2: Authentication & Security (Target: 100% Coverage)
**Timeline: Week 2-3**

#### Backend - Auth/Security
```
models/user.py                    → tests/unit/models/test_user.py
models/api_key.py                 → tests/unit/models/test_api_key.py
middleware/auth_middleware.py     → tests/unit/middleware/test_auth_middleware.py
middleware/security_middleware.py → tests/unit/middleware/test_security_middleware.py
services/auth/                    → tests/unit/services/auth/
├── auth_service.py               → test_auth_service.py (enhance existing)
├── token_service.py              → test_token_service.py
└── permission_service.py         → test_permission_service.py
```

**Test Cases Required:**
- User authentication flows
- Token generation/validation
- Permission checks
- API key management
- Rate limiting
- Security headers
- CORS handling

### 🟡 Priority 3: Core Business Models (Target: 95% Coverage)
**Timeline: Week 3-4**

#### Backend - Business Entities
```
models/agency.py         → tests/unit/models/test_agency.py
models/model.py          → tests/unit/models/test_model.py
models/chat.py           → tests/unit/models/test_chat.py
models/content.py        → tests/unit/models/test_content.py
models/subscriber.py     → tests/unit/models/test_subscriber.py
models/conversation.py   → tests/unit/models/test_conversation.py
models/message.py        → tests/unit/models/test_message.py
```

**Test Cases Required:**
- Model validation
- Relationship integrity
- Business rule enforcement
- Data constraints
- Cascade operations

### 🟢 Priority 4: API Services (Target: 90% Coverage)
**Timeline: Week 4-5**

#### Frontend - API Services
```
src/services/api/
├── analytics.ts    → tests/unit/services/analytics.test.ts (enhance)
├── chat.ts         → tests/unit/services/chat.test.ts
├── models.ts       → tests/unit/services/models.test.ts
├── users.ts        → tests/unit/services/users.test.ts
├── media.ts        → tests/unit/services/media.test.ts
└── platform.ts     → tests/unit/services/platform.test.ts
```

#### Backend - Service Layer
```
services/chat/           → tests/unit/services/chat/
services/analytics/      → tests/unit/services/analytics/
services/platform_sync/  → tests/unit/services/platform_sync/
services/notifications/  → tests/unit/services/notifications/
```

### 🔵 Priority 5: UI Components (Target: 85% Coverage)
**Timeline: Week 5-6**

#### Critical Business Components
```
src/components/analytics/
├── AnalyticsDashboard.tsx     → AnalyticsDashboard.test.tsx
├── RevenueChart.tsx           → RevenueChart.test.tsx
└── PerformanceMetrics.tsx     → PerformanceMetrics.test.tsx

src/components/chat/
├── ChatInterface.tsx          → ChatInterface.test.tsx
├── MessageList.tsx            → MessageList.test.tsx
└── ConversationList.tsx       → ConversationList.test.tsx

src/components/models/
├── ModelProfile.tsx           → ModelProfile.test.tsx
├── ModelSettings.tsx          → ModelSettings.test.tsx
└── ModelAnalytics.tsx         → ModelAnalytics.test.tsx
```

## Test Implementation Strategy

### Phase 1: Critical Path Testing (Weeks 1-2)
```typescript
// Example: Financial Commission Test
describe('CommissionService', () => {
  describe('calculateCommission', () => {
    it('should calculate standard commission correctly', () => {
      const earning = { amount: 1000, type: 'subscription' };
      const commission = calculateCommission(earning, 0.2);
      expect(commission).toBe(200);
    });
    
    it('should handle platform fees', () => {
      const earning = { amount: 1000, platformFee: 0.1 };
      const commission = calculateCommission(earning, 0.2);
      expect(commission).toBe(180); // (1000 - 100) * 0.2
    });
    
    it('should handle currency conversion', () => {
      const earning = { amount: 1000, currency: 'EUR' };
      const commission = calculateCommissionUSD(earning, 0.2, 1.1);
      expect(commission).toBe(220); // 1000 * 1.1 * 0.2
    });
  });
});
```

### Phase 2: Integration Testing (Weeks 3-4)
```python
# Example: Financial Flow Integration Test
@pytest.mark.asyncio
async def test_complete_payout_flow():
    # Create test data
    agency = await create_test_agency(commission_rate=0.2)
    model = await create_test_model(agency=agency)
    
    # Generate earnings
    earnings = await generate_test_earnings(model, amount=5000)
    
    # Process payout
    payout = await payout_service.create_payout(
        model_id=model.id,
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now()
    )
    
    # Verify calculations
    assert payout.gross_amount == 5000
    assert payout.commission_amount == 1000
    assert payout.net_amount == 4000
    assert payout.status == PayoutStatus.PENDING
    
    # Process payment
    await payout_service.process_payment(payout.id)
    
    # Verify completion
    updated_payout = await get_payout(payout.id)
    assert updated_payout.status == PayoutStatus.COMPLETED
    assert updated_payout.paid_at is not None
```

### Phase 3: E2E Testing (Weeks 5-6)
```typescript
// Example: Complete User Journey Test
describe('Model Earnings Flow E2E', () => {
  it('should track earnings from chat to payout', async () => {
    // Login as model
    await loginAs('model@example.com');
    
    // Navigate to chat
    await page.goto('/chat');
    
    // Receive tip in conversation
    await simulateTip({
      amount: 100,
      from: 'fan123',
      message: 'Great content!'
    });
    
    // Verify earnings update
    await page.goto('/earnings');
    await expect(page.locator('[data-testid="today-earnings"]'))
      .toHaveText('$100.00');
    
    // Check commission calculation
    await expect(page.locator('[data-testid="agency-commission"]'))
      .toHaveText('$20.00'); // 20% commission
    
    // Request payout
    await page.click('[data-testid="request-payout"]');
    await expect(page.locator('[data-testid="payout-status"]'))
      .toHaveText('Pending');
  });
});
```

## Coverage Monitoring

### 1. Setup Coverage Tools
```bash
# Frontend
npm install -D @vitest/coverage-v8
npm install -D @vitest/ui

# Backend
poetry add --dev coverage pytest-cov
```

### 2. Coverage Scripts
```json
// package.json
{
  "scripts": {
    "test:coverage": "vitest run --coverage",
    "test:coverage:watch": "vitest --coverage",
    "test:coverage:ui": "vitest --ui --coverage"
  }
}
```

```toml
# pyproject.toml
[tool.coverage.run]
source = ["backend"]
omit = ["*/tests/*", "*/migrations/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 80
```

### 3. CI Coverage Gates
```yaml
# .github/workflows/test.yml
- name: Check coverage
  run: |
    coverage report --fail-under=80
    coverage xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    fail_ci_if_error: true
    verbose: true
```

## Test Data Management

### 1. Test Fixtures
```typescript
// tests/fixtures/financial.fixtures.ts
export const mockEarnings = {
  subscription: {
    amount: 1000,
    type: 'subscription',
    currency: 'USD',
    platformFee: 0.1
  },
  tip: {
    amount: 50,
    type: 'tip',
    currency: 'USD',
    platformFee: 0.05
  },
  ppv: {
    amount: 25,
    type: 'ppv',
    currency: 'USD',
    platformFee: 0.1
  }
};
```

### 2. Test Database Seeds
```python
# tests/seeds/financial_seed.py
async def seed_financial_test_data(db: AsyncSession):
    """Seed comprehensive financial test data."""
    agencies = await create_agencies_with_models(count=3)
    
    for agency in agencies:
        # Create various earning types
        await create_earnings_for_period(
            agency=agency,
            start_date=datetime.now() - timedelta(days=90),
            end_date=datetime.now(),
            daily_range=(100, 1000)
        )
        
        # Create payouts
        await create_historical_payouts(
            agency=agency,
            count=3
        )
```

## Performance Testing

### Load Testing Critical Paths
```python
# tests/performance/test_financial_load.py
@pytest.mark.performance
async def test_bulk_commission_calculation():
    """Test commission calculation under load."""
    earnings = [create_earning(amount=random.uniform(10, 1000)) 
                for _ in range(10000)]
    
    start_time = time.time()
    results = await calculate_bulk_commissions(earnings)
    duration = time.time() - start_time
    
    assert duration < 1.0  # Should process 10k in under 1 second
    assert len(results) == 10000
    assert all(r.commission > 0 for r in results)
```

## Success Metrics

### Coverage Goals
- **Week 2**: 50% overall, 100% critical paths
- **Week 4**: 70% overall, 95% business logic
- **Week 6**: 85% overall, 90% UI components

### Quality Metrics
- Zero flaky tests
- All tests run in < 5 minutes
- 100% of PRs with test coverage
- No production bugs in tested code

## Maintenance Plan

### Daily
- Run coverage reports
- Fix any failing tests
- Review PR test coverage

### Weekly
- Update test fixtures
- Review coverage trends
- Identify new gaps

### Monthly
- Refactor test utilities
- Update test documentation
- Performance test review

## ROI Calculation

### Investment
- 6 weeks developer time
- ~240 hours effort
- Tool and infrastructure setup

### Return
- 90% reduction in production bugs
- 50% faster feature development
- 80% reduction in regression issues
- Improved code documentation
- Higher developer confidence

### Payback Period
- Estimated 2-3 months through reduced bug fixes and faster development