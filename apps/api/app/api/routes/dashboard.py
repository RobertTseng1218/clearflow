from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.integration import Integration
from app.models.user import User
from app.services.dashboard_service import get_dashboard_payload

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _build_connection_status(db: Session, user_id: str, payload: dict) -> dict:
    active_integrations_count = db.scalar(
        select(func.count()).select_from(Integration).where(
            Integration.user_id == user_id,
            Integration.status == "connected",
        )
    ) or 0

    has_historical_data = any(
        [
            bool(payload.get("today_highlights")),
            bool(payload.get("daily_summary_preview", {}).get("summary_id")) if payload.get("daily_summary_preview") else False,
            bool(payload.get("task_preview", {}).get("items")) if payload.get("task_preview") else False,
            bool(payload.get("recent_activity_preview", {}).get("items")) if payload.get("recent_activity_preview") else False,
        ]
    )

    notice = None
    if active_integrations_count == 0 and has_historical_data:
        notice = "你目前已移除所有來源，畫面上顯示的是先前保留的歷史整理結果，後續將不再自動更新。"

    return {
        "active_integrations_count": int(active_integrations_count),
        "has_active_integrations": int(active_integrations_count) > 0,
        "has_historical_data": has_historical_data,
        "notice": notice,
    }


@router.get("")
def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    payload = get_dashboard_payload(db, current_user.id)
    payload["connection_status"] = _build_connection_status(db, current_user.id, payload)
    return success_response(payload)
