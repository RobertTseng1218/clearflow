"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('auth_provider', sa.String(length=50), nullable=False),
        sa.Column('auth_provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('auth_provider', 'auth_provider_user_id', name='uq_auth_provider_user'),
        sa.UniqueConstraint('email')
    )
    op.create_table(
        'plans',
        sa.Column('plan_key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('plan_type', sa.String(length=30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_key')
    )
    op.create_table(
        'activity_logs',
        sa.Column('owner_type', sa.String(length=20), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_source', sa.String(length=50), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('related_entity_type', sa.String(length=50), nullable=True),
        sa.Column('related_entity_id', sa.String(length=36), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'plan_features',
        sa.Column('plan_id', sa.String(length=36), nullable=False),
        sa.Column('feature_key', sa.String(length=100), nullable=False),
        sa.Column('feature_value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id', 'feature_key', name='uq_plan_feature')
    )
    op.create_table(
        'subscriptions',
        sa.Column('owner_type', sa.String(length=20), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('plan_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('renewal_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'usage_counters',
        sa.Column('owner_type', sa.String(length=20), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('metric_key', sa.String(length=100), nullable=False),
        sa.Column('period_key', sa.String(length=30), nullable=False),
        sa.Column('usage_value', sa.Integer(), nullable=False),
        sa.Column('reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_type', 'owner_id', 'metric_key', 'period_key', name='uq_usage_metric_period')
    )
    op.create_table(
        'user_profiles',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('locale', sa.String(length=20), nullable=False),
        sa.Column('work_template_key', sa.String(length=50), nullable=True),
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False),
        sa.Column('notification_preference_json', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_table(
        'integrations',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('provider_key', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_cursor', sa.Text(), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'provider_key', name='uq_user_provider')
    )
    op.create_table(
        'integration_tokens',
        sa.Column('integration_id', sa.String(length=36), nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=False),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id')
    )
    op.create_table(
        'source_items',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('integration_id', sa.String(length=36), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('participants_json', sa.JSON(), nullable=False),
        sa.Column('source_meta_json', sa.JSON(), nullable=False),
        sa.Column('hash_signature', sa.String(length=255), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['integration_id'], ['integrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('integration_id', 'external_id', name='uq_integration_external_id')
    )
    op.create_table(
        'summaries',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('team_id', sa.String(length=36), nullable=True),
        sa.Column('summary_type', sa.String(length=50), nullable=False),
        sa.Column('summary_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'tasks',
        sa.Column('owner_type', sa.String(length=20), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('created_by_type', sa.String(length=20), nullable=False),
        sa.Column('task_hash', sa.String(length=255), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'summary_items',
        sa.Column('summary_id', sa.String(length=36), nullable=False),
        sa.Column('item_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority_score', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('related_source_item_id', sa.String(length=36), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['related_source_item_id'], ['source_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['summary_id'], ['summaries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'task_sources',
        sa.Column('task_id', sa.String(length=36), nullable=False),
        sa.Column('source_item_id', sa.String(length=36), nullable=False),
        sa.Column('relation_type', sa.String(length=30), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_item_id'], ['source_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'source_item_id', name='uq_task_source_pair')
    )


def downgrade() -> None:
    for table in ['task_sources','summary_items','tasks','summaries','source_items','integration_tokens','integrations','user_profiles','usage_counters','subscriptions','plan_features','activity_logs','plans','users']:
        op.drop_table(table)
