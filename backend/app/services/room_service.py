import datetime
import uuid

from sqlalchemy.orm import Session

from app.api.errors import bad_request, conflict, not_found
from app.models import Bed, Room, RoomStatus
from app.schemas.room import RoomCreate, RoomUpdate
from app.services.building_service import get_building


def list_rooms(db: Session, *, building_id: uuid.UUID | None, limit: int, offset: int) -> tuple[list[Room], int]:
    query = db.query(Room).filter(Room.is_deleted.is_(False))
    if building_id is not None:
        query = query.filter(Room.building_id == building_id)
    query = query.order_by(Room.room_number)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_room(db: Session, room_id: uuid.UUID) -> Room:
    room = db.get(Room, room_id)
    if room is None or room.is_deleted:
        raise not_found("Room not found.")
    return room


def create_room(db: Session, payload: RoomCreate, actor_id: uuid.UUID) -> Room:
    get_building(db, payload.building_id)  # 404s if the building doesn't exist
    room = Room(**payload.model_dump(), created_by=actor_id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def update_room(db: Session, room_id: uuid.UUID, payload: RoomUpdate, actor_id: uuid.UUID) -> Room:
    room = get_room(db, room_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == RoomStatus.FULL:
        raise bad_request(
            "status cannot be set to FULL directly — it's derived from bed occupancy via allocations.",
            field="status",
        )
    for field, value in data.items():
        setattr(room, field, value)
    room.updated_by = actor_id
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    room = get_room(db, room_id)
    has_active_beds = db.query(Bed).filter(Bed.room_id == room_id, Bed.is_deleted.is_(False)).first() is not None
    if has_active_beds:
        raise conflict("Cannot delete a room that still has active beds.")
    room.is_deleted = True
    room.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    room.updated_by = actor_id
    db.commit()
