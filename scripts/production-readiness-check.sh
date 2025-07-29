#!/bin/bash
set -euo pipefail

# Production Readiness Checklist Script
# This script validates that all production requirements are met

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Tracking variables
TOTAL_CHECKS=0
PASSED_CHECKS=0
WARNINGS=0
FAILURES=()

# Helper functions
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED_CHECKS++))
    ((TOTAL_CHECKS++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    FAILURES+=("$1")
    ((TOTAL_CHECKS++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

print_section() {
    echo
    echo "========================================="
    echo "$1"
    echo "========================================="
}

# Start checks
echo "🚀 Production Readiness Checklist"
echo "================================="
echo "Date: $(date)"
echo

# 1. Code Quality Checks
print_section "1. CODE QUALITY"

# Python linting
if command -v flake8 &> /dev/null; then
    if flake8 backend --count --statistics > /dev/null 2>&1; then
        check_pass "Python linting (flake8)"
    else
        check_fail "Python linting (flake8) - found issues"
    fi
else
    check_warn "flake8 not installed"
fi

# Type checking
if command -v mypy &> /dev/null; then
    if mypy backend --ignore-missing-imports > /dev/null 2>&1; then
        check_pass "Python type checking (mypy)"
    else
        check_fail "Python type checking (mypy) - found issues"
    fi
else
    check_warn "mypy not installed"
fi

# Security scanning
if command -v bandit &> /dev/null; then
    if bandit -r backend -ll > /dev/null 2>&1; then
        check_pass "Security scanning (bandit)"
    else
        check_fail "Security scanning (bandit) - found issues"
    fi
else
    check_warn "bandit not installed"
fi

# 2. Test Coverage
print_section "2. TEST COVERAGE"

# Run tests with coverage
if [ -f "backend/pytest.ini" ]; then
    cd backend
    if python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=80 > /dev/null 2>&1; then
        check_pass "Test coverage >= 80%"
    else
        check_fail "Test coverage < 80%"
    fi
    cd ..
else
    check_fail "pytest.ini not found"
fi

# 3. Documentation
print_section "3. DOCUMENTATION"

# Check for required documentation files
REQUIRED_DOCS=(
    "README.md"
    "docs/production/README.md"
    "docs/production/runbooks/incident-response.md"
    "docs/production/sla.md"
    "CHANGELOG.md"
    "LICENSE"
)

for doc in "${REQUIRED_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        check_pass "Documentation: $doc"
    else
        check_fail "Documentation: $doc missing"
    fi
done

# API documentation
if [ -f "backend/app/core/openapi.py" ]; then
    check_pass "API documentation (OpenAPI)"
else
    check_fail "API documentation (OpenAPI) missing"
fi

# 4. Configuration
print_section "4. CONFIGURATION"

# Environment configuration
if [ -f "backend/.env.example" ]; then
    check_pass "Environment configuration template"
else
    check_fail "Environment configuration template missing"
fi

# Kubernetes manifests
if [ -d "k8s" ] && [ -f "k8s/base/deployment.yaml" ]; then
    check_pass "Kubernetes manifests"
else
    check_fail "Kubernetes manifests missing"
fi

# Helm charts
if [ -d "helm" ] && [ -f "helm/agency-backend/Chart.yaml" ]; then
    check_pass "Helm charts"
else
    check_fail "Helm charts missing"
fi

# 5. Security
print_section "5. SECURITY"

# Security headers
if grep -q "SecurityHeadersMiddleware" backend/app/main*.py 2>/dev/null; then
    check_pass "Security headers middleware"
else
    check_fail "Security headers middleware not configured"
fi

# Secrets management
if [ -f "backend/core/security/secrets.py" ]; then
    check_pass "Secrets management system"
else
    check_fail "Secrets management system missing"
fi

# Dependency scanning
if [ -f ".github/workflows/security.yml" ] || grep -q "trivy\|safety" .github/workflows/*.yml 2>/dev/null; then
    check_pass "Dependency vulnerability scanning"
else
    check_warn "Dependency vulnerability scanning not in CI/CD"
fi

# 6. Monitoring & Observability
print_section "6. MONITORING & OBSERVABILITY"

# Health check endpoint
if grep -q "/health" backend/app/main*.py 2>/dev/null; then
    check_pass "Health check endpoint"
else
    check_fail "Health check endpoint missing"
fi

# Metrics endpoint
if grep -q "/metrics" backend/app/main*.py 2>/dev/null; then
    check_pass "Metrics endpoint"
else
    check_fail "Metrics endpoint missing"
fi

# Logging configuration
if [ -f "backend/app/core/logging.py" ]; then
    check_pass "Structured logging"
else
    check_fail "Structured logging missing"
fi

# Distributed tracing
if grep -q "opentelemetry\|jaeger" backend/requirements.txt 2>/dev/null; then
    check_pass "Distributed tracing"
else
    check_warn "Distributed tracing not configured"
fi

# 7. Performance
print_section "7. PERFORMANCE"

# Database optimizations
if [ -f "backend/core/optimization/query_optimizer.py" ]; then
    check_pass "Database query optimization"
else
    check_fail "Database query optimization missing"
fi

# Caching
if [ -f "backend/core/optimization/cache_manager.py" ]; then
    check_pass "Caching system"
else
    check_fail "Caching system missing"
fi

# Response compression
if [ -f "backend/core/optimization/compression.py" ]; then
    check_pass "Response compression"
else
    check_fail "Response compression missing"
fi

# Connection pooling
if [ -f "backend/core/optimization/connection_pool.py" ]; then
    check_pass "Connection pooling"
else
    check_fail "Connection pooling missing"
fi

# 8. Reliability
print_section "8. RELIABILITY"

# Circuit breakers
if [ -f "backend/app/core/resilience.py" ]; then
    check_pass "Circuit breakers"
else
    check_fail "Circuit breakers missing"
fi

# Retry logic
if grep -q "retry\|tenacity" backend/requirements.txt 2>/dev/null; then
    check_pass "Retry logic"
else
    check_fail "Retry logic missing"
fi

# Rate limiting
if grep -q "RateLimitMiddleware\|slowapi" backend/app/*.py backend/app/**/*.py 2>/dev/null; then
    check_pass "Rate limiting"
else
    check_fail "Rate limiting missing"
fi

# 9. Deployment
print_section "9. DEPLOYMENT"

# CI/CD pipelines
if [ -f ".github/workflows/ci.yml" ] && [ -f ".github/workflows/cd.yml" ]; then
    check_pass "CI/CD pipelines"
else
    check_fail "CI/CD pipelines incomplete"
fi

# Docker configuration
if [ -f "backend/Dockerfile" ] || [ -f "backend/Dockerfile.optimized" ]; then
    check_pass "Docker configuration"
else
    check_fail "Docker configuration missing"
fi

# Blue-green deployment
if [ -f "scripts/blue-green-deploy.sh" ]; then
    check_pass "Blue-green deployment"
else
    check_fail "Blue-green deployment missing"
fi

# Database migrations
if [ -f "scripts/db-migration.sh" ]; then
    check_pass "Database migration automation"
else
    check_fail "Database migration automation missing"
fi

# 10. Disaster Recovery
print_section "10. DISASTER RECOVERY"

# Backup scripts
if [ -f "scripts/disaster-recovery/backup-automation.sh" ]; then
    check_pass "Automated backups"
else
    check_fail "Automated backups missing"
fi

# Recovery procedures
if [ -f "scripts/disaster-recovery/recover-database.sh" ]; then
    check_pass "Recovery procedures"
else
    check_fail "Recovery procedures missing"
fi

# DR plan
if [ -f "scripts/disaster-recovery/dr-plan.md" ]; then
    check_pass "Disaster recovery plan"
else
    check_fail "Disaster recovery plan missing"
fi

# 11. Operational Readiness
print_section "11. OPERATIONAL READINESS"

# Runbooks
if [ -d "docs/production/runbooks" ]; then
    check_pass "Operational runbooks"
else
    check_fail "Operational runbooks missing"
fi

# SLA definition
if [ -f "docs/production/sla.md" ]; then
    check_pass "SLA documentation"
else
    check_fail "SLA documentation missing"
fi

# Monitoring dashboards
if grep -q "grafana\|datadog\|prometheus" k8s/**/*.yaml helm/**/*.yaml 2>/dev/null; then
    check_pass "Monitoring dashboards configured"
else
    check_warn "Monitoring dashboards not configured"
fi

# 12. Performance Testing
print_section "12. PERFORMANCE TESTING"

# Load tests
if [ -f "backend/tests/load/locustfile.py" ] || [ -f "backend/tests/load/k6_load_test.js" ]; then
    check_pass "Load testing scripts"
else
    check_fail "Load testing scripts missing"
fi

# Performance benchmarks
if [ -f "backend/tests/performance/test_benchmarks.py" ]; then
    check_pass "Performance benchmarks"
else
    check_fail "Performance benchmarks missing"
fi

# Chaos engineering
if [ -f "backend/tests/chaos/test_chaos_engineering.py" ]; then
    check_pass "Chaos engineering tests"
else
    check_fail "Chaos engineering tests missing"
fi

# Summary
print_section "SUMMARY"

SCORE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

echo "Total Checks: $TOTAL_CHECKS"
echo "Passed: $PASSED_CHECKS"
echo "Failed: ${#FAILURES[@]}"
echo "Warnings: $WARNINGS"
echo
echo -e "Production Readiness Score: ${GREEN}${SCORE}%${NC}"

if [ ${#FAILURES[@]} -gt 0 ]; then
    echo
    echo -e "${RED}Failed Checks:${NC}"
    for failure in "${FAILURES[@]}"; do
        echo "  - $failure"
    done
fi

# Recommendations
if [ $SCORE -lt 100 ]; then
    echo
    echo "📋 Recommendations:"
    
    if [ $SCORE -lt 60 ]; then
        echo "  ⚠️  CRITICAL: System is NOT ready for production"
        echo "  - Address all failed checks immediately"
        echo "  - Minimum 80% score recommended for production"
    elif [ $SCORE -lt 80 ]; then
        echo "  ⚠️  WARNING: System needs improvements before production"
        echo "  - Address critical failures first"
        echo "  - Review and implement missing components"
    else
        echo "  ✓ System is approaching production readiness"
        echo "  - Address remaining issues"
        echo "  - Consider implementing warning items"
    fi
fi

# Exit code based on score
if [ $SCORE -ge 80 ]; then
    echo
    echo -e "${GREEN}✅ Production readiness check PASSED${NC}"
    exit 0
else
    echo
    echo -e "${RED}❌ Production readiness check FAILED${NC}"
    exit 1
fi