"""Apply migrations; adopt only an exact, unversioned known development schemas."""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Boolean, JSON, Column, DateTime, ForeignKey, Index, Integer, MetaData, String, Table, UniqueConstraint, create_engine, inspect

from oe_studio.settings import Settings


def initial_metadata():
    """Frozen 0001 schema: adoption must not follow later ORM model changes."""
    metadata = MetaData()
    Table('projects', metadata, Column('id', String, primary_key=True),
          Column('name', String, nullable=False), Column('domain', String, nullable=False),
          Column('approved_version_id', String), Column('corpus_snapshot_id', String),
          Column('pending_publication_id', String), Column('data', JSON, nullable=False))
    items = Table('items', metadata, Column('id', String, primary_key=True),
                  Column('project_id', String, ForeignKey('projects.id'), nullable=False),
                  Column('kind', String, nullable=False), Column('status', String, nullable=False),
                  Column('created_at', String, nullable=False), Column('data', JSON, nullable=False))
    Index('ix_items_project_id', items.c.project_id)
    Index('ix_items_kind', items.c.kind)
    jobs = Table('jobs', metadata, Column('id', String, primary_key=True),
                 Column('project_id', String, ForeignKey('projects.id'), nullable=False),
                 Column('kind', String, nullable=False), Column('idempotency_key', String, nullable=False),
                 Column('payload_digest', String, nullable=False), Column('payload', JSON, nullable=False),
                 Column('actor', JSON, nullable=False), Column('status', String, nullable=False),
                 Column('result', JSON), Column('error', String), Column('attempt', Integer, nullable=False),
                 Column('lease_until', DateTime(timezone=True)), Column('created_at', String, nullable=False),
                 UniqueConstraint('project_id', 'idempotency_key'))
    Index('ix_jobs_project_id', jobs.c.project_id)
    return metadata


def team_metadata():
    """Frozen 0002 schema, including the exact additive identity migration."""
    metadata = initial_metadata()
    Table('accounts', metadata, Column('id', String, primary_key=True),
          Column('username', String, nullable=False, unique=True),
          Column('password_hash', String, nullable=False), Column('enabled', Boolean, nullable=False),
          Column('auth_version', Integer, nullable=False))
    sessions = Table('account_sessions', metadata, Column('id', String, primary_key=True),
                     Column('account_id', String, ForeignKey('accounts.id'), nullable=False),
                     Column('token_hash', String, nullable=False, unique=True),
                     Column('csrf_hash', String, nullable=False), Column('auth_version', Integer, nullable=False),
                     Column('expires_at', String, nullable=False), Column('revoked', Boolean, nullable=False))
    Index('ix_account_sessions_account_id', sessions.c.account_id)
    Table('project_memberships', metadata,
          Column('account_id', String, ForeignKey('accounts.id'), primary_key=True),
          Column('project_id', String, ForeignKey('projects.id'), primary_key=True),
          Column('roles', JSON, nullable=False))
    Table('login_throttles', metadata, Column('key', String, primary_key=True),
          Column('failures', Integer, nullable=False), Column('window_start', String, nullable=False))
    return metadata


def migrate():
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            unversioned = tables and 'alembic_version' not in tables
            if unversioned:
                adopted = None
                for revision, metadata in [('0002', team_metadata()), ('0001', initial_metadata())]:
                    differences = compare_metadata(MigrationContext.configure(connection), metadata)
                    if tables == set(metadata.tables) and not differences:
                        adopted = revision
                        break
                if adopted is None:
                    raise ValueError('Refusing to stamp an unversioned database with a different schema')
        if unversioned:
            command.stamp(config, adopted)
            print(f'Adopted exact known development schema as migration {adopted}; data preserved.')
        command.upgrade(config, 'head')
    finally:
        engine.dispose()


if __name__ == '__main__':
    migrate()
