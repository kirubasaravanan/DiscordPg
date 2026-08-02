import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import PageParams, page_params, require_roles
from app.database.connection import get_db
from app.models import ExpenseCategory, User, UserRole
from app.schemas.common import Page
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.services import expense_service

router = APIRouter()

# No DELETE — expenses are append-only, corrected to match docs/DATABASE.md
# §2 (see docs/ARCHITECTURE.md §12 item 10). Mistakes are corrected via PATCH.
ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("", response_model=Page[ExpenseRead], dependencies=[Depends(require_roles(*ROLES))])
def list_expenses(
    building_id: uuid.UUID | None = Query(None),
    category: ExpenseCategory | None = Query(None),
    db: Session = Depends(get_db),
    pagination: PageParams = Depends(page_params),
) -> Page:
    items, total = expense_service.list_expenses(
        db, building_id=building_id, category=category, limit=pagination.page_size, offset=pagination.offset
    )
    return Page(items=items, page=pagination.page, page_size=pagination.page_size, total=total)


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ROLES)),
) -> ExpenseRead:
    return expense_service.create_expense(db, payload, actor_id=current_user.id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: uuid.UUID,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ROLES)),
) -> ExpenseRead:
    return expense_service.update_expense(db, expense_id, payload, actor_id=current_user.id)
