"""Add A/B testing framework tables

Revision ID: 008_ab_testing_framework
Revises: 007_performance_indexes
Create Date: 2025-01-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008_ab_testing_framework'
down_revision = '007_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create experiments table
    op.create_table(
        'ab_experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('experiment_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('target_audience', sa.JSON(), nullable=True),
        sa.Column('model_ids', sa.JSON(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('allocation_method', sa.String(), nullable=True),
        sa.Column('allocation_config', sa.JSON(), nullable=True),
        sa.Column('primary_metric', sa.String(), nullable=False),
        sa.Column('secondary_metrics', sa.JSON(), nullable=True),
        sa.Column('minimum_sample_size', sa.Integer(), nullable=True),
        sa.Column('statistical_test', sa.String(), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.Column('minimum_detectable_effect', sa.Float(), nullable=True),
        sa.Column('winner_variant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('results_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create experiment variants table
    op.create_table(
        'ab_experiment_variants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_control', sa.Boolean(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('allocation_percentage', sa.Float(), nullable=True),
        sa.Column('participant_count', sa.Integer(), nullable=True),
        sa.Column('conversion_count', sa.Integer(), nullable=True),
        sa.Column('conversion_rate', sa.Float(), nullable=True),
        sa.Column('average_value', sa.Float(), nullable=True),
        sa.Column('statistical_significance', sa.Float(), nullable=True),
        sa.Column('confidence_interval_lower', sa.Float(), nullable=True),
        sa.Column('confidence_interval_upper', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create experiment participants table
    op.create_table(
        'ab_experiment_participants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('participant_type', sa.String(), nullable=False),
        sa.Column('participant_id', sa.String(), nullable=False),
        sa.Column('assignment_timestamp', sa.DateTime(), nullable=True),
        sa.Column('assignment_reason', sa.String(), nullable=True),
        sa.Column('has_converted', sa.Boolean(), nullable=True),
        sa.Column('conversion_timestamp', sa.DateTime(), nullable=True),
        sa.Column('conversion_value', sa.Float(), nullable=True),
        sa.Column('interaction_count', sa.Integer(), nullable=True),
        sa.Column('last_interaction', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ),
        sa.ForeignKeyConstraint(['variant_id'], ['ab_experiment_variants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create experiment events table
    op.create_table(
        'ab_experiment_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_value', sa.Float(), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ),
        sa.ForeignKeyConstraint(['participant_id'], ['ab_experiment_participants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create experiment templates table
    op.create_table(
        'ab_experiment_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('experiment_type', sa.String(), nullable=False),
        sa.Column('default_config', sa.JSON(), nullable=False),
        sa.Column('variant_templates', sa.JSON(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create experiment results table
    op.create_table(
        'ab_experiment_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('total_participants', sa.Integer(), nullable=True),
        sa.Column('total_conversions', sa.Integer(), nullable=True),
        sa.Column('overall_conversion_rate', sa.Float(), nullable=True),
        sa.Column('p_value', sa.Float(), nullable=True),
        sa.Column('effect_size', sa.Float(), nullable=True),
        sa.Column('power', sa.Float(), nullable=True),
        sa.Column('variant_results', sa.JSON(), nullable=True),
        sa.Column('pairwise_comparisons', sa.JSON(), nullable=True),
        sa.Column('segment_results', sa.JSON(), nullable=True),
        sa.Column('daily_results', sa.JSON(), nullable=True),
        sa.Column('cumulative_results', sa.JSON(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('confidence_in_results', sa.Float(), nullable=True),
        sa.Column('analysis_timestamp', sa.DateTime(), nullable=True),
        sa.Column('analysis_version', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id')
    )
    
    # Create indexes for performance
    op.create_index('idx_experiments_agency_status', 'ab_experiments', ['agency_id', 'status'])
    op.create_index('idx_experiments_type_status', 'ab_experiments', ['experiment_type', 'status'])
    op.create_index('idx_experiments_start_date', 'ab_experiments', ['start_date'])
    
    op.create_index('idx_variants_experiment', 'ab_experiment_variants', ['experiment_id'])
    op.create_index('idx_variants_active', 'ab_experiment_variants', ['is_active'])
    
    op.create_index('idx_participants_experiment', 'ab_experiment_participants', ['experiment_id'])
    op.create_index('idx_participants_variant', 'ab_experiment_participants', ['variant_id'])
    op.create_index('idx_participants_type_id', 'ab_experiment_participants', ['participant_type', 'participant_id'])
    op.create_index('idx_participants_assignment', 'ab_experiment_participants', ['assignment_timestamp'])
    op.create_index('idx_participants_conversion', 'ab_experiment_participants', ['has_converted', 'conversion_timestamp'])
    
    op.create_index('idx_events_experiment', 'ab_experiment_events', ['experiment_id'])
    op.create_index('idx_events_participant', 'ab_experiment_events', ['participant_id'])
    op.create_index('idx_events_type_timestamp', 'ab_experiment_events', ['event_type', 'timestamp'])
    
    op.create_index('idx_templates_agency', 'ab_experiment_templates', ['agency_id'])
    op.create_index('idx_templates_type', 'ab_experiment_templates', ['experiment_type'])
    op.create_index('idx_templates_public', 'ab_experiment_templates', ['is_public'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_templates_public', table_name='ab_experiment_templates')
    op.drop_index('idx_templates_type', table_name='ab_experiment_templates')
    op.drop_index('idx_templates_agency', table_name='ab_experiment_templates')
    
    op.drop_index('idx_events_type_timestamp', table_name='ab_experiment_events')
    op.drop_index('idx_events_participant', table_name='ab_experiment_events')
    op.drop_index('idx_events_experiment', table_name='ab_experiment_events')
    
    op.drop_index('idx_participants_conversion', table_name='ab_experiment_participants')
    op.drop_index('idx_participants_assignment', table_name='ab_experiment_participants')
    op.drop_index('idx_participants_type_id', table_name='ab_experiment_participants')
    op.drop_index('idx_participants_variant', table_name='ab_experiment_participants')
    op.drop_index('idx_participants_experiment', table_name='ab_experiment_participants')
    
    op.drop_index('idx_variants_active', table_name='ab_experiment_variants')
    op.drop_index('idx_variants_experiment', table_name='ab_experiment_variants')
    
    op.drop_index('idx_experiments_start_date', table_name='ab_experiments')
    op.drop_index('idx_experiments_type_status', table_name='ab_experiments')
    op.drop_index('idx_experiments_agency_status', table_name='ab_experiments')
    
    # Drop tables
    op.drop_table('ab_experiment_results')
    op.drop_table('ab_experiment_templates')
    op.drop_table('ab_experiment_events')
    op.drop_table('ab_experiment_participants')
    op.drop_table('ab_experiment_variants')
    op.drop_table('ab_experiments')