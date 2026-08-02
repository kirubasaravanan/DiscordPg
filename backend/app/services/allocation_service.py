import datetime
import uuid

from sqlalchemy.orm import Session

from app.api.errors import bad_request, conflict, not_found
from app.models import Allocation, Bed, BedStatus, Room, RoomStatus
from app.schemas.allocation import AllocationCreate
from app.services.bed_service import get_bed
from app.services.tenant_service import get_tenant


def list_allocations(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    room_id: uuid.UUID | None,
    bed_id: uuid.UUID | None,
    active_only: bool,
    limit: int,
    offset: int,
) -> tuple[list[Allocation], int]:
    query = db.query(Allocation)
    if tenant_id is not None:
        query = query.filter(Allocation.tenant_id == tenant_id)
    if room_id is not None:
        query = query.filter(Allocation.room_id == room_id)
    if bed_id is not None:
        query = query.filter(Allocation.bed_id == bed_id)
    if active_only:
        query = query.filter(Allocation.end_date.is_(None))
    query = query.order_by(Allocation.start_date.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_allocation(db: Session, allocation_id: uuid.UUID) -> Allocation:
    allocation = db.get(Allocation, allocation_id)
    if allocation is None:
        raise not_found("Allocation not found.")
    return allocation


def create_allocation(db: Session, payload: AllocationCreate, actor_id: uuid.UUID) -> Allocation:
    tenant = get_tenant(db, payload.tenant_id)
    bed = get_bed(db, payload.bed_id)

    if bed.status != BedStatus.VACANT:
        raise conflict(f"Bed is not vacant (current status: {bed.status.value}).")

    allocation = Allocation(
        tenant_id=tenant.id,
        room_id=bed.room_id,
        bed_id=bed.id,
        start_date=payload.start_date,
        created_by=actor_id,
    )
    db.add(allocation)
    bed.status = BedStatus.OCCUPIED
    bed.updated_by = actor_id
    _sync_room_status(db, bed.room_id, actor_id)

    db.commit()
    db.refresh(allocation)
    return allocation


def end_allocation(
    db: Session, allocation_id: uuid.UUID, end_date: datetime.date | None, actor_id: uuid.UUID
) -> Allocation:
    allocation = get_allocation(db, allocation_id)
    if allocation.end_date is not None:
        raise conflict("This allocation has already ended.")

    resolved_end_date = end_date or datetime.date.today()
    if resolved_end_date < allocation.start_date:
        raise bad_request("end_date cannot be before start_date.", field="end_date")

    allocation.end_date = resolved_end_date
    allocation.updated_by = actor_id

    bed = get_bed(db, allocation.bed_id)
    bed.status = BedStatus.VACANT
    bed.updated_by = actor_id
    _sync_room_status(db, bed.room_id, actor_id)

    db.commit()
    db.refresh(allocation)
    return allocation


def _sync_room_status(db: Session, room_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    """Keeps Room.status's AVAILABLE/FULL value in sync with actual bed
    occupancy. Only ever moves between those two values — MAINTENANCE/
    INACTIVE are staff-managed (app/services/room_service.py) and left alone,
    e.g. a room taken offline for renovation shouldn't flip back to AVAILABLE
    just because its last tenant checked out.
    """
    room = db.get(Room, room_id)
    if room is None or room.status not in (RoomStatus.AVAILABLE, RoomStatus.FULL):
        return
    has_vacant_bed = (
        db.query(Bed)
        .filter(Bed.room_id == room_id, Bed.is_deleted.is_(False), Bed.status == BedStatus.VACANT)
        .first()
        is not None
    )
    new_status = RoomStatus.AVAILABLE if has_vacant_bed else RoomStatus.FULL
    if room.status != new_status:
        room.status = new_status
        room.updated_by = actor_id
