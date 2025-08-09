-- Migration to add missing columns to agencies table
-- Run this to align the database with the Agency model

-- Add contact information columns
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS subdomain VARCHAR(100) UNIQUE;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS country VARCHAR(2);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- Add branding columns
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS favicon_url VARCHAR(500);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS primary_color VARCHAR(7) DEFAULT '#3B82F6';
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS secondary_color VARCHAR(7) DEFAULT '#1E40AF';

-- Add features column
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS features JSON DEFAULT '{}';

-- Add commission settings
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS default_commission_rate NUMERIC(5,2) DEFAULT 20.00;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS payment_frequency VARCHAR(20) DEFAULT 'monthly';
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS minimum_payout NUMERIC(10,2) DEFAULT 100.00;

-- Add limits
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS max_models INTEGER DEFAULT 100;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS max_chatters INTEGER DEFAULT 50;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS max_staff INTEGER DEFAULT 20;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS storage_quota_gb INTEGER DEFAULT 100;

-- Add status columns
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS trial_ends_at VARCHAR(30);

-- Add billing columns
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);
ALTER TABLE agencies ADD COLUMN IF NOT EXISTS billing_email VARCHAR(255);

-- Update existing agencies with default email if missing
UPDATE agencies SET email = name || '@agency.com' WHERE email IS NULL;

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_agencies_is_active ON agencies(is_active);
CREATE INDEX IF NOT EXISTS idx_agencies_subdomain ON agencies(subdomain);
CREATE INDEX IF NOT EXISTS idx_agencies_domain ON agencies(domain);