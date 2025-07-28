-- AgencyDark Database Initialization Script
-- This script sets up the initial database schema and configurations

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create custom types
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'agency_owner', 'agency_staff', 'model', 'fan');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE subscription_status AS ENUM ('active', 'canceled', 'expired', 'trialing');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create indexes for better performance
-- These will be created after tables are populated by migrations

-- Database configuration
ALTER DATABASE agencydark SET statement_timeout = '30s';
ALTER DATABASE agencydark SET lock_timeout = '10s';
ALTER DATABASE agencydark SET idle_in_transaction_session_timeout = '60s';

-- Create read-only user for analytics (optional)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'agencydark_readonly') THEN
      CREATE ROLE agencydark_readonly WITH LOGIN PASSWORD 'readonly_password_change_me';
      GRANT CONNECT ON DATABASE agencydark TO agencydark_readonly;
      GRANT USAGE ON SCHEMA public TO agencydark_readonly;
      GRANT SELECT ON ALL TABLES IN SCHEMA public TO agencydark_readonly;
      ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agencydark_readonly;
   END IF;
END
$do$;

-- Performance optimization settings
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';