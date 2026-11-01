"""Apply migrations; adopt only an exact, unversioned initial development schema."""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from oe_studio.db import Base
from oe_studio.settings import Settings


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
                if ScriptDirectory.from_config(config).get_heads() != ['0001']:
                    raise ValueError('Unversioned database requires an explicit migration review after schema updates')
                differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
                if tables != set(Base.metadata.tables) or differences:
                    raise ValueError(f'Refusing to stamp an unversioned database with a different schema: {differences!r}')
        if unversioned:
            command.stamp(config, '0001')
            print('Adopted exact initial development schema as migration 0001; data preserved.')
        command.upgrade(config, 'head')
    finally:
        engine.dispose()


if __name__ == '__main__':
    migrate()
