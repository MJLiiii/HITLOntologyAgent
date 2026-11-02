from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String, default="unselected")
    approved_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    corpus_snapshot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_publication_id: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Item(Base):
    """Versioned workflow artifacts; only processing/status projections are mutable."""
    __tablename__ = "items"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[str] = mapped_column(String, default=now)
    data: Mapped[dict] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("project_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String)
    payload_digest: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    actor: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="queued")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Database:
    def __init__(self, url):
        self.sqlite = url.startswith("sqlite")
        self.engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if self.sqlite else {})
        if self.sqlite:
            @event.listens_for(self.engine, "connect")
            def pragma(conn, _):
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("PRAGMA journal_mode=WAL")
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.lock = RLock()

    def initialize(self):
        Base.metadata.create_all(self.engine)

    def ensure_migrated(self):
        """Team runtimes inspect migration state; only the operator migration command runs DDL."""
        with self.engine.connect() as connection:
            if 'alembic_version' not in inspect(connection).get_table_names():
                raise ValueError('Team database is not migrated; stop Studio and run make migrate')
            versions = list(connection.scalars(text('SELECT version_num FROM alembic_version')))
            if versions != ['0002']:
                raise ValueError('Team database migration is out of date; stop Studio and run make migrate')
            if not set(Base.metadata.tables) <= set(inspect(connection).get_table_names()):
                raise ValueError('Team database schema is incomplete; restore or repair the migrated database before starting Studio')

    @contextmanager
    def session(self, write=False):
        # ponytail: serialize local writes; switch to per-project locks for multi-project throughput.
        with self.lock if write else _NoLock():
            with self.factory() as session:
                try:
                    if write:
                        session.execute(text("BEGIN IMMEDIATE" if self.sqlite else "SELECT pg_advisory_xact_lock(74196321)"))
                    yield session
                    session.commit()
                except Exception:
                    session.rollback()
                    raise


class _NoLock:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Account(Base):
    __tablename__ = 'accounts'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=1)


class AccountSession(Base):
    __tablename__ = 'account_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String)
    auth_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[str] = mapped_column(String)
    revoked: Mapped[bool] = mapped_column(default=False)


class ProjectMembership(Base):
    __tablename__ = 'project_memberships'
    account_id: Mapped[str] = mapped_column(ForeignKey('accounts.id'), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.id'), primary_key=True)
    roles: Mapped[list] = mapped_column(JSON)


class LoginThrottle(Base):
    __tablename__ = 'login_throttles'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[str] = mapped_column(String)
