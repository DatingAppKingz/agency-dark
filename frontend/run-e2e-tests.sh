#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Starting E2E Tests for Agency Dark${NC}"
echo "================================================"

# Check if backend is running
echo -e "\n${YELLOW}Checking backend status...${NC}"
if ! curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo -e "${RED}❌ Backend is not running!${NC}"
    echo "Please start the backend first with: cd ../backend && python main.py"
    exit 1
fi
echo -e "${GREEN}✅ Backend is running${NC}"

# Check if frontend dev server is running
echo -e "\n${YELLOW}Checking frontend status...${NC}"
if ! curl -s http://localhost:5173 > /dev/null; then
    echo -e "${YELLOW}⚠️  Frontend dev server is not running${NC}"
    echo "Starting frontend dev server..."
    npm run dev &
    DEV_PID=$!
    sleep 5
else
    echo -e "${GREEN}✅ Frontend is running${NC}"
fi

# Run E2E tests
echo -e "\n${YELLOW}Running E2E tests...${NC}"
echo "================================================"

# Run specific test suites or all tests
if [ "$1" ]; then
    echo "Running specific test: $1"
    npm run test:e2e -- "$1"
else
    echo "Running all E2E tests"
    npm run test:e2e
fi

TEST_EXIT_CODE=$?

# Cleanup
if [ ! -z "$DEV_PID" ]; then
    echo -e "\n${YELLOW}Stopping frontend dev server...${NC}"
    kill $DEV_PID
fi

# Report results
echo -e "\n================================================"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All E2E tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo "Check the test report in: playwright-report/index.html"
    echo "Run 'npx playwright show-report' to view the report"
fi

exit $TEST_EXIT_CODE