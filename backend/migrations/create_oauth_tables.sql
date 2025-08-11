-- Create OAuth tables for AgencyDark
-- Run this with: psql -U mariuszbudzisz -d agencydark_dev -f migrations/create_oauth_tables.sql

-- Create oauth_clients table
CREATE TABLE IF NOT EXISTS oauth_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    client_id VARCHAR(48) UNIQUE NOT NULL,
    client_secret VARCHAR(120),
    client_name VARCHAR(100),
    redirect_uris TEXT[],
    grant_types TEXT[] DEFAULT ARRAY['authorization_code'],
    response_types TEXT[] DEFAULT ARRAY['code'],
    scope TEXT DEFAULT '',
    allowed_agencies UUID[],
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_oauth_clients_agency_id ON oauth_clients(agency_id);
CREATE INDEX IF NOT EXISTS idx_oauth_clients_client_id ON oauth_clients(client_id);

-- Create oauth_tokens table
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id VARCHAR(48) REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
    token_type VARCHAR(40),
    access_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    scope TEXT DEFAULT '',
    expires_at TIMESTAMP WITH TIME ZONE,
    extra_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user_id ON oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_expires_at ON oauth_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_access_token ON oauth_tokens(access_token);

-- Create oauth_authorization_codes table
CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    client_id VARCHAR(48) REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
    code VARCHAR(120) UNIQUE NOT NULL,
    redirect_uri TEXT,
    scope TEXT DEFAULT '',
    code_challenge VARCHAR(128),
    code_challenge_method VARCHAR(10),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oauth_authorization_codes_code ON oauth_authorization_codes(code);

-- Create external_oauth_tokens table (for Instagram, OnlyFans, etc.)
CREATE TABLE IF NOT EXISTS external_oauth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    access_token TEXT NOT NULL, -- Encrypted
    refresh_token TEXT, -- Encrypted
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT,
    raw_data TEXT, -- Encrypted JSON
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_external_oauth_tokens_provider ON external_oauth_tokens(provider, user_id);
CREATE INDEX IF NOT EXISTS idx_external_oauth_tokens_agency_id ON external_oauth_tokens(agency_id);

-- Create oauth_consent_records table for tracking user consent
CREATE TABLE IF NOT EXISTS oauth_consent_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id VARCHAR(48) NOT NULL REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_oauth_consent_records_user_client ON oauth_consent_records(user_id, client_id);

-- Add OAuth fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_verified BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS age_verified_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_metadata JSONB;

-- Create indexes on new user columns
CREATE INDEX IF NOT EXISTS idx_users_oauth_provider ON users(oauth_provider, oauth_id);
CREATE INDEX IF NOT EXISTS idx_users_age_verified ON users(age_verified);

-- Grant permissions (adjust user as needed)
GRANT ALL ON oauth_clients TO mariuszbudzisz;
GRANT ALL ON oauth_tokens TO mariuszbudzisz;
GRANT ALL ON oauth_authorization_codes TO mariuszbudzisz;
GRANT ALL ON external_oauth_tokens TO mariuszbudzisz;
GRANT ALL ON oauth_consent_records TO mariuszbudzisz;