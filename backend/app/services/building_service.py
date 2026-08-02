import datetime
import uuid

from sqlalchemy.orm import Session

from app.api.errors import conflict, not_found
from app.models import Building, Room
from app.schemas.building import BuildingCreate, BuildingUpdate


def list_buildings(db: Session, *, limit: int, offset: int) -> tuple[list[Building], int]:
    query = db.query(Building).filter(Building.is_deleted.is_(False)).order_by(Building.name)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_building(db: Session, building_id: uuid.UUID) -> Building:
    building = db.get(Building, building_id)
    if building is None or building.is_deleted:
        raise not_found("Building not found.")
    return building


def create_building(db: Session, payload: BuildingCreate, actor_id: uuid.UUID) -> Building:
    building = Building(**payload.model_dump(), created_by=actor_id)
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


def update_building(db: Session, building_id: uuid.UUID, payload: BuildingUpdate, actor_id: uuid.UUID) -> Building:
    building = get_building(db, building_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(building, field, value)
    building.updated_by = actor_id
    db.commit()
    db.refresh(building)
    return building


def delete_building(db: Session, building_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    building = get_building(db, building_id)
    has_active_rooms = (
        db.query(Room).filter(Room.building_id == building_id, Room.is_deleted.is_(False)).first() is not None
    )
    if has_active_rooms:
        raise conflict("Cannot delete a building that still has active rooms.")
    building.is_deleted = True
    building.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    building.updated_by = actor_id
    db.commit()
