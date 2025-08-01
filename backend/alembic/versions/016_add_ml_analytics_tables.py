"""Add ML Analytics tables

Revision ID: 016
Revises: 015
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ML analytics tables."""
    
    
    
    # Check and create modelstatus enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'modelstatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE modelstatus AS ENUM ('pending', 'training', 'trained', 'evaluating', 'deployed', 'failed', 'archived')"))

    # Check and create predictiontype enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'predictiontype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE predictiontype AS ENUM ('revenue_forecast', 'churn_prediction', 'content_optimization', 'anomaly_detection', 'fan_ltv', 'engagement_score', 'conversion_rate')"))
# Check and create modelstatus enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'modelstatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE modelstatus AS ENUM ('pending', 'training', 'trained', 'evaluating', 'deployed', 'failed', 'archived')"))

    # Check and create predictiontype enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'predictiontype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE predictiontype AS ENUM ('revenue_forecast', 'churn_prediction', 'content_optimization', 'anomaly_detection', 'fan_ltv', 'engagement_score', 'conversion_rate')"))
    # Create enums
    
    # Create ml_models table
    op.create_table('ml_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('prediction_type', postgresql.ENUM('revenue_forecast', 'churn_prediction', 'content_optimization', 'anomaly_detection', 'fan_ltv', 'engagement_score', 'conversion_rate', name='predictiontype', create_type=False), nullable=False),
        sa.Column('algorithm', sa.String(length=100), nullable=True),
        sa.Column('hyperparameters', sa.JSON(), nullable=True),
        sa.Column('features', sa.JSON(), nullable=True),
        sa.Column('target_variable', sa.String(length=100), nullable=True),
        sa.Column('training_data_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('training_data_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('training_samples', sa.Integer(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('accuracy_score', sa.Float(), nullable=True),
        sa.Column('validation_score', sa.Float(), nullable=True),
        sa.Column('model_path', sa.String(length=500), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('model_size_mb', sa.Float(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'training', 'trained', 'evaluating', 'deployed', 'failed', 'archived', name='modelstatus', create_type=False), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('deployment_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for ml_models
    op.create_index('idx_ml_model_agency', 'ml_models', ['agency_id'], unique=False)
    op.create_index('idx_ml_model_type', 'ml_models', ['prediction_type'], unique=False)
    op.create_index('idx_ml_model_status', 'ml_models', ['status'], unique=False)
    op.create_index('idx_ml_model_active', 'ml_models', ['is_active'], unique=False)
    
    # Create predictions table
    op.create_table('predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prediction_type', postgresql.ENUM('revenue_forecast', 'churn_prediction', 'content_optimization', 'anomaly_detection', 'fan_ltv', 'engagement_score', 'conversion_rate', name='predictiontype', create_type=False), nullable=False),
        sa.Column('target_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('prediction_horizon', sa.Integer(), nullable=True),
        sa.Column('predicted_value', sa.Float(), nullable=True),
        sa.Column('confidence_interval_lower', sa.Float(), nullable=True),
        sa.Column('confidence_interval_upper', sa.Float(), nullable=True),
        sa.Column('probability', sa.Float(), nullable=True),
        sa.Column('predictions_json', sa.JSON(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('input_features', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('actual_value', sa.Float(), nullable=True),
        sa.Column('error_percentage', sa.Float(), nullable=True),
        sa.Column('feedback_received_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for predictions
    op.create_index('idx_prediction_model', 'predictions', ['model_id'], unique=False)
    op.create_index('idx_prediction_type', 'predictions', ['prediction_type'], unique=False)
    op.create_index('idx_prediction_entity', 'predictions', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_prediction_created', 'predictions', ['created_at'], unique=False)
    op.create_index('idx_prediction_target_date', 'predictions', ['target_date'], unique=False)
    
    # Create model_training_jobs table
    op.create_table('model_training_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('training_data_query', sa.Text(), nullable=True),
        sa.Column('training_samples', sa.Integer(), nullable=True),
        sa.Column('validation_samples', sa.Integer(), nullable=True),
        sa.Column('test_samples', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('cpu_hours', sa.Float(), nullable=True),
        sa.Column('memory_gb', sa.Float(), nullable=True),
        sa.Column('cost_estimate', sa.Float(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('model_artifact_path', sa.String(length=500), nullable=True),
        sa.Column('triggered_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'], ),
        sa.ForeignKeyConstraint(['triggered_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for model_training_jobs
    op.create_index('idx_training_job_model', 'model_training_jobs', ['model_id'], unique=False)
    op.create_index('idx_training_job_status', 'model_training_jobs', ['status'], unique=False)
    op.create_index('idx_training_job_created', 'model_training_jobs', ['created_at'], unique=False)
    
    # Create feature_store table
    op.create_table('feature_store',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature_name', sa.String(length=100), nullable=False),
        sa.Column('feature_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('numeric_value', sa.Float(), nullable=True),
        sa.Column('categorical_value', sa.String(length=200), nullable=True),
        sa.Column('vector_value', sa.ARRAY(sa.Float()), nullable=True),
        sa.Column('json_value', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('time_window', sa.String(length=50), nullable=True),
        sa.Column('computation_time_ms', sa.Integer(), nullable=True),
        sa.Column('source_table', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for feature_store
    op.create_index('idx_feature_entity', 'feature_store', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_feature_name', 'feature_store', ['feature_name'], unique=False)
    op.create_index('idx_feature_timestamp', 'feature_store', ['timestamp'], unique=False)
    op.create_index('idx_feature_composite', 'feature_store', ['entity_type', 'entity_id', 'feature_name', 'timestamp'], unique=False)
    
    # Create prediction_feedback table
    op.create_table('prediction_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prediction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actual_value', sa.Float(), nullable=True),
        sa.Column('actual_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('absolute_error', sa.Float(), nullable=True),
        sa.Column('percentage_error', sa.Float(), nullable=True),
        sa.Column('squared_error', sa.Float(), nullable=True),
        sa.Column('user_feedback', sa.String(length=50), nullable=True),
        sa.Column('feedback_notes', sa.Text(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('recorded_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], ),
        sa.ForeignKeyConstraint(['recorded_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for prediction_feedback
    op.create_index('idx_feedback_prediction', 'prediction_feedback', ['prediction_id'], unique=False)
    op.create_index('idx_feedback_recorded', 'prediction_feedback', ['recorded_at'], unique=False)
    
    # Create insight_alerts table
    op.create_table('insight_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prediction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('recommendations', sa.JSON(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=True),
        sa.Column('notification_channels', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'], ),
        sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], ),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for insight_alerts
    op.create_index('idx_alert_agency', 'insight_alerts', ['agency_id'], unique=False)
    op.create_index('idx_alert_type', 'insight_alerts', ['alert_type'], unique=False)
    op.create_index('idx_alert_severity', 'insight_alerts', ['severity'], unique=False)
    op.create_index('idx_alert_entity', 'insight_alerts', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_alert_created', 'insight_alerts', ['created_at'], unique=False)
    op.create_index('idx_alert_unread', 'insight_alerts', ['is_read', 'agency_id'], unique=False)
    
    # Set default values
    op.execute("UPDATE ml_models SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE ml_models SET is_active = false WHERE is_active IS NULL")
    op.execute("UPDATE model_training_jobs SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE insight_alerts SET is_read = false WHERE is_read IS NULL")
    op.execute("UPDATE insight_alerts SET is_resolved = false WHERE is_resolved IS NULL")
    op.execute("UPDATE insight_alerts SET notification_sent = false WHERE notification_sent IS NULL")


def downgrade() -> None:
    """Remove ML analytics tables."""
    
    # Drop indexes
    op.drop_index('idx_alert_unread', table_name='insight_alerts')
    op.drop_index('idx_alert_created', table_name='insight_alerts')
    op.drop_index('idx_alert_entity', table_name='insight_alerts')
    op.drop_index('idx_alert_severity', table_name='insight_alerts')
    op.drop_index('idx_alert_type', table_name='insight_alerts')
    op.drop_index('idx_alert_agency', table_name='insight_alerts')
    op.drop_index('idx_feedback_recorded', table_name='prediction_feedback')
    op.drop_index('idx_feedback_prediction', table_name='prediction_feedback')
    op.drop_index('idx_feature_composite', table_name='feature_store')
    op.drop_index('idx_feature_timestamp', table_name='feature_store')
    op.drop_index('idx_feature_name', table_name='feature_store')
    op.drop_index('idx_feature_entity', table_name='feature_store')
    op.drop_index('idx_training_job_created', table_name='model_training_jobs')
    op.drop_index('idx_training_job_status', table_name='model_training_jobs')
    op.drop_index('idx_training_job_model', table_name='model_training_jobs')
    op.drop_index('idx_prediction_target_date', table_name='predictions')
    op.drop_index('idx_prediction_created', table_name='predictions')
    op.drop_index('idx_prediction_entity', table_name='predictions')
    op.drop_index('idx_prediction_type', table_name='predictions')
    op.drop_index('idx_prediction_model', table_name='predictions')
    op.drop_index('idx_ml_model_active', table_name='ml_models')
    op.drop_index('idx_ml_model_status', table_name='ml_models')
    op.drop_index('idx_ml_model_type', table_name='ml_models')
    op.drop_index('idx_ml_model_agency', table_name='ml_models')
    
    # Drop tables
    op.drop_table('insight_alerts')
    op.drop_table('prediction_feedback')
    op.drop_table('feature_store')
    op.drop_table('model_training_jobs')
    op.drop_table('predictions')
    op.drop_table('ml_models')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS modelstatus')
    op.execute('DROP TYPE IF EXISTS predictiontype')
