import uuid

from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.models import Expense, ExpenseCategory
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services.building_service import get_building


def list_expenses(
    db: Session,
    *,
    building_id: uuid.UUID | None,
    category: ExpenseCategory | None,
    limit: int,
    offset: int,
) -> tuple[list[Expense], int]:
    query = db.query(Expense)
    if building_id is not None:
        query = query.filter(Expense.building_id == building_id)
    if category is not None:
        query = query.filter(Expense.category == category)
    query = query.order_by(Expense.date.desc())
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def get_expense(db: Session, expense_id: uuid.UUID) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise not_found("Expense not found.")
    return expense


def create_expense(db: Session, payload: ExpenseCreate, actor_id: uuid.UUID) -> Expense:
    if payload.building_id is not None:
        get_building(db, payload.building_id)  # 404s if the building doesn't exist
    expense = Expense(**payload.model_dump(), created_by=actor_id)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def update_expense(db: Session, expense_id: uuid.UUID, payload: ExpenseUpdate, actor_id: uuid.UUID) -> Expense:
    expense = get_expense(db, expense_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("building_id") is not None:
        get_building(db, data["building_id"])
    for field, value in data.items():
        setattr(expense, field, value)
    expense.updated_by = actor_id
    db.commit()
    db.refresh(expense)
    return expense
