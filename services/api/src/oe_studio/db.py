from contextlib import contextmanager
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, create_engine, event, text
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
