-- Local Database Setup for AgencyDark Development

-- Create agency
INSERT INTO agencies (id, name, slug, domain, settings)
VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'Test Agency Premium',
    'test-agency-premium', 
    'premium.testagency.com',
    '{"features": {"analytics": true, "financial": true, "whitelabel": true}, "commission_rate": 0.30}'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    settings = EXCLUDED.settings;

-- Create test users with correct roles
-- Password hash is for "Test123!" generated with passlib bcrypt
INSERT INTO users (id, email, hashed_password, full_name, role, agency_id, is_active, is_verified, created_at, verified_at)
VALUES 
    (gen_random_uuid(), 'super@agencydark.com', '$2b$12$Gs7dz9DjCUFpr/4WO9VTROZV5kLGapmahNev5bjETl3DXAY/3FdGO', 'Super Administrator', 'SUPER_ADMIN', NULL, true, true, NOW(), NOW()),
    (gen_random_uuid(), 'owner@testagency.com', '$2b$12$Gs7dz9DjCUFpr/4WO9VTROZV5kLGapmahNev5bjETl3DXAY/3FdGO', 'John Agency Owner', 'AGENCY_OWNER', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', true, true, NOW(), NOW()),
    (gen_random_uuid(), 'admin@testagency.com', '$2b$12$Gs7dz9DjCUFpr/4WO9VTROZV5kLGapmahNev5bjETl3DXAY/3FdGO', 'Sarah Admin', 'AGENCY_ADMIN', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', true, true, NOW(), NOW()),
    (gen_random_uuid(), 'model@testagency.com', '$2b$12$Gs7dz9DjCUFpr/4WO9VTROZV5kLGapmahNev5bjETl3DXAY/3FdGO', 'Emma Model', 'MODEL', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', true, true, NOW(), NOW()),
    (gen_random_uuid(), 'chatter@testagency.com', '$2b$12$Gs7dz9DjCUFpr/4WO9VTROZV5kLGapmahNev5bjETl3DXAY/3FdGO', 'Chris Chatter', 'CHATTER', 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', true, true, NOW(), NOW())
ON CONFLICT (email) DO UPDATE SET
    role = EXCLUDED.role,
    agency_id = EXCLUDED.agency_id,
    is_active = EXCLUDED.is_active;

-- Get model user ID for creating profile
-- Run this query to get the model user's ID:
SELECT id, email FROM users WHERE email = 'model@testagency.com';

-- Then create model profile (replace USER_ID with actual ID from above query):
/*
INSERT INTO model_profiles (
    user_id,
    agency_id,
    stage_name,
    bio,
    subscription_price,
    onlyfans_username,
    is_active,
    settings,
    assigned_chatters
)
VALUES (
    'USER_ID_FROM_ABOVE',  -- Replace with actual model user ID
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'Emma Rose',
    'Premium content creator | Your favorite model 💕',
    9.99,
    'emmarose_official',
    true,
    '{"auto_reply_enabled": true, "ppv_minimum_price": 10}',
    ARRAY[]::UUID[]
)
ON CONFLICT (user_id) DO UPDATE SET
    stage_name = EXCLUDED.stage_name,
    bio = EXCLUDED.bio,
    is_active = EXCLUDED.is_active;
*/

-- Verify setup
SELECT 
    u.email,
    u.role,
    u.agency_id,
    a.name as agency_name
FROM users u
LEFT JOIN agencies a ON u.agency_id = a.id
WHERE u.email IN ('super@agencydark.com', 'owner@testagency.com', 'admin@testagency.com', 'model@testagency.com', 'chatter@testagency.com')
ORDER BY u.email;

-- Note: All users have the same password hash for "Test123!" for easy testing