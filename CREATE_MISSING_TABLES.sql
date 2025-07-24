-- Create missing tables for test data generator

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
    fan_id VARCHAR(255) NOT NULL,
    fan_username VARCHAR(255),
    message TEXT NOT NULL,
    is_from_fan BOOLEAN DEFAULT true,
    is_read BOOLEAN DEFAULT false,
    assigned_chatter_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Financial transactions table
CREATE TABLE IF NOT EXISTS financial_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    model_id UUID NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    commission_amount DECIMAL(10, 2),
    status VARCHAR(50) DEFAULT 'pending',
    external_transaction_id VARCHAR(255),
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Commission rules table
CREATE TABLE IF NOT EXISTS commission_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(50),
    rate DECIMAL(5, 2) NOT NULL,
    min_subscribers INTEGER,
    max_subscribers INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Theme configurations table (from whitelabel module)
CREATE TABLE IF NOT EXISTS theme_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    default_mode VARCHAR(10) DEFAULT 'light',
    allow_user_preference BOOLEAN DEFAULT true,
    light_theme JSONB,
    dark_theme JSONB,
    custom_css TEXT,
    font_family VARCHAR(100),
    font_size_base VARCHAR(10),
    layout_config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by UUID REFERENCES users(id),
    UNIQUE(agency_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_messages_model ON chat_messages(model_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_fan ON chat_messages(fan_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);

CREATE INDEX IF NOT EXISTS idx_financial_transactions_agency ON financial_transactions(agency_id);
CREATE INDEX IF NOT EXISTS idx_financial_transactions_model ON financial_transactions(model_id);
CREATE INDEX IF NOT EXISTS idx_financial_transactions_created ON financial_transactions(created_at);

CREATE INDEX IF NOT EXISTS idx_commission_rules_agency ON commission_rules(agency_id);
CREATE INDEX IF NOT EXISTS idx_theme_configuration_agency ON theme_configurations(agency_id);