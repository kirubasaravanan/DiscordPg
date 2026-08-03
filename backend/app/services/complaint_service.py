import datetime
import logging
import uuid

from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.models import Complaint, ComplaintCategory, ComplaintStatus, Priority
from app.schemas.complaint import ComplaintCreate, ComplaintUpdate
from app.services import ai_client
from app.services.room_service import get_room

logger = logging.getLogger(__name__)


def _classify(
    description: str, suggested_category: ComplaintCategory | None
) -> tuple[ComplaintCategory, Priority, str | None]:
    """Calls the Phase 6 AI classifier (docs/AI_DESIGN.md §2) and validates
    its output against the real enums before returning anything — the
    classifier's output is a suggestion; this function is what actually
    enforces it, per docs/ARCHITECTURE.md §5 item 5 ("the service layer
    validates it against real constraints").

    Falls back to the tenant's own suggestion (or `OTHER`) and `MEDIUM`
    priority — the exact Phase 3b placeholder behavior — on ANY failure:
    ai_engine unreachable, a malformed response, or an invalid/hallucinated
    enum value. Filing a complaint must never fail because the AI service
    happens to be down.
    """
    fallback_category = suggested_category or ComplaintCategory.OTHER
    fallback_priority = Priority.MEDIUM

    try:
        result = ai_client.classify_complaint(description)
    except ai_client.AIServiceError as exc:
        logger.warning("Complaint classifier unavailable, using fallback: %s", exc)
        return fallback_category, fallback_priority, None

    try:
        category = ComplaintCategory(result.get("category"))
    except ValueError:
        logger.warning("Classifier returned an invalid category %r, using fallback", result.get("category"))
        category = fallback_category

    try:
        priority = Priority(result.get("priority"))
    except ValueError:
        logger.warning("Classifier returned an invalid priority %r, using fallback", result.get("priority"))
        priority = fallback_priority

    suggested_action = result.get("suggested_action")
    if not isinstance(suggested_action, str) or not suggested_action.strip():
        suggested_action = None

    return category, priority, suggested_action


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
    category, priority, suggested_action = _classify(payload.description, payload.category)
    complaint = Complaint(
        tenant_id=tenant_id,
        room_id=payload.room_id,
        category=category,
        description=payload.description,
        priority=priority,
        suggested_action=suggested_action,
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
