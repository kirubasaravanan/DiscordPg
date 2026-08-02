import datetime
import uuid

from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.models import Complaint, ComplaintCategory, ComplaintStatus, Priority
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate
from app.services.room_service import get_room


def _classify_placeholder(
    description: str, suggested_category: ComplaintCategory | None
) -> tuple[ComplaintCategory, Priority]:
    """Stand-in for the Phase 6 AI classifier (docs/ARCHITECTURE.md §6.1,
    §12 item 11) — that service doesn't exist yet. Until it does: use the
    tenant's optional suggestion, or `OTHER`; priority always starts at
    `MEDIUM` for staff to triage manually.

    `description` is intentionally unused for now (it becomes the AI
    service's input in Phase 6) — kept as a parameter so this function's
    signature doesn't need to change when that lands, only its body.
    """
    del description
    category = suggested_category or ComplaintCategory.OTHER
    priority = Priority.MEDIUM
    return category, priority


def list_complaints(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    room_id: uuid.UUID | None,
    status: ComplaintStatus | None,
    priority: Priority | None,
    limit: int,
    offset: int,
) -> tuple[list[Complaint], int]:
    query = db.query(Complaint)
    if tenant_id is not None:
        query = query.filter(Complaint.tenant_id == tenant_id)
    if room_id is not None:
        query = query.filter(Complaint.room_id == room_id)
    if status is not None:
        query = query.filter(Complaint.status == status)
    if priority is not None:
        query = query.filter(Complaint.priority == priority)
    query = query.order_by(Complaint.created_at.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_complaint(db: Session, complaint_id: uuid.UUID) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise not_found("Complaint not found.")
    return complaint


def create_complaint(db: Session, tenant_id: uuid.UUID, payload: ComplaintCreate, actor_id: uuid.UUID) -> Complaint:
    if payload.room_id is not None:
        get_room(db, payload.room_id)  # 404s if the room doesn't exist
    category, priority = _classify_placeholder(payload.description, payload.category)
    complaint = Complaint(
        tenant_id=tenant_id,
        room_id=payload.room_id,
        category=category,
        description=payload.description,
        priority=priority,
        status=ComplaintStatus.OPEN,
        created_by=actor_id,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


def update_complaint(db: Session, complaint_id: uuid.UUID, payload: ComplaintUpdate, actor_id: uuid.UUID) -> Complaint:
    complaint = get_complaint(db, complaint_id)
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    for field, value in data.items():
        setattr(complaint, field, value)
    # RESOLVED stamps resolved_at; REOPENED explicitly un-resolves it. Every
    # other transition (OPEN, IN_PROGRESS, CLOSED) leaves resolved_at as-is —
    # CLOSED in particular is expected to normally follow RESOLVED, and
    # clearing the timestamp there would lose when it was actually fixed.
    if new_status == ComplaintStatus.RESOLVED:
        complaint.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    elif new_status == ComplaintStatus.REOPENED:
        complaint.resolved_at = None
    complaint.updated_by = actor_id
    db.commit()
    db.refresh(complaint)
    return complaint
