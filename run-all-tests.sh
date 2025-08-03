#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running All Tests for AgencyDark${NC}"
echo "=================================="
echo ""

# Frontend Tests
echo -e "${YELLOW}Frontend Tests:${NC}"
cd frontend
echo "Running Vitest..."
npm run test:run > frontend-test-results.txt 2>&1
FRONTEND_EXIT=$?

if [ $FRONTEND_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend tests passed${NC}"
    PASSED_TESTS=$(grep -E "Tests.*passed" frontend-test-results.txt | tail -1)
    echo "  $PASSED_TESTS"
else
    echo -e "${RED}✗ Frontend tests failed${NC}"
    FAILED_TESTS=$(grep -E "Tests.*failed" frontend-test-results.txt | tail -1)
    echo "  $FAILED_TESTS"
fi

echo ""
echo "Running coverage..."
npm run test:coverage > /dev/null 2>&1
if [ -f coverage/coverage-summary.json ]; then
    COVERAGE=$(node -e "const c=require('./coverage/coverage-summary.json'); console.log('Lines: '+c.total.lines.pct+'% | Branches: '+c.total.branches.pct+'%')")
    echo "  Coverage: $COVERAGE"
fi

cd ..
echo ""

# Backend Tests
echo -e "${YELLOW}Backend Tests:${NC}"
cd backend
echo "Running pytest..."
./run_tests_minimal.py > backend-test-results.txt 2>&1
BACKEND_EXIT=$?

if [ $BACKEND_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ Backend tests passed${NC}"
    PASSED_TESTS=$(grep -E "passed" backend-test-results.txt | tail -1)
    echo "  $PASSED_TESTS"
else
    echo -e "${RED}✗ Backend tests failed${NC}"
    FAILED_TESTS=$(grep -E "failed|error" backend-test-results.txt | tail -1)
    echo "  $FAILED_TESTS"
fi

cd ..
echo ""

# Summary
echo -e "${YELLOW}Test Summary:${NC}"
echo "=================================="

if [ $FRONTEND_EXIT -eq 0 ] && [ $BACKEND_EXIT -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    
    if [ $FRONTEND_EXIT -ne 0 ]; then
        echo -e "  ${RED}Frontend: FAILED${NC}"
        echo "  See frontend/frontend-test-results.txt for details"
    else
        echo -e "  ${GREEN}Frontend: PASSED${NC}"
    fi
    
    if [ $BACKEND_EXIT -ne 0 ]; then
        echo -e "  ${RED}Backend: FAILED${NC}"
        echo "  See backend/backend-test-results.txt for details"
    else
        echo -e "  ${GREEN}Backend: PASSED${NC}"
    fi
    
    exit 1
fi