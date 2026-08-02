import datetime
import uuid

from sqlalchemy.orm import Session

from app.api.errors import bad_request, conflict, not_found
from app.models import Bed, BedStatus
from app.schemas.bed import BedCreate, BedUpdate
from app.services.room_service import get_room


def list_beds(db: Session, *, room_id: uuid.UUID | None, limit: int, offset: int) -> tuple[list[Bed], int]:
    query = db.query(Bed).filter(Bed.is_deleted.is_(False))
    if room_id is not None:
        query = query.filter(Bed.room_id == room_id)
    query = query.order_by(Bed.bed_number)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_bed(db: Session, bed_id: uuid.UUID) -> Bed:
    bed = db.get(Bed, bed_id)
    if bed is None or bed.is_deleted:
        raise not_found("Bed not found.")
    return bed


def create_bed(db: Session, payload: BedCreate, actor_id: uuid.UUID) -> Bed:
    get_room(db, payload.room_id)  # 404s if the room doesn't exist
    bed = Bed(**payload.model_dump(), created_by=actor_id)
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return bed


def update_bed(db: Session, bed_id: uuid.UUID, payload: BedUpdate, actor_id: uuid.UUID) -> Bed:
    bed = get_bed(db, bed_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == BedStatus.OCCUPIED:
        raise bad_request(
            "status cannot be set to OCCUPIED directly — it's derived from allocations.",
            field="status",
        )
    for field, value in data.items():
        setattr(bed, field, value)
    bed.updated_by = actor_id
    db.commit()
    db.refresh(bed)
    return bed


def delete_bed(db: Session, bed_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    bed = get_bed(db, bed_id)
    if bed.status == BedStatus.OCCUPIED:
        raise conflict("Cannot delete a bed that is currently occupied.")
    bed.is_deleted = True
    bed.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    bed.updated_by = actor_id
    db.commit()
