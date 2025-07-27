#!/bin/bash
set -e

# Function to wait for a service
wait_for_service() {
    local service=$1
    local host=$2
    local port=$3
    local max_attempts=${4:-30}
    local attempt=1

    echo "Waiting for $service at $host:$port..."
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z "$host" "$port" >/dev/null 2>&1; then
            echo "$service is ready!"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts: $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "ERROR: $service failed to become ready"
    return 1
}

# Function to check database connection
check_database() {
    echo "Checking database connection..."
    python -c "
import asyncio
import asyncpg
import os

async def check():
    db_url = os.getenv('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
    try:
        conn = await asyncpg.connect(db_url)
        await conn.fetchval('SELECT 1')
        await conn.close()
        print('Database connection successful!')
        return True
    except Exception as e:
        print(f'Database connection failed: {e}')
        return False

asyncio.run(check())
"
}

# Function to check Redis connection
check_redis() {
    echo "Checking Redis connection..."
    python -c "
import asyncio
import redis.asyncio as redis
import os

async def check():
    redis_url = os.getenv('REDIS_URL', '')
    try:
        client = redis.from_url(redis_url)
        await client.ping()
        await client.close()
        print('Redis connection successful!')
        return True
    except Exception as e:
        print(f'Redis connection failed: {e}')
        return False

asyncio.run(check())
"
}

# Function to run migrations
run_migrations() {
    echo "Running database migrations..."
    if [ -f "alembic.ini" ]; then
        alembic upgrade head
        echo "Migrations completed successfully!"
    else
        echo "WARNING: alembic.ini not found, skipping migrations"
    fi
}

# Main entrypoint logic
main() {
    echo "Starting AgencyDark Backend..."
    echo "Environment: ${ENVIRONMENT:-development}"
    
    # Extract host and port from DATABASE_URL
    if [[ "$DATABASE_URL" =~ @([^:]+):([0-9]+)/ ]]; then
        DB_HOST="${BASH_REMATCH[1]}"
        DB_PORT="${BASH_REMATCH[2]}"
        wait_for_service "PostgreSQL" "$DB_HOST" "$DB_PORT"
        check_database || exit 1
    fi
    
    # Extract host and port from REDIS_URL
    if [[ "$REDIS_URL" =~ @([^:]+):([0-9]+) ]]; then
        REDIS_HOST="${BASH_REMATCH[1]}"
        REDIS_PORT="${BASH_REMATCH[2]}"
        wait_for_service "Redis" "$REDIS_HOST" "$REDIS_PORT"
        check_redis || exit 1
    fi
    
    # Run migrations in production
    if [ "$ENVIRONMENT" = "production" ]; then
        run_migrations
    fi
    
    # Create necessary directories
    mkdir -p logs uploads temp
    
    # Start the application
    echo "Starting application..."
    exec "$@"
}

# Run main function with all arguments
main "$@"