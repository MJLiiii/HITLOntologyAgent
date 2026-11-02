"""Add operator-provisioned team identities without modifying workflow artifacts."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('accounts',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('username', sa.String(), nullable=False, unique=True),
                    sa.Column('password_hash', sa.String(), nullable=False),
                    sa.Column('enabled', sa.Boolean(), nullable=False),
                    sa.Column('auth_version', sa.Integer(), nullable=False))
    op.create_table('account_sessions',
                    sa.Column('id', sa.String(), primary_key=True),
                    sa.Column('account_id', sa.String(), sa.ForeignKey('accounts.id'), nullable=False),
                    sa.Column('token_hash', sa.String(), nullable=False, unique=True),
                    sa.Column('csrf_hash', sa.String(), nullable=False),
                    sa.Column('auth_version', sa.Integer(), nullable=False),
                    sa.Column('expires_at', sa.String(), nullable=False),
                    sa.Column('revoked', sa.Boolean(), nullable=False))
    op.create_index('ix_account_sessions_account_id', 'account_sessions', ['account_id'])
    op.create_table('project_memberships',
                    sa.Column('account_id', sa.String(), sa.ForeignKey('accounts.id'), primary_key=True),
                    sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id'), primary_key=True),
                    sa.Column('roles', sa.JSON(), nullable=False))
    op.create_table('login_throttles',
                    sa.Column('key', sa.String(), primary_key=True),
                    sa.Column('failures', sa.Integer(), nullable=False),
                    sa.Column('window_start', sa.String(), nullable=False))


def downgrade():
    for name in ('login_throttles', 'project_memberships', 'account_sessions', 'accounts'):
        op.drop_table(name)
