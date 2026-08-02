import uuid

from sqlalchemy.orm import Session

from app.api.errors import conflict, not_found
from app.models import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.security.password import hash_password


def list_users(db: Session, *, limit: int, offset: int) -> tuple[list[User], int]:
    query = db.query(User).filter(User.is_deleted.is_(False)).order_by(User.email)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise not_found("User not found.")
    return user


def create_user(db: Session, payload: UserCreate, actor_id: uuid.UUID) -> User:
    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
        discord_id=payload.discord_id,
        created_by=actor_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: uuid.UUID, payload: UserUpdate, actor_id: uuid.UUID) -> User:
    user = get_user(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    demoting = "role" in data and data["role"] != UserRole.OWNER
    deactivating = data.get("is_active") is False
    if user.role == UserRole.OWNER and (demoting or deactivating) and not _other_active_owner_exists(db, user.id):
        raise conflict("Cannot remove the last active OWNER account.")

    password = data.pop("password", None)
    for field, value in data.items():
        setattr(user, field, value)
    if password:
        user.password_hash = hash_password(password)
    user.updated_by = actor_id
    db.commit()
    db.refresh(user)
    return user


def _other_active_owner_exists(db: Session, excluding_user_id: uuid.UUID) -> bool:
    return (
        db.query(User)
        .filter(
            User.role == UserRole.OWNER,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
            User.id != excluding_user_id,
        )
        .first()
        is not None
    )
