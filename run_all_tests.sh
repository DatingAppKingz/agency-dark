#!/bin/bash

# AgencyDark Complete Testing Suite Runner
# This script runs all tests for the AgencyDark application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
API_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

echo -e "${CYAN}${BOLD}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           AGENCYDARK COMPLETE TESTING SUITE               ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to check if service is running
check_service() {
    local url=$1
    local name=$2
    
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302"; then
        echo -e "${GREEN}✓${NC} $name is running at $url"
        return 0
    else
        echo -e "${RED}✗${NC} $name is not running at $url"
        return 1
    fi
}

# Function to run a test script
run_test() {
    local script=$1
    local name=$2
    
    echo -e "\n${BLUE}${BOLD}Running $name...${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    
    if [ -f "$script" ]; then
        python3 "$script"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ $name completed successfully${NC}"
        else
            echo -e "${YELLOW}⚠ $name completed with warnings${NC}"
        fi
    else
        echo -e "${RED}✗ $script not found${NC}"
    fi
}

# Check prerequisites
echo -e "${BOLD}Checking prerequisites...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python3 installed ($(python3 --version))"
else
    echo -e "${RED}✗${NC} Python3 not found"
    exit 1
fi

# Check required Python packages
echo -e "\n${BOLD}Checking Python packages...${NC}"
packages=("requests" "playwright" "aiohttp")
for package in "${packages[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $package installed"
    else
        echo -e "${YELLOW}⚠${NC} $package not installed - installing..."
        pip3 install $package
    fi
done

# Check services
echo -e "\n${BOLD}Checking services...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

services_ok=true

# Check backend
if ! check_service "$API_URL/docs" "Backend API"; then
    services_ok=false
fi

# Check frontend
if ! check_service "$FRONTEND_URL" "Frontend"; then
    services_ok=false
fi

# Check PostgreSQL
if pg_isready -h localhost 2>/dev/null || /opt/homebrew/opt/postgresql@16/bin/pg_isready -h localhost 2>/dev/null; then
    echo -e "${GREEN}✓${NC} PostgreSQL is running"
else
    echo -e "${RED}✗${NC} PostgreSQL is not running"
    services_ok=false
fi

# Check Redis
if redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo -e "${GREEN}✓${NC} Redis is running"
else
    echo -e "${RED}✗${NC} Redis is not running"
    services_ok=false
fi

if [ "$services_ok" = false ]; then
    echo -e "\n${RED}Some services are not running. Please start them before running tests.${NC}"
    echo -e "${YELLOW}Hint: Run the backend and frontend first${NC}"
    exit 1
fi

# Main test execution
echo -e "\n${CYAN}${BOLD}Starting test execution...${NC}"
echo "════════════════════════════════════════════════════════════════"

# 1. API Functionality Tests
run_test "test_all_functionalities.py" "API Functionality Tests"

# 2. Frontend E2E Tests (if Playwright is installed)
if python3 -c "import playwright" 2>/dev/null; then
    # Check if Chromium is installed for Playwright
    if playwright show chromium 2>/dev/null | grep -q "chromium"; then
        run_test "test_frontend_e2e.py" "Frontend E2E Tests"
    else
        echo -e "\n${YELLOW}Installing Playwright browsers...${NC}"
        playwright install chromium
        run_test "test_frontend_e2e.py" "Frontend E2E Tests"
    fi
else
    echo -e "\n${YELLOW}Skipping Frontend E2E tests (Playwright not installed)${NC}"
fi

# 3. Load Testing (optional)
if [ -f "test_load.py" ]; then
    echo -e "\n${BLUE}${BOLD}Load Testing (Optional)${NC}"
    echo -e "${YELLOW}Run load tests? (y/n):${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        run_test "test_load.py" "Load Tests"
    fi
fi

# Summary
echo -e "\n${CYAN}${BOLD}════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}${BOLD}                    TEST EXECUTION COMPLETE                      ${NC}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════════════════════════════${NC}"

echo -e "\n${BOLD}Test Reports:${NC}"
echo -e "• API test results: See output above"
echo -e "• Frontend screenshots: screenshot_*.png (if any failures)"
echo -e "• Logs: Check backend and frontend console output"

echo -e "\n${GREEN}${BOLD}✨ All tests completed!${NC}"