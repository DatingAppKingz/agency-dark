-- Migration to fix sessions table to match ORM model
-- This aligns the sessions table with what the Session model expects

-- Add missing columns
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS token VARCHAR(500);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS device_type VARCHAR(50);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS device_name VARCHAR(255);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS location VARCHAR(255);
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS refresh_expires_at TIMESTAMP;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Fix data type mismatches
ALTER TABLE sessions ALTER COLUMN ip_address TYPE VARCHAR(45) USING ip_address::VARCHAR(45);
ALTER TABLE sessions ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE USING expires_at AT TIME ZONE 'UTC';
ALTER TABLE sessions ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;

-- Rename refreshed_at to last_activity_at if it exists
DO $$ 
BEGIN
    IF EXISTS(SELECT 1 FROM information_schema.columns 
              WHERE table_name='sessions' AND column_name='refreshed_at') THEN
        ALTER TABLE sessions RENAME COLUMN refreshed_at TO last_activity_at;
    END IF;
END $$;

-- Update existing sessions with token from refresh_token if token is null
UPDATE sessions SET token = SUBSTRING(refresh_token, 1, 50) WHERE token IS NULL AND refresh_token IS NOT NULL;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_is_active ON sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity_at);

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at 
    BEFORE UPDATE ON sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();