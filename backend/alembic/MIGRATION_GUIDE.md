# Database Migration Guide

This document describes the conventions and best practices for database migrations in AgencyDark.

## Migration Naming Convention

All migration files follow a strict naming convention to ensure proper ordering and clarity:

```
XXX_description_of_change.py
```

Where:
- `XXX` is a 3-digit sequential number (e.g., 001, 002, 003)
- `description_of_change` is a snake_case description of what the migration does

### Examples:
- `001_initial_schema.py` - Initial database schema
- `002_add_user_roles.py` - Adds role column to users table
- `021_add_missing_core_tables.py` - Adds missing core tables
- `022_add_comprehensive_multi_tenant_indexes.py` - Adds multi-tenant indexes

## Creating a New Migration

1. **Always use the next sequential number**
   ```bash
   # Check the highest numbered migration
   ls alembic/versions/ | sort -n
   
   # If the latest is 024_xxx.py, your new migration should be 025_xxx.py
   ```

2. **Use Alembic to generate the migration template**
   ```bash
   alembic revision -m "add user preferences table"
   ```

3. **Rename the generated file to follow our convention**
   ```bash
   # Alembic generates: abc123_add_user_preferences_table.py
   # Rename to: 025_add_user_preferences_table.py
   mv alembic/versions/abc123_add_user_preferences_table.py alembic/versions/025_add_user_preferences_table.py
   ```

4. **Update the revision ID in the file**
   ```python
   # Change this:
   revision = 'abc123'
   
   # To this:
   revision = '025'
   ```

5. **Update the down_revision to point to the previous migration**
   ```python
   # If the previous migration is 024_xxx.py
   down_revision = '024'
   ```

## Migration Best Practices

### 1. Always Include Both Upgrade and Downgrade

Every migration must be reversible:

```python
def upgrade():
    # Create table
    op.create_table('user_preferences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('theme', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'])

def downgrade():
    # Drop indexes first
    op.drop_index('ix_user_preferences_user_id', 'user_preferences')
    
    # Drop table
    op.drop_table('user_preferences')
```

### 2. Add Indexes for Foreign Keys and Common Queries

Always add indexes for:
- Foreign key columns
- Columns used in WHERE clauses
- Columns used in JOIN conditions
- Composite indexes for multi-column queries

```python
# Single column index
op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])

# Composite index for common query pattern
op.create_index('ix_transactions_user_date', 'transactions', ['user_id', 'created_at'])

# Partial index for specific conditions
op.create_index('ix_active_subscriptions', 'subscriptions', ['user_id'], 
                postgresql_where=text('is_active = true'))
```

### 3. Use Appropriate Column Types

- **UUIDs**: Use for all primary keys and foreign keys
- **Timestamps**: Always include `created_at` and `updated_at`
- **Money**: Use `DECIMAL(10,2)` for currency amounts
- **JSON**: Use `JSONB` for flexible data (PostgreSQL)

```python
sa.Column('id', sa.UUID(), nullable=False, default=uuid4),
sa.Column('amount', sa.DECIMAL(10, 2), nullable=False),
sa.Column('metadata', sa.JSON(), nullable=True),
sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
```

### 4. Handle Multi-Tenant Data

For multi-tenant tables, always:
- Include `agency_id` column
- Add index on `agency_id`
- Consider composite indexes with `agency_id`

```python
sa.Column('agency_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),

# Add indexes
op.create_index('ix_models_agency_id', 'models', ['agency_id'])
op.create_index('ix_models_agency_status', 'models', ['agency_id', 'status'])
```

### 5. Data Migrations

When migrating data, always:
- Use batch operations for large datasets
- Add progress logging
- Make operations idempotent

```python
def upgrade():
    # Add new column with default
    op.add_column('users', sa.Column('display_name', sa.String(100), nullable=True))
    
    # Migrate data in batches
    connection = op.get_bind()
    result = connection.execute("SELECT COUNT(*) FROM users")
    total = result.scalar()
    
    batch_size = 1000
    for offset in range(0, total, batch_size):
        connection.execute(
            text("""
                UPDATE users 
                SET display_name = username 
                WHERE display_name IS NULL 
                AND id IN (
                    SELECT id FROM users 
                    WHERE display_name IS NULL 
                    LIMIT :batch_size OFFSET :offset
                )
            """),
            {"batch_size": batch_size, "offset": offset}
        )
        print(f"Migrated {min(offset + batch_size, total)}/{total} users")
```

## Testing Migrations

### 1. Test Forward Migration
```bash
# Run all migrations
alembic upgrade head

# Verify schema
python scripts/test_migrations.py
```

### 2. Test Rollback
```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 020

# Test full rollback and re-upgrade
alembic downgrade base
alembic upgrade head
```

### 3. Test on Fresh Database
```bash
# Create test database and run all migrations
python scripts/test_migrations.py
```

## Common Issues and Solutions

### 1. Circular Dependencies
If migrations have circular dependencies, refactor into multiple migrations:
```python
# Migration 025: Create tables without foreign keys
def upgrade():
    op.create_table('table_a', ...)
    op.create_table('table_b', ...)

# Migration 026: Add foreign key constraints
def upgrade():
    op.create_foreign_key('fk_a_to_b', 'table_a', 'table_b', ['b_id'], ['id'])
    op.create_foreign_key('fk_b_to_a', 'table_b', 'table_a', ['a_id'], ['id'])
```

### 2. Large Table Alterations
For tables with millions of rows, use online operations:
```python
# Add column without locking
op.add_column('large_table', sa.Column('new_col', sa.String(), nullable=True))

# Add index concurrently (PostgreSQL)
op.create_index('ix_large_table_new_col', 'large_table', ['new_col'], 
                postgresql_concurrently=True)
```

### 3. Renaming Columns
Always use a two-step process:
```python
# Migration 025: Add new column and copy data
def upgrade():
    op.add_column('users', sa.Column('email_address', sa.String(255)))
    op.execute("UPDATE users SET email_address = email")

# Migration 026: Drop old column after code deployment
def upgrade():
    op.drop_column('users', 'email')
```

## Deployment Process

1. **Development**: Create and test migration locally
2. **Review**: Code review includes migration SQL review
3. **Staging**: Deploy to staging and verify
4. **Production**: Deploy during maintenance window

### Pre-deployment Checklist:
- [ ] Migration tested on copy of production data
- [ ] Rollback tested and verified
- [ ] Migration time estimated for production data volume
- [ ] Backup created before deployment
- [ ] Monitoring alerts configured

## Emergency Procedures

### If Migration Fails in Production:

1. **Stop the migration immediately**
   ```bash
   # Kill the migration process
   ```

2. **Assess the damage**
   ```sql
   -- Check migration status
   SELECT * FROM alembic_version;
   
   -- Check for partial changes
   ```

3. **Rollback if safe**
   ```bash
   alembic downgrade -1
   ```

4. **Or restore from backup if necessary**
   ```bash
   # Restore database from backup
   ```

## Migration Performance Tips

1. **Create indexes after data insertion**
2. **Use UNLOGGED tables for temporary data**
3. **Disable triggers during bulk operations**
4. **Use parallel operations when possible**
5. **Monitor disk space during large migrations**

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Best Practices](https://wiki.postgresql.org/wiki/Main_Page)
- [SQLAlchemy Migration Patterns](https://docs.sqlalchemy.org/)