#!/bin/bash

# Start backend server for testing auth flow
echo "Starting backend server for auth testing..."

# Set environment variables
export DATABASE_URL="postgresql://mariuszbudzisz@localhost/agencydark_dev"
export REDIS_URL="redis://localhost:6379"
export SECRET_KEY="test-secret-key-for-development"
export JWT_SECRET_KEY="test-jwt-secret-key"
export JWT_ALGORITHM="HS256"
export JWT_ACCESS_TOKEN_EXPIRE_MINUTES="30"
export ACCESS_TOKEN_EXPIRE_MINUTES="30"
export REFRESH_TOKEN_EXPIRE_DAYS="7"
export ENVIRONMENT="development"
export ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8000"

# Kill any existing process on port 8000
echo "Checking for existing processes on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Start the server
echo "Starting server..."
python3 main.py