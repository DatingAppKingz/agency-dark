#!/bin/bash

# AgencyDark Test Runner Script

echo "🧪 AgencyDark Test Suite"
echo "========================"

# Set test environment
export ENVIRONMENT=test
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agencydark_test

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run tests
run_tests() {
    local test_type=$1
    local test_path=$2
    
    echo -e "\n${YELLOW}Running $test_type tests...${NC}"
    
    if python3 -m pytest $test_path -v --tb=short; then
        echo -e "${GREEN}✓ $test_type tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ $test_type tests failed${NC}"
        return 1
    fi
}

# Create test database if it doesn't exist
echo "Setting up test database..."
createdb agencydark_test 2>/dev/null || echo "Test database already exists"

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip3 install pytest pytest-asyncio pytest-cov httpx --break-system-packages

# Run migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
cd /Users/mariuszbudzisz/SourceCode/agency-dark
python3 -m alembic -c backend/alembic.ini upgrade head

# Initialize test results
FAILED=0

# Run unit tests
if ! run_tests "Unit" "backend/tests/unit/"; then
    FAILED=$((FAILED + 1))
fi

# Run integration tests
if ! run_tests "Integration" "backend/tests/integration/"; then
    FAILED=$((FAILED + 1))
fi

# Run security tests
if ! run_tests "Security" "backend/tests/unit/test_security.py backend/tests/integration/test_api_security.py"; then
    FAILED=$((FAILED + 1))
fi

# Generate coverage report
echo -e "\n${YELLOW}Generating coverage report...${NC}"
python3 -m pytest backend/tests/ --cov=backend --cov-report=html --cov-report=term

# Summary
echo -e "\n========================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo "Coverage report available at: htmlcov/index.html"
    exit 0
else
    echo -e "${RED}✗ $FAILED test suite(s) failed${NC}"
    exit 1
fi