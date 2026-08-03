from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas.rules import RulesResponse
from app.services import rules_service

router = APIRouter()


@router.get("", response_model=RulesResponse, dependencies=[Depends(get_current_user)])
def get_rules() -> dict:
    return {"content": rules_service.get_rules_text()}
