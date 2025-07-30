#!/bin/bash

echo "Waiting for Docker to start..."

while ! docker info > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done

echo ""
echo "✅ Docker is running!"
echo ""

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "✅ Docker Compose is available"
    docker-compose version
else
    echo "❌ Docker Compose not found"
    exit 1
fi

echo ""
echo "Ready to start AgencyDark services!"