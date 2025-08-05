-- Agency Dark Test Data Seed
-- This file creates comprehensive test data for all user roles
-- All passwords are 'admin123', 'owner123', 'model123', 'chatter123', or 'member123'

-- Start transaction
BEGIN;

-- Create password hash for all test passwords
-- Note: These are bcrypt hashes for the passwords mentioned above
-- admin123 / owner123 / model123 / chatter123 / member123 all use simplified hashes for testing

-- Insert Agencies
INSERT INTO agencies (id, name, owner_id, is_active, created_at, updated_at) VALUES
('11111111-1111-1111-1111-111111111111', 'Elite Models Agency', NULL, true, NOW() - INTERVAL '1 year', NOW()),
('22222222-2222-2222-2222-222222222222', 'Premium Talent Management', NULL, true, NOW() - INTERVAL '8 months', NOW()),
('33333333-3333-3333-3333-333333333333', 'Rising Stars Agency', NULL, true, NOW() - INTERVAL '3 months', NOW());

-- Insert Users
-- Password for all: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu (this is 'admin123' hashed)

-- Super Admin
INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at, agency_id) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'admin@agency.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Super Admin', 'SUPER_ADMIN', true, true, NOW() - INTERVAL '2 years', NOW(), NULL);

-- Elite Models Agency Users
INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at, agency_id) VALUES
-- Agency Owner
('b1111111-1111-1111-1111-111111111111', 'owner@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'James Thompson', 'AGENCY_OWNER', true, true, NOW() - INTERVAL '1 year', NOW(), '11111111-1111-1111-1111-111111111111'),
-- Agency Admin
('b2222222-2222-2222-2222-222222222222', 'admin@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Mary Johnson', 'AGENCY_ADMIN', true, true, NOW() - INTERVAL '10 months', NOW(), '11111111-1111-1111-1111-111111111111'),
-- Models
('b3333333-3333-3333-3333-333333333333', 'sarah@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Sarah Johnson', 'MODEL', true, true, NOW() - INTERVAL '8 months', NOW() - INTERVAL '1 day', '11111111-1111-1111-1111-111111111111'),
('b4444444-4444-4444-4444-444444444444', 'emma@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Emma Davis', 'MODEL', true, true, NOW() - INTERVAL '6 months', NOW() - INTERVAL '2 days', '11111111-1111-1111-1111-111111111111'),
('b5555555-5555-5555-5555-555555555555', 'lisa@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Lisa Brown', 'MODEL', true, true, NOW() - INTERVAL '1 month', NOW() - INTERVAL '3 days', '11111111-1111-1111-1111-111111111111'),
-- Chatters
('b6666666-6666-6666-6666-666666666666', 'john@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'John Smith', 'CHATTER', true, true, NOW() - INTERVAL '7 months', NOW() - INTERVAL '1 hour', '11111111-1111-1111-1111-111111111111'),
('b7777777-7777-7777-7777-777777777777', 'mike@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Mike Wilson', 'CHATTER', true, true, NOW() - INTERVAL '3 months', NOW() - INTERVAL '2 hours', '11111111-1111-1111-1111-111111111111'),
-- Agency Member
('b8888888-8888-8888-8888-888888888888', 'support@elitemodels.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Support Staff', 'AGENCY_MEMBER', true, true, NOW() - INTERVAL '5 months', NOW() - INTERVAL '1 week', '11111111-1111-1111-1111-111111111111');

-- Premium Talent Management Users
INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at, agency_id) VALUES
-- Agency Owner
('c1111111-1111-1111-1111-111111111111', 'owner@premiumtalent.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Robert Martinez', 'AGENCY_OWNER', true, true, NOW() - INTERVAL '8 months', NOW(), '22222222-2222-2222-2222-222222222222'),
-- Models
('c2222222-2222-2222-2222-222222222222', 'jessica@premiumtalent.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Jessica White', 'MODEL', true, true, NOW() - INTERVAL '5 months', NOW() - INTERVAL '1 day', '22222222-2222-2222-2222-222222222222'),
('c3333333-3333-3333-3333-333333333333', 'ashley@premiumtalent.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Ashley Green', 'MODEL', true, true, NOW() - INTERVAL '4 months', NOW() - INTERVAL '2 days', '22222222-2222-2222-2222-222222222222'),
-- Chatter
('c4444444-4444-4444-4444-444444444444', 'alex@premiumtalent.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Alex Turner', 'CHATTER', true, true, NOW() - INTERVAL '6 months', NOW() - INTERVAL '3 hours', '22222222-2222-2222-2222-222222222222');

-- Rising Stars Agency Users
INSERT INTO users (id, email, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at, agency_id) VALUES
-- Agency Owner
('d1111111-1111-1111-1111-111111111111', 'owner@risingstars.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Linda Chen', 'AGENCY_OWNER', true, true, NOW() - INTERVAL '3 months', NOW(), '33333333-3333-3333-3333-333333333333'),
-- Model
('d2222222-2222-2222-2222-222222222222', 'sophia@risingstars.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYpfQP3YE/0HnBu', 'Sophia Rodriguez', 'MODEL', true, true, NOW() - INTERVAL '2 months', NOW() - INTERVAL '4 hours', '33333333-3333-3333-3333-333333333333');

-- Update agencies with owner_ids
UPDATE agencies SET owner_id = 'b1111111-1111-1111-1111-111111111111' WHERE id = '11111111-1111-1111-1111-111111111111';
UPDATE agencies SET owner_id = 'c1111111-1111-1111-1111-111111111111' WHERE id = '22222222-2222-2222-2222-222222222222';
UPDATE agencies SET owner_id = 'd1111111-1111-1111-1111-111111111111' WHERE id = '33333333-3333-3333-3333-333333333333';

-- Insert Model Profiles for all models
INSERT INTO model_profiles (id, user_id, stage_name, bio, profile_image_url, created_at, updated_at, is_active) VALUES
('mp111111-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', 'SarahJ', 'Top performing model with 2 years experience. Fitness enthusiast and lifestyle blogger.', 'https://placeholder.com/sarah.jpg', NOW() - INTERVAL '8 months', NOW(), true),
('mp222222-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', 'EmmaD', 'Fashion model and content creator. Love connecting with fans!', 'https://placeholder.com/emma.jpg', NOW() - INTERVAL '6 months', NOW(), true),
('mp333333-3333-3333-3333-333333333333', 'b5555555-5555-5555-5555-555555555555', 'LisaB', 'New to the platform but excited to share my journey!', 'https://placeholder.com/lisa.jpg', NOW() - INTERVAL '1 month', NOW(), true),
('mp444444-4444-4444-4444-444444444444', 'c2222222-2222-2222-2222-222222222222', 'JessicaW', 'Professional model with international experience. Luxury lifestyle content.', 'https://placeholder.com/jessica.jpg', NOW() - INTERVAL '5 months', NOW(), true),
('mp555555-5555-5555-5555-555555555555', 'c3333333-3333-3333-3333-333333333333', 'AshleyG', 'Yoga instructor and wellness advocate. Daily motivation and fitness tips.', 'https://placeholder.com/ashley.jpg', NOW() - INTERVAL '4 months', NOW(), true),
('mp666666-6666-6666-6666-666666666666', 'd2222222-2222-2222-2222-222222222222', 'SophiaR', 'Rising star in fashion modeling. Authentic and engaging content daily!', 'https://placeholder.com/sophia.jpg', NOW() - INTERVAL '2 months', NOW(), true);

-- Insert Model-Chatter Assignments
INSERT INTO model_chatters (id, model_id, chatter_id, assigned_at, is_active) VALUES
-- John handles Sarah and Emma
('mc111111-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', 'b6666666-6666-6666-6666-666666666666', NOW() - INTERVAL '7 months', true),
('mc222222-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', 'b6666666-6666-6666-6666-666666666666', NOW() - INTERVAL '6 months', true),
-- Mike handles Lisa
('mc333333-3333-3333-3333-333333333333', 'b5555555-5555-5555-5555-555555555555', 'b7777777-7777-7777-7777-777777777777', NOW() - INTERVAL '1 month', true),
-- Alex handles Jessica and Ashley
('mc444444-4444-4444-4444-444444444444', 'c2222222-2222-2222-2222-222222222222', 'c4444444-4444-4444-4444-444444444444', NOW() - INTERVAL '5 months', true),
('mc555555-5555-5555-5555-555555555555', 'c3333333-3333-3333-3333-333333333333', 'c4444444-4444-4444-4444-444444444444', NOW() - INTERVAL '4 months', true);

-- Insert Commission Rules
INSERT INTO commission_rules (id, agency_id, role, percentage, created_at, updated_at, is_active) VALUES
('cr111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'MODEL', 20.0, NOW() - INTERVAL '1 year', NOW(), true),
('cr222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'MODEL', 25.0, NOW() - INTERVAL '8 months', NOW(), true),
('cr333333-3333-3333-3333-333333333333', '33333333-3333-3333-3333-333333333333', 'MODEL', 15.0, NOW() - INTERVAL '3 months', NOW(), true);

-- Insert sample Financial Transactions for models (last 6 months)
INSERT INTO financial_transactions (id, user_id, agency_id, amount, type, status, description, created_at) VALUES
-- Sarah's transactions (top performer)
('ft111111-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 5000.00, 'EARNING', 'COMPLETED', 'Monthly earnings', NOW() - INTERVAL '1 month', NOW() - INTERVAL '1 month'),
('ft111112-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 4800.00, 'EARNING', 'COMPLETED', 'Monthly earnings', NOW() - INTERVAL '2 months', NOW() - INTERVAL '2 months'),
('ft111113-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 5200.00, 'EARNING', 'COMPLETED', 'Monthly earnings', NOW() - INTERVAL '3 months', NOW() - INTERVAL '3 months'),
-- Emma's transactions
('ft222221-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', 3000.00, 'EARNING', 'COMPLETED', 'Monthly earnings', NOW() - INTERVAL '1 month', NOW() - INTERVAL '1 month'),
('ft222222-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', 2800.00, 'EARNING', 'COMPLETED', 'Monthly earnings', NOW() - INTERVAL '2 months', NOW() - INTERVAL '2 months'),
-- Lisa's transactions (new model)
('ft333331-3333-3333-3333-333333333333', 'b5555555-5555-5555-5555-555555555555', '11111111-1111-1111-1111-111111111111', 800.00, 'EARNING', 'COMPLETED', 'First month earnings', NOW() - INTERVAL '2 weeks', NOW() - INTERVAL '2 weeks');

-- Insert sample Payouts
INSERT INTO payouts (id, user_id, agency_id, amount, status, scheduled_date, processed_date, created_at) VALUES
-- Recent payouts
('po111111-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 4000.00, 'COMPLETED', NOW() - INTERVAL '1 week', NOW() - INTERVAL '1 week', NOW() - INTERVAL '1 week'),
('po222222-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', '11111111-1111-1111-1111-111111111111', 2400.00, 'COMPLETED', NOW() - INTERVAL '1 week', NOW() - INTERVAL '1 week', NOW() - INTERVAL '1 week'),
-- Pending payouts
('po333333-3333-3333-3333-333333333333', 'b3333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 4200.00, 'PENDING', NOW() + INTERVAL '3 days', NULL, NOW()),
('po444444-4444-4444-4444-444444444444', 'c2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 3500.00, 'PENDING', NOW() + INTERVAL '3 days', NULL, NOW());

-- Insert Content Performance data for models
INSERT INTO content_performance (id, model_id, content_type, content_id, views, likes, comments, revenue, created_at) VALUES
-- Sarah's content (high engagement)
('cp111111-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', 'PHOTO', 'content-001', 15000, 3200, 450, 250.00, NOW() - INTERVAL '1 week'),
('cp111112-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', 'VIDEO', 'content-002', 25000, 5400, 780, 500.00, NOW() - INTERVAL '2 weeks'),
-- Emma's content
('cp222221-2222-2222-2222-222222222222', 'b4444444-4444-4444-4444-444444444444', 'PHOTO', 'content-003', 8000, 1600, 220, 150.00, NOW() - INTERVAL '1 week'),
-- Lisa's content (new, growing)
('cp333331-3333-3333-3333-333333333333', 'b5555555-5555-5555-5555-555555555555', 'PHOTO', 'content-004', 2000, 400, 65, 50.00, NOW() - INTERVAL '3 days');

-- Insert Metric Snapshots for analytics
INSERT INTO metric_snapshots (id, agency_id, metric_type, metric_value, snapshot_date, created_at) VALUES
-- Elite Models metrics
('ms111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'TOTAL_REVENUE', 15000.00, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'),
('ms111112-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'ACTIVE_MODELS', 3, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'),
('ms111113-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'TOTAL_SUBSCRIBERS', 850, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'),
-- Premium Talent metrics
('ms222221-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'TOTAL_REVENUE', 8000.00, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'),
('ms222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'ACTIVE_MODELS', 2, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day');

-- Insert sample Chat Messages
INSERT INTO chat_messages (id, sender_id, recipient_id, message, is_read, created_at) VALUES
-- Recent chat activity
('cm111111-1111-1111-1111-111111111111', 'b6666666-6666-6666-6666-666666666666', 'b3333333-3333-3333-3333-333333333333', 'Hi Sarah, you have new fan messages to review!', true, NOW() - INTERVAL '2 hours'),
('cm111112-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', 'b6666666-6666-6666-6666-666666666666', 'Thanks John, I will check them now.', true, NOW() - INTERVAL '1 hour'),
('cm222221-2222-2222-2222-222222222222', 'b7777777-7777-7777-7777-777777777777', 'b5555555-5555-5555-5555-555555555555', 'Lisa, great job on your first week! Keep it up!', false, NOW() - INTERVAL '30 minutes');

-- Insert sample Notifications
INSERT INTO notifications (id, user_id, type, title, message, is_read, created_at) VALUES
-- Unread notifications
('nt111111-1111-1111-1111-111111111111', 'b3333333-3333-3333-3333-333333333333', 'PAYOUT', 'Payout Scheduled', 'Your payout of $4,200 is scheduled for processing.', false, NOW() - INTERVAL '1 hour'),
('nt222222-2222-2222-2222-222222222222', 'b1111111-1111-1111-1111-111111111111', 'SYSTEM', 'Monthly Report Ready', 'Your agency monthly report is ready for review.', false, NOW() - INTERVAL '2 hours'),
('nt333333-3333-3333-3333-333333333333', 'b5555555-5555-5555-5555-555555555555', 'ACHIEVEMENT', 'Welcome Bonus!', 'Congratulations on your first week! You earned a $100 bonus.', false, NOW() - INTERVAL '1 day');

-- Commit transaction
COMMIT;

-- Display summary
SELECT 'Test data loaded successfully!' as status;
SELECT 'Total users created: ' || COUNT(*) as count FROM users;
SELECT 'Total agencies created: ' || COUNT(*) as count FROM agencies;
SELECT 'Total models created: ' || COUNT(*) as count FROM model_profiles;