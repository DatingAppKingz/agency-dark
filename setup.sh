#!/bin/bash

echo "🚀 Setting up AgencyDark..."

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration values"
fi

# Start PostgreSQL and Redis
echo "🐘 Starting PostgreSQL and Redis..."
docker-compose up -d db redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Install backend dependencies
echo "🐍 Setting up backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# Setup frontend
echo "📦 Setting up frontend..."
cd frontend
npm init -y
npm install next@latest react@latest react-dom@latest typescript @types/react @types/react-dom @types/node
npm install @mui/material @emotion/react @emotion/styled zustand @tanstack/react-query socket.io-client recharts
cd ..

echo "✅ Setup complete!"
echo ""
echo "To start the development environment:"
echo "  docker-compose up"
echo ""
echo "Or run services individually:"
echo "  Backend: cd backend && source venv/bin/activate && uvicorn main:app --reload"
echo "  Frontend: cd frontend && npm run dev"