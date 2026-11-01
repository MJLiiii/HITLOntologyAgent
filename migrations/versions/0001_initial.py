"""Initial local Studio workflow schema. Revision: 0001."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('projects',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('domain', sa.String(), nullable=False),
                    sa.Column('approved_version_id', sa.String(), nullable=True),
                    sa.Column('corpus_snapshot_id', sa.String(), nullable=True),
                    sa.Column('pending_publication_id', sa.String(), nullable=True),
                    sa.Column('data', sa.JSON(), nullable=False))
    op.create_table('items',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=False),
                    sa.Column('kind', sa.String(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('created_at', sa.String(), nullable=False),
                    sa.Column('data', sa.JSON(), nullable=False))
    op.create_index('ix_items_project_id', 'items', ['project_id'])
    op.create_index('ix_items_kind', 'items', ['kind'])
    op.create_table('jobs',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), nullable=False),
                    sa.Column('kind', sa.String(), nullable=False),
                    sa.Column('idempotency_key', sa.String(), nullable=False),
                    sa.Column('payload_digest', sa.String(), nullable=False),
                    sa.Column('payload', sa.JSON(), nullable=False),
                    sa.Column('actor', sa.JSON(), nullable=False),
                    sa.Column('status', sa.String(), nullable=False),
                    sa.Column('result', sa.JSON(), nullable=True),
                    sa.Column('error', sa.String(), nullable=True),
                    sa.Column('attempt', sa.Integer(), nullable=False),
                    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
                    sa.Column('created_at', sa.String(), nullable=False),
                    sa.UniqueConstraint('project_id', 'idempotency_key'))
    op.create_index('ix_jobs_project_id', 'jobs', ['project_id'])


def downgrade():
    op.drop_table('jobs')
    op.drop_table('items')
    op.drop_table('projects')
