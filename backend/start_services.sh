#!/bin/bash

# Start Services Script for AgencyDark Backend
# This script starts all required services for the backend

echo "🚀 Starting AgencyDark Backend Services..."
echo "========================================"

# Check if PostgreSQL is running
echo "1. Checking PostgreSQL..."
if pg_isready -h localhost -p 5433 > /dev/null 2>&1; then
    echo "   ✅ PostgreSQL is already running on port 5433"
else
    echo "   ⚠️  PostgreSQL is not running. Starting Docker container..."
    docker run -d \
        --name postgres-agencydark \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=agencydark \
        -p 5433:5432 \
        postgres:16
    
    echo "   ⏳ Waiting for PostgreSQL to be ready..."
    sleep 5
    
    if pg_isready -h localhost -p 5433 > /dev/null 2>&1; then
        echo "   ✅ PostgreSQL started successfully"
    else
        echo "   ❌ Failed to start PostgreSQL"
        exit 1
    fi
fi

# Check if Redis is running
echo -e "\n2. Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "   ✅ Redis is already running"
else
    echo "   ⚠️  Redis is not running. Starting..."
    if command -v brew &> /dev/null; then
        brew services start redis
        echo "   ✅ Redis started via Homebrew"
    else
        redis-server --daemonize yes
        echo "   ✅ Redis started as daemon"
    fi
fi

# Run database migrations
echo -e "\n3. Running database migrations..."
cd /Users/mariuszbudzisz/SourceCode/agency-dark/backend

# Check if alembic is initialized
if [ ! -d "alembic" ]; then
    echo "   ⚠️  Initializing Alembic..."
    alembic init alembic
fi

# Run migrations
echo "   Running migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "   ✅ Migrations completed successfully"
else
    echo "   ⚠️  Migration warnings detected (may be normal for existing tables)"
fi

# Create test users
echo -e "\n4. Creating test users..."
if [ -f "scripts/create_test_users_fixed.py" ]; then
    python3 scripts/create_test_users_fixed.py
    echo "   ✅ Test users created/verified"
else
    echo "   ⚠️  Test user script not found"
fi

# Install missing dependencies
echo -e "\n5. Checking Python dependencies..."
pip3 install xgboost scikit-learn > /dev/null 2>&1
echo "   ✅ ML dependencies installed"

# Start the backend server
echo -e "\n6. Starting backend server..."
echo "========================================"
echo "🌐 Backend will be available at: http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "🔄 Alternative docs: http://localhost:8000/redoc"
echo ""
echo "Test Credentials:"
echo "  Admin: admin@agency.com / admin123"
echo "  Agency Owner: owner@agency.com / owner123"
echo "  Model: model@agency.com / model123"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"

# Set environment variables
export DATABASE_URL="postgresql://postgres:postgres@localhost:5433/agencydark"
export REDIS_URL="redis://localhost:6379"
export DISABLE_ML="false"  # Enable ML features now that dependencies are installed

# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000