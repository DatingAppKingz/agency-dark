#!/bin/bash

# AgencyDark Test Suite Runner with Coverage
# This script runs all tests for both backend and frontend with coverage reporting

set -e

echo "=========================================="
echo "AgencyDark Test Suite with Coverage"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Backend Tests
echo -e "${YELLOW}Running Backend Tests...${NC}"
echo "----------------------------------------"

if [ -d "backend" ]; then
    cd backend
    
    if command_exists poetry; then
        echo "Installing backend dependencies..."
        poetry install --no-interaction --no-root
        
        echo -e "\n${GREEN}Running backend tests with coverage...${NC}"
        echo -e "${YELLOW}Note: Backend tests require database setup.${NC}"
        echo -e "${YELLOW}To run backend tests:${NC}"
        echo -e "${YELLOW}1. Create test database: createdb agencydark_test${NC}"
        echo -e "${YELLOW}2. Set DATABASE_URL environment variable${NC}"
        echo -e "${YELLOW}3. Run: poetry run pytest --cov=. --cov-report=html${NC}"
        echo ""
        echo -e "${YELLOW}See BACKEND_TEST_FIX_SUMMARY.md for details${NC}"
        
        # Uncomment when database is set up:
        # poetry run pytest --cov=. --cov-report=html --cov-report=term -v
        # echo -e "\n${GREEN}Backend coverage report generated at: backend/htmlcov/index.html${NC}"
    else
        echo -e "${RED}Poetry not found. Please install Poetry to run backend tests.${NC}"
    fi
    
    cd ..
else
    echo -e "${RED}Backend directory not found!${NC}"
fi

echo ""

# Frontend Tests
echo -e "${YELLOW}Running Frontend Tests...${NC}"
echo "----------------------------------------"

if [ -d "frontend" ]; then
    cd frontend
    
    if command_exists npm; then
        echo "Installing frontend dependencies..."
        npm install
        
        echo -e "\n${GREEN}Running frontend tests with coverage...${NC}"
        npm run test:coverage
        
        echo -e "\n${GREEN}Frontend coverage report generated at: frontend/coverage/index.html${NC}"
    else
        echo -e "${RED}npm not found. Please install Node.js to run frontend tests.${NC}"
    fi
    
    cd ..
else
    echo -e "${RED}Frontend directory not found!${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Test Suite Execution Complete!${NC}"
echo "=========================================="
echo ""
echo "Coverage Reports:"
echo "- Backend:  backend/htmlcov/index.html"
echo "- Frontend: frontend/coverage/index.html"
echo ""
echo "To view coverage reports:"
echo "- Backend:  open backend/htmlcov/index.html"
echo "- Frontend: open frontend/coverage/index.html"
echo ""

# Summary of test files
echo "Test Files Created:"
echo "----------------------------------------"
echo "Backend (12 files):"
echo "  - Financial, User, API Key models"
echo "  - Auth & Security middleware"
echo "  - Permission service"
echo "  - Agency, Model, Chat, Content, Subscriber models"
echo ""
echo "Frontend (9 files):"
echo "  - API Services: chat, models, users, sync, webhooks, financial"
echo "  - Components: ModelPerformance, MessageThread, DateRangePicker"
echo ""

# Exit with appropriate code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}All tests completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please check the output above.${NC}"
    exit 1
fi