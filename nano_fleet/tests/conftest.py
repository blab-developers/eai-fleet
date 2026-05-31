"""Test fixtures — in-memory SQLite, no Docker."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from ..database import get_session
from ..main import app


@pytest.fixture
def test_engine():
    """In-memory SQLite engine with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_engine):
    """TestClient with dependency overrides for test engine."""

    def session_override():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    yield TestClient(app)
    app.dependency_overrides.clear()
