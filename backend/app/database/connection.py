from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, echo=settings.database_echo, pool_pre_ping=True)

# autoflush=True (the default) matters here: services that modify an object
# and then query based on that change within the same transaction (e.g.
# allocation_service syncing Room.status from Bed occupancy) need the pending
# UPDATE visible to the SELECT, not just at the next commit.
SessionLocal = sessionmaker(bind=engine, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
