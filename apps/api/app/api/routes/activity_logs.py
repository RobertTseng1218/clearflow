from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.services.activity_log_service import format_activity_message

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


@router.get("")
def list_activity_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    stmt = (
        select(ActivityLog)
        .where(ActivityLog.owner_type == "user", ActivityLog.owner_id == current_user.id)
        .order_by(ActivityLog.created_at.desc())
    )
    items = list(db.scalars(stmt.offset((page - 1) * limit).limit(limit)))
    total = len(list(db.scalars(select(ActivityLog).where(ActivityLog.owner_type == "user", ActivityLog.owner_id == current_user.id))))
    return success_response(
        {
            "items": [
                {
                    "id": item.id,
                    "event_type": item.event_type,
                    "event_source": item.event_source,
                    "message": format_activity_message(
                        event_type=item.event_type,
                        event_source=item.event_source,
                        message=item.message,
                        meta_json=item.meta_json,
                    ),
                    "related_entity_type": item.related_entity_type,
                    "related_entity_id": item.related_entity_id,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        },
        meta={"page": page, "limit": limit, "total": total},
    )
