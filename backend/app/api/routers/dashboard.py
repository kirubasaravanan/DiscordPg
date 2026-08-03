from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.connection import get_db
from app.models import UserRole
from app.schemas.dashboard import ComplaintsReport, DashboardRead, IncomeReport, OccupancyReport, SummaryResponse
from app.services import dashboard_service, scheduled_jobs

router = APIRouter()

# docs/API.md §5.12 marks dashboard access "OWNER, MANAGER, STAFF (partial)"
# but doesn't split the payload by role — STAFF gets the same summary as
# everyone else. A single aggregate expenses total isn't the line-item detail
# that Expenses'/Deposits' own stricter RBAC is protecting against.
DASHBOARD_ROLES = (UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)
REPORT_ROLES = (UserRole.OWNER, UserRole.MANAGER)


@router.get("/dashboard", response_model=DashboardRead, dependencies=[Depends(require_roles(*DASHBOARD_ROLES))])
def get_dashboard(db: Session = Depends(get_db)) -> DashboardRead:
    return dashboard_service.get_dashboard_summary(db)


@router.get("/reports/income", response_model=IncomeReport, dependencies=[Depends(require_roles(*REPORT_ROLES))])
def get_income_report(months: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)) -> IncomeReport:
    return IncomeReport(rows=dashboard_service.get_income_report(db, months=months))


@router.get("/reports/occupancy", response_model=OccupancyReport, dependencies=[Depends(require_roles(*REPORT_ROLES))])
def get_occupancy_report(db: Session = Depends(get_db)) -> OccupancyReport:
    return OccupancyReport(rows=dashboard_service.get_occupancy_report(db))


@router.get("/reports/complaints", response_model=ComplaintsReport, dependencies=[Depends(require_roles(*REPORT_ROLES))])
def get_complaints_report(db: Session = Depends(get_db)) -> ComplaintsReport:
    return ComplaintsReport(by_category=dashboard_service.get_complaints_report(db))


@router.get("/reports/summary", response_model=SummaryResponse, dependencies=[Depends(require_roles(*REPORT_ROLES))])
def get_management_summary(db: Session = Depends(get_db)) -> dict:
    """On-demand version of the daily 21:00 job (docs/AI_DESIGN.md §4) —
    same function, so they can never drift apart.
    """
    return {"summary": scheduled_jobs.build_management_summary(db)}
