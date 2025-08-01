"""Add fraud detection tables

Revision ID: 008
Revises: 007
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add fraud detection tables."""
    
    # Create enums manually with existence checks
    connection = op.get_bind()
    
    # Check and create risklevel enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'risklevel'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high', 'critical')"))
    
    # Check and create fraudtype enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'fraudtype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE fraudtype AS ENUM ('payment_fraud', 'account_takeover', 'fake_engagement', 'chargebacks', 'velocity_abuse', 'suspicious_behavior', 'bot_activity', 'content_theft')"))
    
    # Check and create actiontype enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'actiontype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE actiontype AS ENUM ('monitor', 'flag', 'restrict', 'suspend', 'block', 'review')"))
    
    # Create fraud_rules table
    op.create_table('fraud_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(length=50), nullable=False),
        sa.Column('fraud_type', postgresql.ENUM('payment_fraud', 'account_takeover', 'fake_engagement', 'chargebacks', 'velocity_abuse', 'suspicious_behavior', 'bot_activity', 'content_theft', name='fraudtype', create_type=False), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('time_window_seconds', sa.Integer(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('auto_action', postgresql.ENUM('monitor', 'flag', 'restrict', 'suspend', 'block', 'review', name='actiontype', create_type=False), nullable=True),
        sa.Column('notification_enabled', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create indexes for fraud_rules
    op.create_index('idx_fraud_rule_active', 'fraud_rules', ['is_active'], unique=False)
    op.create_index('idx_fraud_rule_type', 'fraud_rules', ['rule_type'], unique=False)
    op.create_index('idx_fraud_rule_fraud_type', 'fraud_rules', ['fraud_type'], unique=False)
    
    # Create fraud_scores table
    op.create_table('fraud_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('current_score', sa.Integer(), nullable=True),
        sa.Column('max_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', postgresql.ENUM('low', 'medium', 'high', 'critical', name='risklevel', create_type=False), nullable=True),
        sa.Column('velocity_score', sa.Integer(), nullable=True),
        sa.Column('pattern_score', sa.Integer(), nullable=True),
        sa.Column('anomaly_score', sa.Integer(), nullable=True),
        sa.Column('history_score', sa.Integer(), nullable=True),
        sa.Column('is_blocked', sa.Boolean(), nullable=True),
        sa.Column('is_under_review', sa.Boolean(), nullable=True),
        sa.Column('auto_action_taken', postgresql.ENUM('monitor', 'flag', 'restrict', 'suspend', 'block', 'review', name='actiontype', create_type=False), nullable=True),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True),
        sa.Column('score_updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for fraud_scores
    op.create_index('idx_fraud_score_entity', 'fraud_scores', ['entity_type', 'entity_id'], unique=True)
    op.create_index('idx_fraud_score_risk_level', 'fraud_scores', ['risk_level'], unique=False)
    op.create_index('idx_fraud_score_blocked', 'fraud_scores', ['is_blocked'], unique=False)
    op.create_index('idx_fraud_score_review', 'fraud_scores', ['is_under_review'], unique=False)
    
    # Create fraud_events table
    op.create_table('fraud_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('fraud_type', postgresql.ENUM('payment_fraud', 'account_takeover', 'fake_engagement', 'chargebacks', 'velocity_abuse', 'suspicious_behavior', 'bot_activity', 'content_theft', name='fraudtype', create_type=False), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('risk_level', postgresql.ENUM('low', 'medium', 'high', 'critical', name='risklevel', create_type=False), nullable=False),
        sa.Column('triggered_rules', sa.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('anomaly_factors', sa.JSON(), nullable=True),
        sa.Column('velocity_metrics', sa.JSON(), nullable=True),
        sa.Column('pattern_matches', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('device_fingerprint', sa.String(length=255), nullable=True),
        sa.Column('location_data', sa.JSON(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('action_taken', postgresql.ENUM('monitor', 'flag', 'restrict', 'suspend', 'block', 'review', name='actiontype', create_type=False), nullable=True),
        sa.Column('blocked', sa.Boolean(), nullable=True),
        sa.Column('reviewed', sa.Boolean(), nullable=True),
        sa.Column('false_positive', sa.Boolean(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for fraud_events
    op.create_index('idx_fraud_event_entity', 'fraud_events', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_fraud_event_user', 'fraud_events', ['user_id'], unique=False)
    op.create_index('idx_fraud_event_detected', 'fraud_events', ['detected_at'], unique=False)
    op.create_index('idx_fraud_event_risk_level', 'fraud_events', ['risk_level'], unique=False)
    op.create_index('idx_fraud_event_review', 'fraud_events', ['reviewed', 'false_positive'], unique=False)
    
    # Create fraud_patterns table
    op.create_table('fraud_patterns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('pattern_type', sa.String(length=50), nullable=False),
        sa.Column('fraud_type', postgresql.ENUM('payment_fraud', 'account_takeover', 'fake_engagement', 'chargebacks', 'velocity_abuse', 'suspicious_behavior', 'bot_activity', 'content_theft', name='fraudtype', create_type=False), nullable=False),
        sa.Column('pattern_data', sa.JSON(), nullable=False),
        sa.Column('confidence_threshold', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('auto_block', sa.Boolean(), nullable=True),
        sa.Column('match_count', sa.Integer(), nullable=True),
        sa.Column('false_positive_count', sa.Integer(), nullable=True),
        sa.Column('last_matched', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for fraud_patterns
    op.create_index('idx_fraud_pattern_active', 'fraud_patterns', ['is_active'], unique=False)
    op.create_index('idx_fraud_pattern_type', 'fraud_patterns', ['pattern_type', 'fraud_type'], unique=False)
    
    # Create velocity_checks table
    op.create_table('velocity_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('check_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('time_window_seconds', sa.Integer(), nullable=False),
        sa.Column('max_count', sa.Integer(), nullable=True),
        sa.Column('max_amount', sa.Float(), nullable=True),
        sa.Column('unique_constraint', sa.String(length=50), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('auto_action', postgresql.ENUM('monitor', 'flag', 'restrict', 'suspend', 'block', 'review', name='actiontype', create_type=False), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for velocity_checks
    op.create_index('idx_velocity_check_active', 'velocity_checks', ['is_active'], unique=False)
    op.create_index('idx_velocity_check_type', 'velocity_checks', ['check_type', 'entity_type'], unique=False)
    
    # Create review_queue table
    op.create_table('review_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('fraud_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', postgresql.ENUM('low', 'medium', 'high', 'critical', name='risklevel', create_type=False), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('assigned_to_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution', sa.String(length=50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['fraud_event_id'], ['fraud_events.id'], ),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for review_queue
    op.create_index('idx_review_queue_status', 'review_queue', ['status'], unique=False)
    op.create_index('idx_review_queue_priority', 'review_queue', ['priority', 'status'], unique=False)
    op.create_index('idx_review_queue_assigned', 'review_queue', ['assigned_to_id', 'status'], unique=False)
    op.create_index('idx_review_queue_entity', 'review_queue', ['entity_type', 'entity_id'], unique=False)
    
    # Create fraud_whitelist table
    op.create_table('fraud_whitelist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('whitelist_level', sa.String(length=20), nullable=True),
        sa.Column('skip_checks', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for fraud_whitelist
    op.create_index('idx_fraud_whitelist_entity', 'fraud_whitelist', ['entity_type', 'entity_id'], unique=True)
    op.create_index('idx_fraud_whitelist_validity', 'fraud_whitelist', ['valid_from', 'valid_until'], unique=False)
    
    # Set default values
    op.execute("UPDATE fraud_rules SET notification_enabled = true WHERE notification_enabled IS NULL")
    op.execute("UPDATE fraud_rules SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE fraud_rules SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE fraud_scores SET current_score = 0 WHERE current_score IS NULL")
    op.execute("UPDATE fraud_scores SET max_score = 0 WHERE max_score IS NULL")
    op.execute("UPDATE fraud_scores SET risk_level = 'low' WHERE risk_level IS NULL")
    op.execute("UPDATE fraud_scores SET velocity_score = 0 WHERE velocity_score IS NULL")
    op.execute("UPDATE fraud_scores SET pattern_score = 0 WHERE pattern_score IS NULL")
    op.execute("UPDATE fraud_scores SET anomaly_score = 0 WHERE anomaly_score IS NULL")
    op.execute("UPDATE fraud_scores SET history_score = 0 WHERE history_score IS NULL")
    op.execute("UPDATE fraud_scores SET is_blocked = false WHERE is_blocked IS NULL")
    op.execute("UPDATE fraud_scores SET is_under_review = false WHERE is_under_review IS NULL")
    op.execute("UPDATE fraud_patterns SET confidence_threshold = 0.8 WHERE confidence_threshold IS NULL")
    op.execute("UPDATE fraud_patterns SET auto_block = false WHERE auto_block IS NULL")
    op.execute("UPDATE fraud_patterns SET match_count = 0 WHERE match_count IS NULL")
    op.execute("UPDATE fraud_patterns SET false_positive_count = 0 WHERE false_positive_count IS NULL")
    op.execute("UPDATE fraud_patterns SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE velocity_checks SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE review_queue SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE review_queue SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE fraud_whitelist SET whitelist_level = 'full' WHERE whitelist_level IS NULL")
    op.execute("UPDATE fraud_events SET blocked = false WHERE blocked IS NULL")
    op.execute("UPDATE fraud_events SET reviewed = false WHERE reviewed IS NULL")
    
    # Insert default velocity checks
    op.execute("""
        INSERT INTO velocity_checks (id, name, check_type, entity_type, time_window_seconds, 
            max_count, risk_score, is_active)
        VALUES
        -- Transaction count checks
        (gen_random_uuid(), 'High transaction frequency (5min)', 'transaction_count', 'user', 300, 5, 30, true),
        (gen_random_uuid(), 'High transaction frequency (1hr)', 'transaction_count', 'user', 3600, 20, 20, true),
        (gen_random_uuid(), 'High transaction frequency (24hr)', 'transaction_count', 'user', 86400, 100, 15, true),
        
        -- Amount-based checks
        (gen_random_uuid(), 'High transaction amount (1hr)', 'amount_sum', 'user', 3600, NULL, 25, true),
        (gen_random_uuid(), 'High transaction amount (24hr)', 'amount_sum', 'user', 86400, NULL, 20, true),
        
        -- IP-based checks
        (gen_random_uuid(), 'Multiple users from same IP (1hr)', 'unique_users', 'ip', 3600, 5, 40, true),
        (gen_random_uuid(), 'High requests from IP (5min)', 'request_count', 'ip', 300, 50, 35, true)
    """)
    
    # Insert default fraud patterns
    op.execute("""
        INSERT INTO fraud_patterns (id, name, pattern_type, fraud_type, pattern_data, 
            risk_score, is_active)
        VALUES
        -- Card testing pattern
        (gen_random_uuid(), 'Card testing pattern', 'transactional', 'payment_fraud', 
            '{"amount": {"operator": "lt", "value": 5}, "frequency": {"operator": "gt", "value": 3}}', 
            50, true),
        
        -- Unusual time pattern
        (gen_random_uuid(), 'Late night high value', 'behavioral', 'suspicious_behavior',
            '{"hour": {"operator": "in", "value": [0, 1, 2, 3, 4]}, "amount": {"operator": "gt", "value": 1000}}',
            35, true),
        
        -- Rapid succession pattern
        (gen_random_uuid(), 'Rapid succession transactions', 'behavioral', 'velocity_abuse',
            '{"time_between": {"operator": "lt", "value": 60}, "count": {"operator": "gt", "value": 3}}',
            45, true)
    """)


def downgrade() -> None:
    """Remove fraud detection tables."""
    
    # Drop indexes
    op.drop_index('idx_fraud_whitelist_validity', table_name='fraud_whitelist')
    op.drop_index('idx_fraud_whitelist_entity', table_name='fraud_whitelist')
    op.drop_index('idx_review_queue_entity', table_name='review_queue')
    op.drop_index('idx_review_queue_assigned', table_name='review_queue')
    op.drop_index('idx_review_queue_priority', table_name='review_queue')
    op.drop_index('idx_review_queue_status', table_name='review_queue')
    op.drop_index('idx_velocity_check_type', table_name='velocity_checks')
    op.drop_index('idx_velocity_check_active', table_name='velocity_checks')
    op.drop_index('idx_fraud_pattern_type', table_name='fraud_patterns')
    op.drop_index('idx_fraud_pattern_active', table_name='fraud_patterns')
    op.drop_index('idx_fraud_event_review', table_name='fraud_events')
    op.drop_index('idx_fraud_event_risk_level', table_name='fraud_events')
    op.drop_index('idx_fraud_event_detected', table_name='fraud_events')
    op.drop_index('idx_fraud_event_user', table_name='fraud_events')
    op.drop_index('idx_fraud_event_entity', table_name='fraud_events')
    op.drop_index('idx_fraud_score_review', table_name='fraud_scores')
    op.drop_index('idx_fraud_score_blocked', table_name='fraud_scores')
    op.drop_index('idx_fraud_score_risk_level', table_name='fraud_scores')
    op.drop_index('idx_fraud_score_entity', table_name='fraud_scores')
    op.drop_index('idx_fraud_rule_fraud_type', table_name='fraud_rules')
    op.drop_index('idx_fraud_rule_type', table_name='fraud_rules')
    op.drop_index('idx_fraud_rule_active', table_name='fraud_rules')
    
    # Drop tables
    op.drop_table('fraud_whitelist')
    op.drop_table('review_queue')
    op.drop_table('velocity_checks')
    op.drop_table('fraud_patterns')
    op.drop_table('fraud_events')
    op.drop_table('fraud_scores')
    op.drop_table('fraud_rules')
    
    # Drop enums
    actiontype_enum = ENUM('monitor', 'flag', 'restrict', 'suspend', 'block', 'review', name='actiontype')
    fraudtype_enum = ENUM('payment_fraud', 'account_takeover', 'fake_engagement', 'chargebacks', 'velocity_abuse', 'suspicious_behavior', 'bot_activity', 'content_theft', name='fraudtype')
    risklevel_enum = ENUM('low', 'medium', 'high', 'critical', name='risklevel')
    
    actiontype_enum.drop(op.get_bind(), checkfirst=True)
    fraudtype_enum.drop(op.get_bind(), checkfirst=True)
    risklevel_enum.drop(op.get_bind(), checkfirst=True)