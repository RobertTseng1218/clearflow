from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.user import User
from app.services.plan_service import get_current_plan_payload, get_usage_payload

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return success_response(
        {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "avatar_url": current_user.avatar_url,
            "created_at": current_user.created_at.isoformat(),
        }
    )


@router.get("/plan")
def get_me_plan(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return success_response(get_current_plan_payload(db, current_user.id))


@router.get("/usage")
def get_me_usage(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    return success_response(get_usage_payload(db, current_user.id))
