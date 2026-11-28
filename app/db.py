from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_sessions: sessionmaker[Session] | None = None


def configure(url: str) -> Engine:
    """Creates the engine. Called lazily, and by tests to point at a temporary database."""
    global _engine, _sessions
    if _engine is not None:
        _engine.dispose()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    _sessions = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def engine() -> Engine:
    if _engine is None:
        configure(settings.database_url)
    assert _engine is not None
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    engine()
    assert _sessions is not None
    session = _sessions()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session
