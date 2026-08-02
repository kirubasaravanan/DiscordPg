import datetime
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.connection import get_db
from app.main import app as fastapi_app
from app.models import Bed, Building, Room, Tenant, User, UserRole
import app.models  # noqa: F401  (populates Base.metadata)
from app.security.jwt import create_access_token
from app.security.password import hash_password

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://pgos:pgos_local_dev_password@localhost:5432/pgos_test",
)


@pytest.fixture(scope="session")
def engine():
    """One engine for the whole test session; schema created once up front."""
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db_session(engine):
    """A session isolated in its own transaction, rolled back after each test.

    Uses SQLAlchemy's savepoint-backed join mode so that code under test is
    free to call `session.commit()` (as the service layer and seed script
    do) without ending the outer transaction early — see "Joining a Session
    into an External Transaction" in the SQLAlchemy docs.
    """
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture
def building(db_session) -> Building:
    b = Building(name="Test PG", address="1 Test Street")
    db_session.add(b)
    db_session.flush()
    return b


@pytest.fixture
def room(db_session, building) -> Room:
    r = Room(building_id=building.id, room_number="101", floor=1, capacity=2)
    db_session.add(r)
    db_session.flush()
    return r


@pytest.fixture
def bed(db_session, room) -> Bed:
    bd = Bed(room_id=room.id, bed_number="A")
    db_session.add(bd)
    db_session.flush()
    return bd


@pytest.fixture
def tenant(db_session) -> Tenant:
    t = Tenant(name="Test Tenant", phone="9000000000", joining_date=datetime.date(2026, 1, 1))
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def client(db_session):
    """TestClient wired to the same isolated, rolled-back-after-test session
    as every other fixture — an API test and a model test observe the same
    transaction, so fixtures like `building`/`tenant` are visible to it.
    """

    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def make_user(db_session):
    """Factory fixture: make_user(UserRole.OWNER, password="...", email="...")."""

    def _make(role: UserRole, *, email: str | None = None, password: str = "Test-Pass123!", **kwargs) -> User:
        email = email or f"{role.value.lower()}-{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password(password), role=role, **kwargs)
        db_session.add(user)
        db_session.flush()
        return user

    return _make


def auth_headers(user: User) -> dict[str, str]:
    """Builds a valid Authorization header directly from a user, bypassing
    the login endpoint — for tests where the thing under test isn't login
    itself, just "an authenticated request as this role".
    """
    token = create_access_token(user.id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def owner_user(make_user) -> User:
    return make_user(UserRole.OWNER)


@pytest.fixture
def manager_user(make_user) -> User:
    return make_user(UserRole.MANAGER)


@pytest.fixture
def staff_user(make_user) -> User:
    return make_user(UserRole.STAFF)


@pytest.fixture
def tenant_with_user(db_session, make_user) -> tuple[Tenant, User]:
    """A Tenant row with a linked TENANT-role User account — for self-service
    endpoint tests, which need both the tenant data and a way to authenticate
    as that specific tenant.
    """
    user = make_user(UserRole.TENANT)
    t = Tenant(name="Linked Tenant", phone="9000000099", joining_date=datetime.date(2026, 1, 1), user_id=user.id)
    db_session.add(t)
    db_session.flush()
    return t, user
