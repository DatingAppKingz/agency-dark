# Troubleshooting Guide

This guide helps you resolve common issues with the AgencyDark backend.

## 🔍 Common Issues

### 1. Database Connection Errors

#### Error: `asyncpg.exceptions.InvalidCatalogNameError: database "agencydark" does not exist`

**Solution:**
```bash
# Create the database
createdb agencydark

# Or using psql
psql -U postgres -c "CREATE DATABASE agencydark;"
```

#### Error: `FATAL: password authentication failed`

**Solution:**
1. Check your DATABASE_URL in .env
2. Ensure PostgreSQL is running
3. Verify user credentials:
```bash
psql -U your_user -d postgres
```

#### Error: `asyncpg.exceptions.UndefinedTableError`

**Solution:**
```bash
# Run migrations
alembic upgrade head

# If migrations fail, check current state
alembic current
alembic history
```

### 2. Redis Connection Issues

#### Error: `redis.exceptions.ConnectionError: Error -2 connecting to redis:6379`

**Solution:**
1. Ensure Redis is running:
```bash
# Check Redis status
redis-cli ping

# Start Redis
redis-server
```

2. Verify REDIS_URL in .env:
```bash
REDIS_URL=redis://localhost:6379/0
```

### 3. Import Errors

#### Error: `ModuleNotFoundError: No module named 'core'`

**Solution:**
1. Ensure PYTHONPATH is set:
```bash
export PYTHONPATH=/path/to/agency-dark/backend:$PYTHONPATH
```

2. Or run from the backend directory:
```bash
cd backend
python main.py
```

### 4. Migration Issues

#### Error: `alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'`

**Solution:**
1. Check migration files exist:
```bash
ls alembic/versions/
```

2. Reset to a known revision:
```bash
alembic downgrade base
alembic upgrade head
```

3. If corrupted, manually fix alembic_version table:
```sql
SELECT * FROM alembic_version;
UPDATE alembic_version SET version_num = 'known_good_revision';
```

### 5. Authentication Issues

#### Error: `401 Unauthorized`

**Solution:**
1. Check token expiration
2. Verify SECRET_KEY hasn't changed
3. Clear browser cookies/localStorage
4. Generate new token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@agencydark.com", "password": "your_password"}'
```

### 6. File Upload Issues

#### Error: `413 Request Entity Too Large`

**Solution:**
1. Check MAX_UPLOAD_SIZE in .env
2. Update Nginx config if using reverse proxy:
```nginx
client_max_body_size 100M;
```

#### Error: `Permission denied: '/app/uploads'`

**Solution:**
```bash
# Create directories with proper permissions
mkdir -p uploads logs exports temp
chmod 755 uploads logs exports temp
```

### 7. External API Issues

#### Stripe: `Invalid API Key provided`

**Solution:**
1. Verify STRIPE_SECRET_KEY in .env
2. Check if using test vs live keys
3. Validate in Stripe dashboard

#### OnlyFans API: `Authentication failed`

**Solution:**
1. Check API credentials are current
2. Verify IP whitelist in OnlyFans settings
3. Test with curl:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://onlyfans.com/api2/v2/users/me
```

### 8. Performance Issues

#### Slow API Responses

**Solution:**
1. Check database queries:
```python
# Enable query logging
DATABASE_ECHO=true
```

2. Monitor with built-in profiling:
```
GET /api/v1/debug/profile?duration=30
```

3. Check indexes exist:
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'your_table';
```

#### High Memory Usage

**Solution:**
1. Reduce worker count:
```bash
WORKERS=2  # Instead of 4
```

2. Check for memory leaks:
```python
# Add to main.py
import tracemalloc
tracemalloc.start()
```

### 9. Docker Issues

#### Error: `docker: Error response from daemon: Ports are not available`

**Solution:**
```bash
# Check what's using port 8000
lsof -i :8000
# Or
netstat -tulpn | grep 8000

# Kill the process or use different port
docker run -p 8001:8000 ...
```

#### Error: `standard_init_linux.go:228: exec user process caused: no such file or directory`

**Solution:**
1. Check line endings (CRLF vs LF)
2. Rebuild with proper base image:
```bash
docker build --no-cache -t agencydark-backend .
```

### 10. Celery/Task Issues

#### Tasks Not Executing

**Solution:**
1. Ensure Celery worker is running:
```bash
celery -A tasks.celery_app worker --loglevel=info
```

2. Check Redis connectivity
3. Verify task is registered:
```python
from tasks.celery_app import celery_app
print(celery_app.tasks)
```

## 🛠️ Debugging Tools

### 1. Enable Debug Mode
```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### 2. Database Query Logging
```python
# In main.py
app.add_middleware(DatabaseQueryLoggingMiddleware, slow_query_threshold=0.1)
```

### 3. Request/Response Logging
```bash
# View structured logs
tail -f logs/app.log | jq '.'
```

### 4. Performance Profiling
```bash
# CPU profiling
python -m cProfile -o profile.stats main.py

# Memory profiling
python -m memory_profiler main.py
```

### 5. API Testing
```bash
# Health check
curl http://localhost:8000/health

# With authentication
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/users/me
```

## 📊 Monitoring

### Check Application Metrics
```bash
curl http://localhost:8000/metrics
```

### View Logs
```bash
# Application logs
docker logs agencydark-backend

# With timestamps
docker logs -t agencydark-backend

# Follow logs
docker logs -f agencydark-backend
```

### Database Diagnostics
```sql
-- Check active connections
SELECT pid, usename, application_name, client_addr, state 
FROM pg_stat_activity;

-- Check slow queries
SELECT query, calls, mean_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;

-- Check table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## 🚨 Emergency Procedures

### 1. Application Won't Start
```bash
# Check syntax errors
python -m py_compile main.py

# Run with minimal config
python main.py --workers=1 --no-reload
```

### 2. Database Locked
```sql
-- Kill all connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = 'agencydark' AND pid <> pg_backend_pid();
```

### 3. Redis Memory Full
```bash
# Clear Redis cache
redis-cli FLUSHDB

# Check memory usage
redis-cli INFO memory
```

### 4. Restore from Backup
```bash
# Database restore
pg_restore -U postgres -d agencydark backup.dump

# File restore
aws s3 sync s3://backup-bucket/uploads ./uploads
```

## 📞 Getting Help

1. **Check Logs First**: Most issues are revealed in logs
2. **Search Error Messages**: Copy exact error messages
3. **Provide Context**: Include OS, Python version, and .env (without secrets)
4. **Create Minimal Reproduction**: Isolate the issue

### Useful Commands
```bash
# System info
python --version
pip list | grep -E "fastapi|sqlalchemy|redis"
postgres --version
redis-server --version

# Environment check
python -c "import sys; print(sys.path)"
env | grep -E "DATABASE|REDIS|PYTHON"
```

## 🔗 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Guide](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Docker Debugging](https://docs.docker.com/config/containers/logging/)