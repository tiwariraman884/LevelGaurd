"""
Shared pytest fixtures for LABELGUARD backend testing.
"""

from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


@pytest.fixture(scope="session")
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def admin_user(db_session: Session) -> User:
    user = db_session.get(User, 1)
    if not user:
        raise RuntimeError("Seed admin user with ID 1 not found in database.")
    return user


@pytest.fixture
def client(admin_user: User, db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_current_user():
        return admin_user

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
