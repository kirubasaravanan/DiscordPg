import datetime

from app.models import Allocation, BedStatus, RoomStatus, User, UserRole


def test_building_room_bed_relationship_chain(db_session, building, room, bed):
    db_session.commit()

    assert [r.id for r in building.rooms] == [room.id]
    assert [b.id for b in room.beds] == [bed.id]
    assert bed.room.id == room.id
    assert room.building.id == building.id


def test_room_and_bed_status_defaults(db_session, room, bed):
    db_session.commit()
    assert room.status == RoomStatus.AVAILABLE
    assert bed.status == BedStatus.VACANT


def test_tenant_allocation_room_bed_relationships(db_session, tenant, room, bed):
    allocation = Allocation(tenant_id=tenant.id, room_id=room.id, bed_id=bed.id, start_date=datetime.date(2026, 1, 1))
    db_session.add(allocation)
    db_session.commit()

    assert tenant.allocations == [allocation]
    assert allocation.tenant.id == tenant.id
    assert allocation.room.id == room.id
    assert allocation.bed.id == bed.id


def test_user_tenant_link_disambiguates_from_audit_fks(db_session, tenant):
    """Regression test: Tenant has three FKs to users.id (user_id, created_by,
    updated_by from AuditUserMixin). Without explicit foreign_keys= on the
    Tenant.user / User.tenant relationship, SQLAlchemy can't determine which
    one to join on and raises AmbiguousForeignKeysError at mapper-configure
    time — this exercises that the relationship also *resolves correctly*,
    not just that it configures without error.
    """
    user = User(email="portal@example.com", password_hash="x", role=UserRole.TENANT)
    db_session.add(user)
    db_session.flush()
    tenant.user_id = user.id
    db_session.commit()

    db_session.refresh(tenant)
    db_session.refresh(user)
    assert tenant.user.id == user.id
    assert user.tenant.id == tenant.id


def test_audit_timestamps_populate(db_session, building):
    db_session.commit()
    assert building.created_at is not None
    assert building.updated_at is None  # only set by onupdate, not on insert

    building.name = "Renamed PG"
    db_session.commit()
    db_session.refresh(building)
    assert building.updated_at is not None


def test_soft_delete_defaults_false(db_session, building, tenant):
    db_session.commit()
    assert building.is_deleted is False
    assert tenant.is_deleted is False
