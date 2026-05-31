"""Database engine + session (SQLModel)."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create tables if missing."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with Session(engine) as session:
        yield session
