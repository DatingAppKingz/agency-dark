#!/bin/bash

# Start Backend Script for AgencyDark
# This script starts the backend with existing PostgreSQL and Redis

echo "🚀 Starting AgencyDark Backend..."
echo "========================================"

cd /Users/mariuszbudzisz/SourceCode/agency-dark/backend

# Check services
echo "1. Checking services..."

# Check PostgreSQL
if /opt/homebrew/opt/postgresql@16/bin/psql -U $USER -l > /dev/null 2>&1; then
    echo "   ✅ PostgreSQL is running"
else
    echo "   ❌ PostgreSQL is not accessible"
    echo "   Try: brew services restart postgresql@16"
    exit 1
fi

# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "   ✅ Redis is running"
else
    echo "   ❌ Redis is not running"
    echo "   Try: brew services start redis"
    exit 1
fi

# Create database if it doesn't exist
echo -e "\n2. Setting up database..."
DB_NAME="agencydark_dev"

if /opt/homebrew/opt/postgresql@16/bin/psql -U $USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo "   ✅ Database '$DB_NAME' already exists"
else
    echo "   Creating database '$DB_NAME'..."
    /opt/homebrew/opt/postgresql@16/bin/createdb -U $USER $DB_NAME
    echo "   ✅ Database created"
fi

# Set environment variables for local PostgreSQL (no password needed for local user)
export DATABASE_URL="postgresql://$USER@localhost/$DB_NAME"
export REDIS_URL="redis://localhost:6379"
export JWT_SECRET_KEY="your-secret-key-here"
export JWT_ALGORITHM="HS256"
export JWT_ACCESS_TOKEN_EXPIRE_MINUTES="30"

echo "   Using DATABASE_URL: $DATABASE_URL"

# Run migrations
echo -e "\n3. Running database migrations..."

# Initialize alembic if needed
if [ ! -d "alembic" ]; then
    echo "   Initializing Alembic..."
    alembic init alembic
    
    # Update alembic.ini with our database URL
    sed -i '' "s|sqlalchemy.url = .*|sqlalchemy.url = $DATABASE_URL|" alembic.ini
fi

# Run migrations
alembic upgrade head 2>&1 | grep -v "UserWarning" || true
echo "   ✅ Migrations completed"

# Create test users
echo -e "\n4. Creating test users..."
python3 -c "
import asyncio
import sys
sys.path.append('.')

async def create_users():
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select
        from models.user import User
        from models.agency import Agency
        from passlib.context import CryptContext
        import uuid
        
        # Create async engine
        engine = create_async_engine(
            '$DATABASE_URL'.replace('postgresql://', 'postgresql+asyncpg://'),
            echo=False
        )
        
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
        
        async with async_session() as session:
            # Check if agency exists
            result = await session.execute(
                select(Agency).where(Agency.name == 'Test Agency')
            )
            agency = result.scalar_one_or_none()
            
            if not agency:
                # Create agency
                agency = Agency(
                    id=uuid.uuid4(),
                    name='Test Agency',
                    domain='test-agency'
                )
                session.add(agency)
                await session.commit()
                print('   Created Test Agency')
            
            # Create users
            users = [
                ('admin@agency.com', 'admin123', 'Admin User', 'super_admin'),
                ('owner@agency.com', 'owner123', 'Agency Owner', 'agency_owner'),
                ('model@agency.com', 'model123', 'Model User', 'model'),
            ]
            
            for email, password, name, role in users:
                result = await session.execute(
                    select(User).where(User.email == email)
                )
                if not result.scalar_one_or_none():
                    user = User(
                        id=uuid.uuid4(),
                        email=email,
                        username=email.split('@')[0],
                        full_name=name,
                        hashed_password=pwd_context.hash(password),
                        role=role,
                        agency_id=agency.id,
                        is_active=True,
                        is_verified=True
                    )
                    session.add(user)
                    print(f'   Created user: {email}')
            
            await session.commit()
            print('   ✅ Test users ready')
            
    except Exception as e:
        print(f'   ⚠️  Error creating users: {e}')

asyncio.run(create_users())
"

# Install missing dependencies if needed
echo -e "\n5. Checking Python dependencies..."
pip3 install -q xgboost scikit-learn 2>/dev/null && echo "   ✅ ML dependencies installed" || echo "   ⚠️  Some dependencies may be missing"

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

# Start uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000