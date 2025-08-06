# RBAC Fix - Detailed Technical Implementation

## Document Version: 1.0
## Date: August 6, 2025
## Purpose: Technical expansion of RBAC_FIX_IMPLEMENTATION_PLAN.md

---

## Phase 1: Preparation and Cleanup - DETAILED

### 1.1 Complete Dependency Audit and Documentation

#### Step 1: Audit Current Dependencies
```bash
# Create a script to audit all imports in the project
cat > audit_dependencies.py << 'EOF'
import ast
import os
from pathlib import Path
from collections import defaultdict

def find_imports(directory):
    imports = defaultdict(set)
    
    for py_file in Path(directory).rglob("*.py"):
        try:
            with open(py_file, 'r') as f:
                tree = ast.parse(f.read())
                
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports[name.name].add(str(py_file))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports[node.module].add(str(py_file))
        except Exception as e:
            print(f"Error parsing {py_file}: {e}")
    
    return imports

# Run audit
backend_imports = find_imports("backend/")
frontend_imports = find_imports("frontend/")  # For Python scripts in frontend

# Generate report
with open("dependency_audit.txt", "w") as f:
    for module, files in sorted(backend_imports.items()):
        f.write(f"\n{module}:\n")
        for file in sorted(files):
            f.write(f"  - {file}\n")
EOF

python3 audit_dependencies.py
```

#### Step 2: Create Comprehensive Requirements Files
```bash
# Create requirements directory structure
mkdir -p requirements

# Base requirements (core functionality)
cat > requirements/base.txt << 'EOF'
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0.post1
pydantic==2.5.0
pydantic-settings==2.1.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9
asyncpg==0.29.0

# Redis
redis==5.0.1
aioredis==2.0.1
hiredis==2.3.2

# Core utilities
python-dotenv==1.0.0
click==8.1.7
httpx==0.25.2
EOF

# Security requirements
cat > requirements/security.txt << 'EOF'
# Authentication & Authorization
passlib[bcrypt]==1.7.4
bcrypt==4.1.1
python-jose[cryptography]==3.5.0
cryptography==41.0.7
PyJWT==2.8.0

# Rate Limiting
slowapi==0.1.9
limits==3.7.0

# Security headers and CORS
secure==0.3.0
python-cors==1.0.0

# Input validation
email-validator==2.1.0
python-magic==0.4.27
EOF

# Development requirements
cat > requirements/development.txt << 'EOF'
# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.25.2
faker==20.1.0
factory-boy==3.3.0

# Code quality
black==23.12.0
isort==5.13.2
flake8==6.1.0
mypy==1.7.1
pylint==3.0.3

# Debugging
ipython==8.18.1
ipdb==0.13.13
rich==13.7.0

# Documentation
mkdocs==1.5.3
mkdocs-material==9.5.2
EOF

# Production requirements
cat > requirements/production.txt << 'EOF'
# Performance
uvloop==0.19.0
orjson==3.9.10
ujson==5.9.0

# Monitoring
prometheus-client==0.19.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-instrumentation-fastapi==0.43b0

# Process management
gunicorn==21.2.0
supervisor==4.2.5
EOF

# ML and Analytics (optional)
cat > requirements/ml.txt << 'EOF'
# Machine Learning
scikit-learn==1.3.2
pandas==2.1.4
numpy==1.26.2
joblib==1.3.2

# Visualization
matplotlib==3.8.2
seaborn==0.13.0
plotly==5.18.0
EOF

# External services
cat > requirements/external.txt << 'EOF'
# AWS
boto3==1.34.11

# Email
aiosmtplib==3.0.1

# SMS
twilio==8.10.3

# Payment
stripe==7.8.0

# Search
elasticsearch==8.11.0

# Internationalization
babel==2.14.0

# File handling
openpyxl==3.1.2
xlsxwriter==3.1.9
reportlab==4.0.8

# Scheduling
croniter==2.0.1
celery==5.3.4
EOF

# Create main requirements file
cat > requirements/all.txt << 'EOF'
-r base.txt
-r security.txt
-r external.txt
EOF

# Create install script
cat > install_requirements.sh << 'EOF'
#!/bin/bash
echo "Installing RBAC Fix requirements..."

# Upgrade pip first
pip install --upgrade pip

# Install base requirements
pip install -r requirements/base.txt

# Install security requirements
pip install -r requirements/security.txt

# Install external services (optional)
read -p "Install external service dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install -r requirements/external.txt
fi

# Install development tools (optional)
read -p "Install development dependencies? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install -r requirements/development.txt
fi

echo "Installation complete!"
EOF

chmod +x install_requirements.sh
```

### 1.2 Create Backup and Rollback Infrastructure

#### Automated Backup Script
```bash
cat > create_backup.sh << 'EOF'
#!/bin/bash
# Comprehensive backup before RBAC fix

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/rbac_fix_${TIMESTAMP}"

echo "Creating backup directory: ${BACKUP_DIR}"
mkdir -p ${BACKUP_DIR}

# 1. Git state backup
echo "Backing up git state..."
git stash save "Pre-RBAC fix backup ${TIMESTAMP}"
git tag "backup-${TIMESTAMP}"

# 2. Database backup
echo "Backing up database..."
pg_dump agencydark_dev > "${BACKUP_DIR}/database_backup.sql"

# 3. Redis backup
echo "Backing up Redis..."
redis-cli --rdb "${BACKUP_DIR}/redis_backup.rdb"

# 4. Configuration files backup
echo "Backing up configuration files..."
cp .env "${BACKUP_DIR}/.env.backup" 2>/dev/null || true
cp .env.* "${BACKUP_DIR}/" 2>/dev/null || true

# 5. Create backup manifest
cat > "${BACKUP_DIR}/manifest.json" << MANIFEST
{
  "timestamp": "${TIMESTAMP}",
  "git_commit": "$(git rev-parse HEAD)",
  "git_branch": "$(git branch --show-current)",
  "database": "agencydark_dev",
  "files_backed_up": [
    "database_backup.sql",
    "redis_backup.rdb",
    ".env files"
  ]
}
MANIFEST

echo "Backup complete: ${BACKUP_DIR}"
echo "To restore, run: ./restore_backup.sh ${BACKUP_DIR}"
EOF

chmod +x create_backup.sh
```

#### Rollback Script
```bash
cat > restore_backup.sh << 'EOF'
#!/bin/bash
# Restore from backup

if [ $# -eq 0 ]; then
    echo "Usage: ./restore_backup.sh <backup_directory>"
    exit 1
fi

BACKUP_DIR=$1

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "Restoring from: $BACKUP_DIR"

# Confirm restoration
read -p "This will overwrite current state. Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# 1. Restore database
if [ -f "$BACKUP_DIR/database_backup.sql" ]; then
    echo "Restoring database..."
    psql agencydark_dev < "$BACKUP_DIR/database_backup.sql"
fi

# 2. Restore Redis
if [ -f "$BACKUP_DIR/redis_backup.rdb" ]; then
    echo "Restoring Redis..."
    redis-cli shutdown
    cp "$BACKUP_DIR/redis_backup.rdb" /var/lib/redis/dump.rdb
    redis-server &
fi

# 3. Restore configuration
if [ -f "$BACKUP_DIR/.env.backup" ]; then
    echo "Restoring configuration..."
    cp "$BACKUP_DIR/.env.backup" .env
fi

echo "Restoration complete!"
EOF

chmod +x restore_backup.sh
```

---

## Phase 2: Module Restructuring - DETAILED

### 2.1 Step-by-Step Module Migration

#### Step 1: Create New Structure (Without Breaking Existing)
```python
# create_new_structure.py
import os
import shutil
from pathlib import Path

def create_security_structure():
    """Create new security module structure alongside existing."""
    
    base_path = Path("backend/core/security_v2")  # Temporary v2 suffix
    
    # Define structure
    structure = {
        "authentication": ["jwt_handler.py", "password_handler.py", "session_manager.py"],
        "authorization": ["rbac_core.py", "permissions.py", "roles.py", "decorators.py"],
        "authorization/feature_permissions": ["reports.py", "analytics.py", "exports.py", "messaging.py"],
        "api_key_management": ["manager.py", "generator.py", "validator.py", "rotation.py", "middleware.py"],
        "rate_limiting": ["limiter.py", "algorithms/__init__.py"],
        "rate_limiting/algorithms": ["token_bucket.py", "sliding_window.py", "adaptive.py"],
        "audit": ["logger.py", "trail.py", "integrity.py"],
        "audit/compliance": ["gdpr.py", "sox.py", "hipaa.py"],
        "utils": ["cache_strategies.py", "permission_optimizer.py", "query_optimization.py"]
    }
    
    # Create directories and files
    for dir_path, files in structure.items():
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py
        (full_path / "__init__.py").touch()
        
        # Create placeholder files
        for file in files:
            if not file.endswith("__init__.py"):
                (full_path / file).write_text(f'"""Module: {dir_path}/{file}"""\n\n# TODO: Implement\n')
    
    print(f"Created new structure at: {base_path}")
    return base_path

# Run creation
create_security_structure()
```

#### Step 2: Migration Mapping
```python
# migration_map.py
"""
Maps old imports to new imports for automated migration.
"""

IMPORT_MAPPING = {
    # Old import -> New import
    "from core.security.api_keys import APIKeyManager": 
        "from core.security.api_key_management.manager import APIKeyManager",
    
    "from core.security import verify_password":
        "from core.security.authentication.password_handler import verify_password",
    
    "from core.security import create_access_token":
        "from core.security.authentication.jwt_handler import create_token",
    
    "from core.security.rate_limiter import RateLimiter":
        "from core.security.rate_limiting.limiter import RateLimiter",
    
    "from core.security.audit import audit_log":
        "from core.security.audit.logger import audit_log",
    
    # Add all mappings...
}

def update_imports_in_file(filepath: str):
    """Update imports in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    for old_import, new_import in IMPORT_MAPPING.items():
        content = content.replace(old_import, new_import)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Updated imports in: {filepath}")

def migrate_all_imports():
    """Migrate all Python files."""
    from pathlib import Path
    
    for py_file in Path("backend").rglob("*.py"):
        if "security_v2" not in str(py_file):  # Skip new modules
            update_imports_in_file(str(py_file))
```

### 2.2 Core Module Implementations

#### Authentication Module
```python
# backend/core/security_v2/authentication/jwt_handler.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from pydantic import BaseModel
from core.config import settings

class TokenData(BaseModel):
    """JWT token payload structure."""
    sub: str  # Subject (user email)
    user_id: str
    role: str
    agency_id: Optional[str] = None
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # JWT ID for revocation

class JWTHandler:
    """Handles JWT token creation and validation."""
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire = timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        self.refresh_token_expire = timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    def create_access_token(
        self, 
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create an access token."""
        to_encode = data.copy()
        
        # Set expiration
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + self.access_token_expire
        
        # Add standard claims
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        # Create token
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        data: Dict[str, Any]
    ) -> str:
        """Create a refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + self.refresh_token_expire
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode a token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return TokenData(**payload)
        except JWTError:
            return None
    
    def revoke_token(self, jti: str):
        """Add token to revocation list (Redis)."""
        # TODO: Implement token revocation using Redis
        pass

# Global instance
jwt_handler = JWTHandler()

# Export convenience functions
create_token = jwt_handler.create_access_token
create_refresh_token = jwt_handler.create_refresh_token
verify_token = jwt_handler.verify_token
```

#### Password Handler
```python
# backend/core/security_v2/authentication/password_handler.py
from passlib.context import CryptContext
from typing import Optional
import secrets
import string

class PasswordHandler:
    """Handles password hashing and verification."""
    
    def __init__(self):
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12
        )
        self.min_length = 8
        self.require_uppercase = True
        self.require_numbers = True
        self.require_special = True
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return self.pwd_context.hash(password)
    
    def verify_password(
        self, 
        plain_password: str, 
        hashed_password: str
    ) -> bool:
        """Verify a password against a hash."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def validate_password_strength(self, password: str) -> tuple[bool, str]:
        """Validate password meets security requirements."""
        if len(password) < self.min_length:
            return False, f"Password must be at least {self.min_length} characters"
        
        if self.require_uppercase and not any(c.isupper() for c in password):
            return False, "Password must contain uppercase letter"
        
        if self.require_numbers and not any(c.isdigit() for c in password):
            return False, "Password must contain number"
        
        if self.require_special and not any(c in string.punctuation for c in password):
            return False, "Password must contain special character"
        
        return True, "Password is valid"
    
    def generate_secure_password(self, length: int = 16) -> str:
        """Generate a secure random password."""
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password
    
    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if password needs rehashing (algorithm update)."""
        return self.pwd_context.needs_update(hashed_password)

# Global instance
password_handler = PasswordHandler()

# Export convenience functions
hash_password = password_handler.hash_password
verify_password = password_handler.verify_password
validate_password = password_handler.validate_password_strength
```

---

## Phase 3: Database Fixes - DETAILED

### 3.1 Model Migration Script
```python
# scripts/fix_models.py
"""
Fix model issues including SQLAlchemy reserved words.
"""
import ast
import os
from pathlib import Path

def fix_metadata_field():
    """Fix metadata field conflict in models."""
    
    model_files = [
        "backend/models/platform_api_key.py",
        # Add other files with metadata field
    ]
    
    for filepath in model_files:
        if not Path(filepath).exists():
            continue
            
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Replace metadata field definition
        old_definition = 'metadata = Column(JSON'
        new_definition = 'key_metadata = Column("metadata", JSON'
        
        if old_definition in content:
            content = content.replace(old_definition, new_definition)
            
            # Add property for backward compatibility
            if "@property" not in content:
                property_code = '''
    @property
    def metadata(self):
        """Backward compatibility property."""
        return self.key_metadata
    
    @metadata.setter
    def metadata(self, value):
        """Backward compatibility setter."""
        self.key_metadata = value
'''
                # Find class end and insert property
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'class PlatformAPIKey' in line:
                        # Find end of class
                        for j in range(i+1, len(lines)):
                            if lines[j] and not lines[j].startswith(' '):
                                # Insert before next class/function
                                lines.insert(j-1, property_code)
                                break
                content = '\n'.join(lines)
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            print(f"Fixed metadata field in: {filepath}")

def fix_import_issues():
    """Fix import statement issues."""
    
    fixes = {
        "from models.webhook import APIKey": "from models.api_key import APIKey",
        # Add more import fixes
    }
    
    for py_file in Path("backend").rglob("*.py"):
        content = py_file.read_text()
        modified = False
        
        for old_import, new_import in fixes.items():
            if old_import in content:
                content = content.replace(old_import, new_import)
                modified = True
        
        if modified:
            py_file.write_text(content)
            print(f"Fixed imports in: {py_file}")

# Run fixes
if __name__ == "__main__":
    print("Fixing model issues...")
    fix_metadata_field()
    fix_import_issues()
    print("Model fixes complete!")
```

### 3.2 Alembic Migration
```python
# alembic/versions/xxx_rbac_model_fixes.py
"""RBAC model fixes

Revision ID: rbac_model_fixes_001
Revises: previous_revision
Create Date: 2025-08-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'rbac_model_fixes_001'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None

def upgrade():
    """Apply RBAC model fixes."""
    
    # Note: Column rename from 'metadata' to 'key_metadata' is handled
    # at the model level using Column("metadata", ...) so no actual
    # database change is needed
    
    # Add any new columns needed for RBAC
    op.add_column('users', 
        sa.Column('mfa_secret', sa.String(255), nullable=True)
    )
    op.add_column('users',
        sa.Column('mfa_enabled', sa.Boolean(), default=False)
    )
    
    # Add indexes for performance
    op.create_index(
        'idx_users_role_active',
        'users',
        ['role', 'is_active']
    )
    
    # Create audit log table if not exists
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('previous_hash', sa.String(64), nullable=True),
        sa.Column('current_hash', sa.String(64), nullable=False),
        sa.Index('idx_audit_logs_timestamp', 'timestamp'),
        sa.Index('idx_audit_logs_user_action', 'user_id', 'action'),
    )

def downgrade():
    """Rollback RBAC model fixes."""
    
    op.drop_table('audit_logs')
    op.drop_index('idx_users_role_active')
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'mfa_secret')
```

---

## Phase 4: Authentication Flow - DETAILED

### 4.1 Unified Auth Endpoint
```python
# backend/api/v1/endpoints/auth_unified.py
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from core.database import get_db
from core.security_v2.authentication import (
    hash_password, verify_password,
    create_token, verify_token, create_refresh_token
)
from core.security_v2.authorization import RBACManager
from models.user import User
from schemas.auth import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)

class UnifiedAuthService:
    """Unified authentication service handling all auth flows."""
    
    async def authenticate_user(
        self,
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """Authenticate a user with email and password."""
        
        # Get user from database
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            return None
        
        # Check if account is active
        if not user.is_active:
            return None
        
        return user
    
    def create_tokens(self, user: User) -> tuple[str, str]:
        """Create access and refresh tokens for user."""
        
        token_data = {
            "sub": user.email,
            "user_id": str(user.id),
            "role": user.role.value,
            "agency_id": str(user.agency_id) if user.agency_id else None
        }
        
        access_token = create_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return access_token, refresh_token
    
    def set_auth_cookies(
        self,
        response: Response,
        access_token: str,
        refresh_token: str
    ):
        """Set secure HTTP-only cookies for tokens."""
        
        # Access token cookie (short-lived)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,  # HTTPS only
            samesite="lax",
            max_age=1800,  # 30 minutes
            path="/"
        )
        
        # Refresh token cookie (long-lived)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=604800,  # 7 days
            path="/api/v1/auth/refresh"  # Limited path
        )

# Initialize service
auth_service = UnifiedAuthService()

@router.post("/login", response_model=TokenResponse)
@router.post("/login-fix", response_model=TokenResponse, deprecated=True)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Unified login endpoint.
    Supports both /login and /login-fix for backward compatibility.
    """
    
    # Authenticate user
    user = await auth_service.authenticate_user(
        db,
        request.email,
        request.password
    )
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    # Create tokens
    access_token, refresh_token = auth_service.create_tokens(user)
    
    # Set cookies
    auth_service.set_auth_cookies(response, access_token, refresh_token)
    
    # Log authentication event
    await audit_log(
        db,
        user_id=user.id,
        action="USER_LOGIN",
        details={"email": user.email}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Refresh token not found")
    
    # Verify refresh token
    token_data = verify_token(refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")
    
    # Get user
    user = await db.get(User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    
    # Create new tokens
    access_token, new_refresh_token = auth_service.create_tokens(user)
    
    # Update cookies
    auth_service.set_auth_cookies(response, access_token, new_refresh_token)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )

@router.post("/logout")
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Logout user and clear cookies."""
    
    # Clear cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    
    # TODO: Add token to revocation list in Redis
    
    return {"message": "Logged out successfully"}
```

---

## Phase 5: Testing Strategy - DETAILED

### 5.1 Unit Tests
```python
# tests/unit/security/test_password_handler.py
import pytest
from core.security_v2.authentication.password_handler import PasswordHandler

class TestPasswordHandler:
    
    @pytest.fixture
    def handler(self):
        return PasswordHandler()
    
    def test_hash_password(self, handler):
        """Test password hashing."""
        password = "TestPassword123!"
        hashed = handler.hash_password(password)
        
        # Hash should be different from original
        assert hashed != password
        
        # Hash should be bcrypt format
        assert hashed.startswith("$2b$")
    
    def test_verify_correct_password(self, handler):
        """Test verifying correct password."""
        password = "TestPassword123!"
        hashed = handler.hash_password(password)
        
        assert handler.verify_password(password, hashed) is True
    
    def test_verify_incorrect_password(self, handler):
        """Test verifying incorrect password."""
        password = "TestPassword123!"
        hashed = handler.hash_password(password)
        
        assert handler.verify_password("WrongPassword", hashed) is False
    
    def test_validate_password_strength(self, handler):
        """Test password strength validation."""
        
        # Too short
        valid, msg = handler.validate_password_strength("Pass1!")
        assert valid is False
        assert "at least 8 characters" in msg
        
        # No uppercase
        valid, msg = handler.validate_password_strength("password123!")
        assert valid is False
        assert "uppercase" in msg
        
        # No number
        valid, msg = handler.validate_password_strength("Password!")
        assert valid is False
        assert "number" in msg
        
        # No special character
        valid, msg = handler.validate_password_strength("Password123")
        assert valid is False
        assert "special character" in msg
        
        # Valid password
        valid, msg = handler.validate_password_strength("ValidPass123!")
        assert valid is True
    
    def test_generate_secure_password(self, handler):
        """Test secure password generation."""
        password = handler.generate_secure_password(16)
        
        assert len(password) == 16
        
        # Should pass validation
        valid, _ = handler.validate_password_strength(password)
        assert valid is True
        
        # Should be unique
        password2 = handler.generate_secure_password(16)
        assert password != password2
```

### 5.2 Integration Tests
```python
# tests/integration/test_auth_flow.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from main import app
from models.user import User, UserRole
from core.security_v2.authentication import hash_password

@pytest.mark.asyncio
class TestAuthenticationFlow:
    
    @pytest.fixture
    async def test_user(self, db: AsyncSession):
        """Create a test user."""
        user = User(
            email="test@example.com",
            hashed_password=hash_password("TestPassword123!"),
            full_name="Test User",
            role=UserRole.USER,
            is_active=True,
            is_verified=True
        )
        db.add(user)
        await db.commit()
        return user
    
    async def test_login_success(self, client: AsyncClient, test_user):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test@example.com"
        
        # Check cookies are set
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies
    
    async def test_login_invalid_password(self, client: AsyncClient, test_user):
        """Test login with invalid password."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "AnyPassword123!"
            }
        )
        
        assert response.status_code == 401
    
    async def test_refresh_token_flow(self, client: AsyncClient, test_user):
        """Test refresh token flow."""
        
        # Login first
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        assert login_response.status_code == 200
        
        # Use refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            cookies=login_response.cookies
        )
        
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert "access_token" in data
        
        # New access token should be different
        assert data["access_token"] != login_response.json()["access_token"]
    
    async def test_logout(self, client: AsyncClient, test_user):
        """Test logout flow."""
        
        # Login first
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        
        # Logout
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {login_response.json()['access_token']}"
            }
        )
        
        assert logout_response.status_code == 200
        
        # Cookies should be cleared
        assert "access_token" not in logout_response.cookies
        assert "refresh_token" not in logout_response.cookies
    
    async def test_protected_endpoint_with_token(self, client: AsyncClient, test_user):
        """Test accessing protected endpoint with valid token."""
        
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        
        # Access protected endpoint
        response = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {login_response.json()['access_token']}"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"
    
    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test accessing protected endpoint without token."""
        
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
```

### 5.3 Performance Tests
```python
# tests/performance/test_auth_performance.py
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest

class TestAuthPerformance:
    
    @pytest.mark.performance
    async def test_login_response_time(self, base_url: str):
        """Test login endpoint response time."""
        
        async with httpx.AsyncClient() as client:
            start = time.time()
            response = await client.post(
                f"{base_url}/api/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "TestPassword123!"
                }
            )
            duration = time.time() - start
        
        assert response.status_code == 200
        assert duration < 0.2  # Should respond within 200ms
    
    @pytest.mark.performance
    async def test_concurrent_logins(self, base_url: str):
        """Test system under concurrent login load."""
        
        async def single_login(client: httpx.AsyncClient, index: int):
            response = await client.post(
                f"{base_url}/api/v1/auth/login",
                json={
                    "email": f"test{index}@example.com",
                    "password": "TestPassword123!"
                }
            )
            return response.status_code, response.elapsed.total_seconds()
        
        async with httpx.AsyncClient() as client:
            # Simulate 100 concurrent logins
            tasks = [
                single_login(client, i) 
                for i in range(100)
            ]
            results = await asyncio.gather(*tasks)
        
        # Check success rate
        success_count = sum(1 for status, _ in results if status == 200)
        assert success_count > 95  # >95% success rate
        
        # Check response times
        response_times = [time for _, time in results]
        avg_time = sum(response_times) / len(response_times)
        assert avg_time < 0.5  # Average under 500ms
```

---

## Phase 6: Monitoring and Observability

### 6.1 Health Check Endpoints
```python
# backend/api/v1/endpoints/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.redis import redis_client
import time

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }

@router.get("/detailed")
async def detailed_health(db: AsyncSession = Depends(get_db)):
    """Detailed health check with component status."""
    
    checks = {}
    
    # Database check
    try:
        await db.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
    # Redis check
    try:
        await redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
    
    # Security module check
    try:
        from core.security_v2 import __version__
        checks["security"] = f"healthy (v{__version__})"
    except Exception as e:
        checks["security"] = f"unhealthy: {str(e)}"
    
    overall_status = "healthy" if all(
        "healthy" in status for status in checks.values()
    ) else "degraded"
    
    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": time.time()
    }
```

---

## Conclusion

This detailed implementation guide provides:

1. **Complete code examples** for each phase
2. **Migration scripts** to safely transition
3. **Comprehensive test suites** for validation
4. **Performance benchmarks** to ensure quality
5. **Monitoring capabilities** for production

The implementation is designed to be:
- **Incremental**: Each phase can be completed independently
- **Reversible**: Rollback procedures at each step
- **Testable**: Comprehensive test coverage
- **Observable**: Health checks and monitoring

Follow this guide alongside the main RBAC_FIX_IMPLEMENTATION_PLAN.md for a successful security system restoration.