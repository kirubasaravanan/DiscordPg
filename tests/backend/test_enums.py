"""Confirm status columns are backed by real Postgres ENUM types, not just
app-level validation — i.e. the database itself rejects an invalid value
even via raw SQL that bypasses the ORM/Python enum entirely.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_database_rejects_invalid_room_status(db_session, building):
    db_session.commit()
    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                "INSERT INTO rooms (id, building_id, room_number, capacity, status) "
                "VALUES (gen_random_uuid(), :building_id, '1', 1, 'NOT_A_REAL_STATUS')"
            ),
            {"building_id": str(building.id)},
        )


def test_database_rejects_invalid_complaint_priority(db_session, tenant):
    db_session.commit()
    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                "INSERT INTO complaints (id, tenant_id, category, description, priority, status) "
                "VALUES (gen_random_uuid(), :tenant_id, 'OTHER', 'x', 'SUPER_URGENT', 'OPEN')"
            ),
            {"tenant_id": str(tenant.id)},
        )
