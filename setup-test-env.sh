#!/bin/bash

# AgencyDark Test Environment Setup Script
# This script sets up the test environment for running all tests

set -e

echo "=========================================="
echo "AgencyDark Test Environment Setup"
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

# Check dependencies
echo "Checking dependencies..."

if ! command_exists docker; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies satisfied${NC}"
echo ""

# Start test databases
echo "Starting test databases..."
docker-compose -f docker-compose.test.yml up -d

# Wait for databases to be ready
echo "Waiting for databases to be ready..."
sleep 5

# Check if PostgreSQL is ready
until docker exec agencydark-test-db pg_isready -U postgres > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "\n${GREEN}✓ PostgreSQL is ready${NC}"

# Check if Redis is ready
until docker exec agencydark-test-redis redis-cli ping > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e "${GREEN}✓ Redis is ready${NC}"

# Export test environment variables
echo ""
echo "Setting up environment variables..."
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/agencydark_test"
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/agencydark_test"
export REDIS_URL="redis://localhost:6380"
export ENVIRONMENT="test"

# Create .env.test file
cat > .env.test << EOF
# Test Environment Variables
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/agencydark_test
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/agencydark_test
REDIS_URL=redis://localhost:6380
ENVIRONMENT=test
SECRET_KEY=test-secret-key-for-testing-only
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
EOF

echo -e "${GREEN}✓ Environment variables configured${NC}"

# Install backend dependencies
echo ""
echo "Installing backend dependencies..."
cd backend
poetry install --no-root
cd ..

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "=========================================="
echo -e "${GREEN}Test Environment Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Test databases are running:"
echo "- PostgreSQL: localhost:5433 (user: postgres, pass: postgres)"
echo "- Redis: localhost:6380"
echo ""
echo "To run tests:"
echo "- Backend: cd backend && poetry run pytest"
echo "- Frontend: cd frontend && npm test"
echo "- All tests: ./run-tests-with-coverage.sh"
echo ""
echo "To stop test databases:"
echo "docker-compose -f docker-compose.test.yml down"
echo ""
echo "To remove test data:"
echo "docker-compose -f docker-compose.test.yml down -v"
echo ""