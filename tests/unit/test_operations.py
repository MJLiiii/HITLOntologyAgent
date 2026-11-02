import json
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect

from oe_studio.artifacts import ArtifactStore
from oe_studio.db import Database, Item, Project
from oe_studio.git_store import GitStore
from scripts.backup_restore import backup, restore
from scripts.migrate import migrate


def populated_store(root):
    root.mkdir()
    db = Database(f'sqlite:///{root / "studio.sqlite"}')
    db.initialize()
    artifact = ArtifactStore(root / 'artifacts').put(b'synthetic ontology', 'text/turtle')
    git = GitStore(root / 'ontology.git')
    commit = git.commit({'ontology.ttl': b'synthetic ontology'}, None, 'Synthetic backup fixture')
    git.advance('demo-project', commit, None)
    with db.session(write=True) as session:
        session.add(Project(id='demo-project', name='Demo', domain='demo', approved_version_id='release'))
        session.flush()
        session.add(Item(id='release', project_id='demo-project', kind='version', status='published',
                         data={'ontology': artifact, 'commit': commit}))
    db.engine.dispose()
    return commit


def test_restore_preserves_database_artifacts_and_approved_git_head(tmp_path):
    source, snapshot, restored = (tmp_path / name for name in ('data', 'snapshot', 'restored'))
    commit = populated_store(source)
    (source / 'session.key').write_text('not copied')
    manifest = backup(source, snapshot)
    state = restore(snapshot, restored)
    assert state['projects'] == [['demo-project', 'release']]
    assert state['git_refs'] == [f'{commit} refs/heads/demo-project-approved']
    assert not (restored / 'session.key').exists()
    assert manifest['contents']['studio.sqlite']
    assert len(list((restored / 'artifacts').iterdir())) == 1


def test_backup_and_restore_reject_corrupt_artifacts(tmp_path):
    source, snapshot = tmp_path / 'data', tmp_path / 'snapshot'
    populated_store(source)
    backup(source, snapshot)
    artifact = next((snapshot / 'artifacts').iterdir())
    artifact.write_text('tampered')
    with pytest.raises(ValueError, match='hash mismatch'):
        restore(snapshot, tmp_path / 'restored')
    original = next((source / 'artifacts').iterdir())
    original.write_text('tampered')
    with pytest.raises(ValueError, match='Artifact hash mismatch'):
        backup(source, tmp_path / 'second')


def test_backup_does_not_overwrite_or_recurse_into_application_data(tmp_path):
    source = tmp_path / 'data'
    populated_store(source)
    with pytest.raises(ValueError, match='separate'):
        backup(source, source / 'snapshot')
    existing = tmp_path / 'existing'
    existing.mkdir()
    with pytest.raises(ValueError, match='already exist'):
        backup(source, existing)


def test_migration_matches_declared_schema(tmp_path, monkeypatch):
    monkeypatch.setenv('OE_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{tmp_path / "studio.sqlite"}')
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    command.upgrade(config, 'head')
    command.check(config)
    db = Database(f'sqlite:///{tmp_path / "studio.sqlite"}')
    assert {'projects', 'items', 'jobs', 'accounts', 'account_sessions', 'project_memberships', 'login_throttles', 'alembic_version'} == set(inspect(db.engine).get_table_names())
    assert json.dumps(inspect(db.engine).get_unique_constraints('jobs'))
    db.engine.dispose()


def test_migrate_adopts_only_identical_legacy_schema_and_preserves_rows(tmp_path, monkeypatch):
    source = tmp_path / 'data'
    populated_store(source)
    db = Database(f'sqlite:///{source / "studio.sqlite"}')
    with db.engine.begin() as connection:
        for name in ('login_throttles', 'project_memberships', 'account_sessions', 'accounts'):
            connection.exec_driver_sql(f'DROP TABLE {name}')
    db.engine.dispose()
    monkeypatch.setenv('OE_DATA_DIR', str(source))
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{source / "studio.sqlite"}')
    migrate()
    db = Database(f'sqlite:///{source / "studio.sqlite"}')
    with db.session() as session:
        assert session.get(Project, 'demo-project').approved_version_id == 'release'
    assert 'alembic_version' in inspect(db.engine).get_table_names()
    db.engine.dispose()


def test_migrate_refuses_unversioned_schema_drift(tmp_path, monkeypatch):
    import sqlite3
    source = tmp_path / 'data'
    populated_store(source)
    monkeypatch.setenv('OE_DATA_DIR', str(source))
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{source / "studio.sqlite"}')
    with sqlite3.connect(source / 'studio.sqlite') as connection:
        connection.execute('ALTER TABLE projects ADD COLUMN unexpected TEXT')
    with pytest.raises(ValueError, match='different schema'):
        migrate()
    with sqlite3.connect(source / 'studio.sqlite') as connection:
        assert connection.execute("SELECT count(*) FROM sqlite_master WHERE name='alembic_version'").fetchone()[0] == 0


def test_migrate_adopts_exact_unversioned_team_schema_preserving_rows(tmp_path, monkeypatch):
    source = tmp_path / 'data'
    populated_store(source)
    monkeypatch.setenv('OE_DATA_DIR', str(source))
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{source / "studio.sqlite"}')
    from oe_studio.accounts import create_account
    db = Database(f'sqlite:///{source / "studio.sqlite"}')
    account = create_account(db, 'synthetic', 'synthetic account password')
    db.engine.dispose()
    migrate()
    from oe_studio.db import Account
    db = Database(f'sqlite:///{source / "studio.sqlite"}')
    db.ensure_migrated()
    with db.session() as session:
        assert session.get(Project, 'demo-project').approved_version_id == 'release'
        assert session.get(Account, account.id).password_hash == account.password_hash
    db.engine.dispose()
