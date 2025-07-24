-- Fix User Roles and Create Complete Test Data
-- Run this against the Supabase database to fix all data issues

-- Step 1: Create agencies if they don't exist
INSERT INTO agencies (id, name, slug, domain, subscription_status, created_at, updated_at)
VALUES 
  ('a1111111-1111-1111-1111-111111111111', 'Test Agency Premium', 'test-agency-premium', 'testagency.com', 'ACTIVE', NOW(), NOW()),
  ('a2222222-2222-2222-2222-222222222222', 'Competitor Agency', 'competitor-agency', 'competitor.com', 'ACTIVE', NOW(), NOW())
ON CONFLICT (slug) DO UPDATE SET
  name = EXCLUDED.name,
  domain = EXCLUDED.domain,
  subscription_status = EXCLUDED.subscription_status,
  updated_at = NOW();

-- Step 2: Update user roles and link to agencies
UPDATE users SET 
  role = 'AGENCY_OWNER',
  agency_id = (SELECT id FROM agencies WHERE slug = 'test-agency-premium')
WHERE email = 'owner@testagency.com';

UPDATE users SET 
  role = 'AGENCY_ADMIN',
  agency_id = (SELECT id FROM agencies WHERE slug = 'test-agency-premium')
WHERE email = 'admin@testagency.com';

UPDATE users SET 
  role = 'MODEL',
  agency_id = (SELECT id FROM agencies WHERE slug = 'test-agency-premium')
WHERE email = 'model@testagency.com';

UPDATE users SET 
  role = 'CHATTER',
  agency_id = (SELECT id FROM agencies WHERE slug = 'test-agency-premium')
WHERE email = 'chatter@testagency.com';

UPDATE users SET 
  role = 'AGENCY_MEMBER',
  agency_id = (SELECT id FROM agencies WHERE slug = 'test-agency-premium')
WHERE email = 'member@testagency.com';

UPDATE users SET 
  role = 'AGENCY_OWNER',
  agency_id = (SELECT id FROM agencies WHERE slug = 'competitor-agency')
WHERE email = 'owner@competitor.com';

-- Step 3: Create model profile for MODEL user
INSERT INTO model_profiles (
    id, user_id, agency_id, stage_name, onlyfans_username,
    bio, subscription_price, is_active,
    inflow_api_key, inflow_account_id,
    onlyfans_api_key, onlyfans_user_id,
    settings, assigned_chatters,
    created_at, updated_at
)
SELECT 
    'mp111111-1111-1111-1111-111111111111',
    u.id,
    u.agency_id,
    'Emma Rose',
    'emmarose_of',
    'Premium content creator | DM for customs',
    9.99,
    true,
    'test_inflow_key_123',
    'inflow_account_emma',
    'test_of_key_123',
    'of_user_emma_123',
    '{"auto_reply_enabled": true, "ppv_minimum_price": 10}'::jsonb,
    ARRAY[(SELECT id FROM users WHERE email = 'chatter@testagency.com')],
    NOW(),
    NOW()
FROM users u
WHERE u.email = 'model@testagency.com'
ON CONFLICT (id) DO UPDATE SET
    stage_name = EXCLUDED.stage_name,
    assigned_chatters = EXCLUDED.assigned_chatters,
    updated_at = NOW();

-- Step 4: Create commission rules for agencies
INSERT INTO commission_rules (
    id, agency_id, name, tier, percentage,
    min_subscribers, max_subscribers, is_active,
    description, created_at, updated_at
)
SELECT 
    gen_random_uuid(),
    a.id,
    CASE tier_num 
        WHEN 1 THEN 'Tier 1 - Starter'
        WHEN 2 THEN 'Tier 2 - Growth'
        WHEN 3 THEN 'Tier 3 - Premium'
    END,
    CASE tier_num 
        WHEN 1 THEN 'TIER_1'
        WHEN 2 THEN 'TIER_2'
        WHEN 3 THEN 'TIER_3'
    END::commissiontier,
    CASE tier_num
        WHEN 1 THEN 70.00
        WHEN 2 THEN 65.00
        WHEN 3 THEN 60.00
    END,
    CASE tier_num
        WHEN 1 THEN 0
        WHEN 2 THEN 5001
        WHEN 3 THEN 10001
    END,
    CASE tier_num
        WHEN 1 THEN 5000
        WHEN 2 THEN 10000
        WHEN 3 THEN NULL
    END,
    true,
    CASE tier_num
        WHEN 1 THEN '70% commission for models with 0-5,000 subscribers'
        WHEN 2 THEN '65% commission for models with 5,001-10,000 subscribers'
        WHEN 3 THEN '60% commission for models with 10,000+ subscribers'
    END,
    NOW(),
    NOW()
FROM agencies a
CROSS JOIN (VALUES (1), (2), (3)) AS tiers(tier_num)
WHERE a.slug IN ('test-agency-premium', 'competitor-agency')
ON CONFLICT DO NOTHING;

-- Step 5: Create current billing cycle for agencies
INSERT INTO billing_cycles (
    id, agency_id, start_date, end_date, is_closed,
    total_revenue, total_commission, total_payout,
    created_at, updated_at
)
SELECT
    gen_random_uuid(),
    a.id,
    date_trunc('month', CURRENT_DATE)::date,
    (date_trunc('month', CURRENT_DATE) + interval '1 month' - interval '1 day')::date,
    false,
    0.00,
    0.00,
    0.00,
    NOW(),
    NOW()
FROM agencies a
WHERE a.slug IN ('test-agency-premium', 'competitor-agency')
  AND NOT EXISTS (
    SELECT 1 FROM billing_cycles bc 
    WHERE bc.agency_id = a.id 
      AND bc.start_date = date_trunc('month', CURRENT_DATE)::date
  );

-- Step 6: Create some sample analytics data for the model
INSERT INTO metric_snapshots (
    id, model_id, snapshot_date,
    subscriber_count, total_revenue, message_count,
    ppv_count, tip_count, post_count,
    new_subscribers, churned_subscribers,
    metrics, created_at
)
SELECT
    gen_random_uuid(),
    mp.id,
    CURRENT_DATE - (n || ' days')::interval,
    5000 + (random() * 200)::int,
    (1000 + (random() * 500))::numeric(10,2),
    100 + (random() * 50)::int,
    10 + (random() * 10)::int,
    20 + (random() * 15)::int,
    5,
    50 + (random() * 20)::int,
    5 + (random() * 10)::int,
    '{"engagement_rate": 0.65, "avg_message_price": 2.50}'::jsonb,
    NOW()
FROM model_profiles mp
CROSS JOIN generate_series(0, 6) AS n
WHERE mp.stage_name = 'Emma Rose'
ON CONFLICT DO NOTHING;

-- Step 7: Create theme configuration for agencies
INSERT INTO theme_configurations (
    id, agency_id, default_mode, allow_user_preference,
    light_theme, dark_theme, font_family, font_size_base,
    border_radius, created_at, updated_at
)
SELECT
    gen_random_uuid(),
    a.id,
    'light',
    true,
    '{"primary": "#1976d2", "secondary": "#dc004e", "background": "#ffffff", "surface": "#f5f5f5"}'::jsonb,
    '{"primary": "#90caf9", "secondary": "#f48fb1", "background": "#121212", "surface": "#1e1e1e"}'::jsonb,
    'Inter, system-ui, sans-serif',
    '16px',
    '8px',
    NOW(),
    NOW()
FROM agencies a
WHERE a.slug IN ('test-agency-premium', 'competitor-agency')
ON CONFLICT DO NOTHING;

-- Step 8: Create agency profiles
INSERT INTO agency_profiles (
    id, agency_id, display_name, tagline,
    description, support_email, support_phone,
    created_at, updated_at
)
SELECT
    gen_random_uuid(),
    a.id,
    a.name,
    'Your Success, Our Priority',
    'Leading OnlyFans management agency with proven results',
    'support@' || a.domain,
    '+1-555-123-4567',
    NOW(),
    NOW()
FROM agencies a
WHERE a.slug IN ('test-agency-premium', 'competitor-agency')
ON CONFLICT DO NOTHING;

-- Verification queries
SELECT 'Users by Role:' as info;
SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY role;

SELECT 'Agencies:' as info;
SELECT name, slug, subscription_status FROM agencies;

SELECT 'Model Profiles:' as info;
SELECT mp.stage_name, u.email, mp.subscription_price 
FROM model_profiles mp 
JOIN users u ON mp.user_id = u.id;

SELECT 'Commission Rules per Agency:' as info;
SELECT a.name as agency, COUNT(cr.id) as rule_count 
FROM agencies a 
LEFT JOIN commission_rules cr ON a.id = cr.agency_id 
GROUP BY a.name;

SELECT 'Billing Cycles:' as info;
SELECT a.name as agency, bc.start_date, bc.end_date, bc.is_closed
FROM billing_cycles bc
JOIN agencies a ON bc.agency_id = a.id
ORDER BY bc.start_date DESC;