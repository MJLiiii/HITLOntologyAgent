import pytest
from oe_studio.db import Database, Project
from oe_studio.settings import Settings
from oe_studio.errors import Problem
from oe_studio import accounts


@pytest.fixture
def store(tmp_path):
    db = Database(f'sqlite:///{tmp_path}/accounts.sqlite')
    db.initialize()
    settings = Settings(mode='team', team_test_sqlite=True, data_dir=tmp_path)
    user = accounts.create_account(db, 'alice', 'a sufficiently long password')
    with db.session(write=True) as s:
        s.add(Project(id='p1', name='One'))
        s.add(Project(id='p2', name='Two'))
    accounts.grant_project(db, user.id, 'p1', ['viewer', 'researcher'])
    return db, settings, user


def test_membership_and_revocation(store):
    db, settings, user = store
    actor, token, csrf = accounts.login(db, settings, 'alice', 'a sufficiently long password', 'peer')
    assert token not in str(actor) and csrf not in str(actor)
    assert accounts.authorize_project(db, actor, 'p1', 'researcher')['roles'] == ['researcher', 'viewer']
    for project, role in [('p2', 'viewer'), ('p1', 'approver')]:
        with pytest.raises(Problem):
            accounts.authorize_project(db, actor, project, role)
    accounts.revoke_session(db, actor['session_id'], user.id)
    with pytest.raises(Problem):
        accounts.revalidate_actor(db, actor)


def test_reset_and_disable_revoke(store):
    db, settings, user = store
    actor, _, _ = accounts.login(db, settings, 'alice', 'a sufficiently long password', 'peer')
    accounts.reset_password(db, user.id, 'another sufficiently long password')
    with pytest.raises(Problem):
        accounts.revalidate_actor(db, actor)
    actor, _, _ = accounts.login(db, settings, 'alice', 'another sufficiently long password', 'peer')
    accounts.disable_account(db, user.id)
    with pytest.raises(Problem):
        accounts.revalidate_actor(db, actor)


def test_throttle(store):
    db, settings, _ = store
    for _ in range(5):
        with pytest.raises(Problem) as failure:
            accounts.login(db, settings, 'alice', 'wrong', 'peer')
        assert failure.value.status == 401
    with pytest.raises(Problem) as failure:
        accounts.login(db, settings, 'alice', 'a sufficiently long password', 'peer')
    assert failure.value.status == 429


def test_request_csrf_and_exact_origin(store):
    from types import SimpleNamespace
    from starlette.requests import Request
    db, settings, _ = store
    settings.team_origin = 'https://studio.example'
    actor, token, csrf = accounts.login(db, settings, 'alice', 'a sufficiently long password', 'peer')
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, studio=SimpleNamespace(db=db)))
    def request(origin, csrf_header):
        return Request(dict(type='http', method='POST', path='/', app=app,
                            headers=[(b'cookie', f'oe_session={token}'.encode()),
                                     (b'origin', origin.encode()), (b'x-csrf-token', csrf_header.encode())]))
    assert accounts.authenticate_request(request(settings.team_origin, csrf))['subject'] == actor['subject']
    for origin, header in [('https://studio.example.attacker', csrf), (settings.team_origin, ''), ('', csrf)]:
        with pytest.raises(Problem):
            accounts.authenticate_request(request(origin, header))
    new_csrf = accounts.rotate_csrf(db, actor, token)
    assert new_csrf == csrf == accounts.rotate_csrf(db, actor, token)
    with pytest.raises(Problem):
        accounts.rotate_csrf(db, actor, "wrong-token")
    accounts.authenticate_request(request(settings.team_origin, new_csrf))


def test_team_requires_postgres_and_https(tmp_path):
    with pytest.raises(ValueError):
        Settings(mode='team', data_dir=tmp_path, team_origin='https://studio.example')
    with pytest.raises(ValueError):
        Settings(mode='team', team_test_sqlite=True, team_origin='http://studio.example')


def test_migrations_preserve_initial_rows(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from scripts.migrate import migrate
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{tmp_path}/migrate.sqlite')
    monkeypatch.setenv('OE_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('OE_MODE', 'local')
    config = Config('alembic.ini')
    command.upgrade(config, '0001')
    engine = create_engine(f'sqlite:///{tmp_path}/migrate.sqlite')
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO projects (id,name,domain,data) VALUES ('original','Original','synthetic','{}')"))
        connection.execute(text('DROP TABLE alembic_version'))
    migrate()
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT name FROM projects')) == 'Original'
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0002'
    engine.dispose()


@pytest.mark.parametrize('granted', ['viewer', 'researcher', 'reviewer', 'approver'])
def test_explicit_role_matrix(store, granted):
    db, settings, user = store
    accounts.grant_project(db, user.id, 'p1', [granted])
    actor, _, _ = accounts.login(db, settings, user.username, 'a sufficiently long password', 'peer')
    assert accounts.authorize_project(db, actor, 'p1', 'viewer')
    for requested in ['researcher', 'reviewer', 'approver']:
        if requested == granted:
            accounts.authorize_project(db, actor, 'p1', requested)
        else:
            with pytest.raises(Problem):
                accounts.authorize_project(db, actor, 'p1', requested)


def test_expired_session_and_disabled_login(store):
    from datetime import timedelta
    from oe_studio.db import AccountSession
    db, settings, user = store
    actor, _, _ = accounts.login(db, settings, user.username, 'a sufficiently long password', 'peer')
    with db.session(write=True) as s:
        s.get(AccountSession, actor['session_id']).expires_at = (accounts.utc() - timedelta(seconds=1)).isoformat()
    with pytest.raises(Problem):
        accounts.revalidate_actor(db, actor)
    accounts.disable_account(db, user.id)
    with pytest.raises(Problem) as failure:
        accounts.login(db, settings, user.username, 'a sufficiently long password', 'peer')
    assert failure.value.status == 401


def test_migration_refuses_unknown_unversioned_schema(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from scripts.migrate import migrate
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{tmp_path}/unknown.sqlite')
    monkeypatch.setenv('OE_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('OE_MODE', 'local')
    engine = create_engine(f'sqlite:///{tmp_path}/unknown.sqlite')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE unrelated (id INTEGER PRIMARY KEY)'))
    with pytest.raises(ValueError, match='different schema'):
        migrate()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT name FROM sqlite_master WHERE name='unrelated'")) == 'unrelated'
    engine.dispose()


def test_team_runtime_requires_migrations_without_ddl(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text
    monkeypatch.setenv('OE_DATABASE_URL', f'sqlite:///{tmp_path}/startup.sqlite')
    monkeypatch.setenv('OE_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('OE_MODE', 'local')
    db = Database(f'sqlite:///{tmp_path}/startup.sqlite')
    with pytest.raises(ValueError, match='make migrate'):
        db.ensure_migrated()
    assert inspect(db.engine).get_table_names() == []
    command.upgrade(Config('alembic.ini'), '0001')
    with db.engine.begin() as connection:
        connection.execute(text("INSERT INTO projects (id,name,domain,data) VALUES ('kept','Kept','synthetic','{}')"))
    before = set(inspect(db.engine).get_table_names())
    with pytest.raises(ValueError, match='make migrate'):
        db.ensure_migrated()
    assert set(inspect(db.engine).get_table_names()) == before
    assert 'accounts' not in before
    with db.engine.connect() as connection:
        assert connection.scalar(text('SELECT name FROM projects')) == 'Kept'
    command.upgrade(Config('alembic.ini'), 'head')
    db.ensure_migrated()
    with db.engine.connect() as connection:
        assert connection.scalar(text('SELECT name FROM projects')) == 'Kept'
    db.engine.dispose()
def test_invalid_team_settings_do_not_echo_connection_credentials(tmp_path):
    from pydantic import ValidationError
    from oe_studio.settings import Settings
    import pytest
    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None, data_dir=tmp_path, mode='team',
                 database_url='postgresql+psycopg://user:synthetic-password@127.0.0.1/db',
                 team_origin='http://untrusted.example')
    assert 'input_value=' not in str(failure.value)
    assert 'synthetic-password' not in str(failure.value)

