# Claude Session Memory - Authentication Fix
**Last Updated**: 2025-08-06
**Critical Context**: Fixing RBAC authentication that broke on Aug 5-6

## 🚨 CRITICAL REQUIREMENTS (USER MANDATES)
1. **NO SIMPLIFIED FLOWS** - Fix the actual flow, don't create simplified versions
2. **NO NEW MODULES** - Modify existing files only (no security_v2, no auth_simple)  
3. **NO PASSWORD HASHING** - Plain text passwords only, direct string comparison
4. **KEEP IT SIMPLE** - Don't overcomplicate with unnecessary security features

## 🔴 Current Issues to Fix

### Primary Issue: SQLAlchemy ORM Mapper Failure
```
InvalidRequestError: One or more mappers failed to initialize - can't proceed with initialization of other mappers. 
Triggering mapper: 'Mapper[AuditLog(audit_logs)]'
```

**Root Cause**: Model-Database Schema Mismatch
- Database uses UUID primary keys
- Models were using Integer primary keys
- AuditLog relationships can't resolve foreign keys

**Partial Fix Applied**:
- ✅ Changed BaseModel to use UUID: `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`
- ✅ Updated User model to use UUID
- ❌ AuditLog relationships still fail due to SQLAlchemy mapper cache

### Secondary Issues
1. **Cookie DateTime Error**: `ValueError: usegmt option requires a UTC datetime`
   - Fix: Use `datetime.now(timezone.utc)` instead of `datetime.utcnow()`

2. **Circular Imports**: core/security <-> auth modules
   - Fix: Remove circular dependencies

## ✅ What's Working

### Database Structure
```sql
-- Users table (PostgreSQL)
id: UUID (primary key)
email: varchar(255)
hashed_password: varchar(255)  -- Contains plain text despite column name
role: userrole enum
```

### Working Credentials
- Email: `admin@agency.com`
- Password: `admin123` (plain text)
- Role: `SUPER_ADMIN`

### Working Code Pattern
```python
# Authentication that works (from auth_simple.py)
from sqlalchemy import text

# Use raw SQL to avoid ORM mapper issues
result = await db.execute(
    text("SELECT id, email, hashed_password, is_active, role FROM users WHERE email = :email"),
    {"email": credentials.email}
)
user = result.fetchone()

# Plain text password verification
if not user or credentials.password != user.hashed_password:
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

## 🎯 Correct Implementation Approach

### Step 1: Fix Password Verification
```python
# In core/security/auth_simple.py
def verify_password(plain_password: str, stored_password: str) -> bool:
    return plain_password == stored_password  # NO HASHING

def get_password_hash(password: str) -> str:
    return password  # Return as-is, NO HASHING
```

### Step 2: Fix Auth Endpoint (WITHOUT creating new files)
```python
# In api/v1/endpoints/auth.py - Replace ORM with raw SQL
from sqlalchemy import text

# Instead of:
# user = await db.query(User).filter(User.email == email).first()

# Use:
result = await db.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}
)
user = result.fetchone()
```

### Step 3: Fix Model Definitions
```python
# In models/base.py
from sqlalchemy.dialects.postgresql import UUID
import uuid

class BaseModel(Base):
    __abstract__ = True
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # NOT: id = Column(Integer, primary_key=True)
```

### Step 4: Handle AuditLog Issues
- Either fix relationships with proper primaryjoin expressions
- OR disable AuditLog temporarily by commenting out relationships
- OR use raw SQL for all audit operations

## 🛠️ Commands & Environment

### Start Backend Correctly
```bash
# Kill any existing Python processes
pkill -f "python.*main"

# Set environment variables
export DATABASE_URL="postgresql://mariuszbudzisz@localhost/agencydark_dev"
export REDIS_URL="redis://localhost:6379"
export JWT_SECRET_KEY="your-secret-key-here"
export JWT_ALGORITHM="HS256"
export JWT_ACCESS_TOKEN_EXPIRE_MINUTES="30"
export DISABLE_ML="true"

# Run with venv Python (has all dependencies)
venv/bin/python main.py
```

### Test Authentication
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@agency.com", "password": "admin123"}'

# Test with token
TOKEN="<token-from-login>"
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Check Database
```bash
# Connect to PostgreSQL
/opt/homebrew/opt/postgresql@16/bin/psql -U mariuszbudzisz -d agencydark_dev

# Check user
SELECT email, hashed_password, role FROM users WHERE email = 'admin@agency.com';
```

## ⚠️ Common Pitfalls to Avoid

1. **DON'T** create new modules (auth_simple.py, security_v2, etc.)
2. **DON'T** use bcrypt or any password hashing
3. **DON'T** use ORM queries if they trigger mapper errors - use raw SQL
4. **DON'T** assume Integer IDs - database uses UUIDs
5. **DON'T** use `datetime.utcnow()` - use `datetime.now(timezone.utc)`
6. **DON'T** create simplified flows - fix the actual implementation

## 📋 Next Session Action Plan

1. **Clear SQLAlchemy Cache**: Kill all Python processes first
2. **Fix AuditLog Relationships**: Add proper primaryjoin expressions or disable
3. **Update Original Auth Endpoint**: Use raw SQL instead of ORM
4. **Test Full Flow**: Ensure login works without creating new files
5. ~~**Clean Up**: Remove any temporary files (auth_simple.py, etc.)~~ ✅ COMPLETED

## ✅ Cleanup Completed (2025-08-06 Evening)

### Files Removed:
- `main_minimal.py`, `main_auth.py`, `main_with_auth.py`
- `auth_simple.py`, `secrets_minimal.py`, `simple_cache.py`
- `users_simple.py`, `user_simple.py`, `test_user_simple.py`
- All `simple_*.py` endpoint files
- All `*minimal*.log` and `*simple*.log` files
- `create_admin.py`, `seed_data.py`, `fix_auth_imports.sh`

### References Fixed:
- Removed imports of `auth_simple` from all endpoint files
- Updated to use `core.dependencies.CurrentUser` instead
- Removed `auth_simple` references from `core/security/__init__.py`
- Removed `auth_simple` references from `core/auth/__init__.py`
- Cleaned up all pycache directories

### Current State:
- NO simplified flows exist anymore
- Original auth endpoint ready to be fixed properly
- Plain text password functions implemented directly in `core/security/__init__.py`
- All imports point to proper dependencies, not simplified versions

## 🎓 Key Learnings

1. **Database First**: Always check actual database schema before changing models
2. **Raw SQL Fallback**: When ORM fails, use text() queries
3. **User Requirements**: Follow explicit instructions (no hashing, no new modules)
4. **Mapper Cache**: SQLAlchemy caches mappers - kill Python to clear
5. **Simple Solutions**: Don't overcomplicate - user wants simple, working auth

## File Locations
- Main backend: `/Users/mariuszbudzisz/SourceCode/agency-dark/backend/main.py`
- Auth endpoint: `/Users/mariuszbudzisz/SourceCode/agency-dark/backend/api/v1/endpoints/auth.py`
- Security module: `/Users/mariuszbudzisz/SourceCode/agency-dark/backend/core/security/`
- Models: `/Users/mariuszbudzisz/SourceCode/agency-dark/backend/models/`
- Database config: `/Users/mariuszbudzisz/SourceCode/agency-dark/backend/core/database.py`

---
**Remember**: The user wants the ACTUAL flow fixed, not workarounds or simplified versions. 
NO password hashing, NO new modules, MODIFY existing files only.