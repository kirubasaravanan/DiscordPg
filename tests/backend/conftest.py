import datetime
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models import Bed, Building, Room, Tenant
import app.models  # noqa: F401  (populates Base.metadata)

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
