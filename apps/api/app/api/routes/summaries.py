from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.integration import Integration
from app.models.source_data import Summary, SummaryItem
from app.models.user import User
from app.services.plan_service import get_usage_payload
from app.services.summary_service import generate_daily_summary

router = APIRouter(prefix="/summaries", tags=["summaries"])


def _history_threshold(days: int):
    return (datetime.now(timezone.utc) - timedelta(days=max(days, 1))).date()


def _build_connection_status(db: Session, user_id: str, has_historical_data: bool) -> dict:
    active_integrations_count = db.scalar(
        select(func.count()).select_from(Integration).where(
            Integration.user_id == user_id,
            Integration.status == "connected",
        )
    ) or 0
    notice = None
    if active_integrations_count == 0 and has_historical_data:
        notice = "你目前已移除所有來源，這裡顯示的是先前保留的歷史摘要，不會再自動更新。"
    return {
        "active_integrations_count": int(active_integrations_count),
        "has_active_integrations": int(active_integrations_count) > 0,
        "has_historical_data": has_historical_data,
        "notice": notice,
    }


def _get_existing_today_summary(db: Session, user_id: str, summary_type: str = 'daily') -> Summary | None:
    today = datetime.now(timezone.utc).date()
    return db.scalar(
        select(Summary)
        .where(
            Summary.user_id == user_id,
            Summary.summary_type == summary_type,
            Summary.summary_date == today,
        )
        .order_by(Summary.created_at.desc())
        .limit(1)
    )


@router.get("")
def list_summaries(
    type: str = Query(default="daily"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if type == "daily" and _get_existing_today_summary(db, current_user.id, type) is None:
        generate_daily_summary(db, current_user.id)

    usage = get_usage_payload(db, current_user.id)
    threshold = _history_threshold(usage["history_days_limit"])

    query = (
        select(Summary)
        .where(
            Summary.user_id == current_user.id,
            Summary.summary_type == type,
            Summary.summary_date >= threshold,
        )
        .order_by(Summary.summary_date.desc(), Summary.created_at.desc())
    )

    items = list(db.scalars(query.offset((page - 1) * limit).limit(limit)))
    total = len(list(db.scalars(query)))
    connection_status = _build_connection_status(db, current_user.id, len(items) > 0)

    return success_response(
        {
            "items": [
                {
                    "id": item.id,
                    "summary_type": item.summary_type,
                    "summary_date": item.summary_date.isoformat(),
                    "summary_text_preview": (item.summary_text or "")[:200],
                    "created_at": item.created_at.isoformat(),
                    "source_breakdown": (item.meta_json or {}).get("source_breakdown", {}),
                    "signal_breakdown": (item.meta_json or {}).get("signal_breakdown", {}),
                    "filtered_counts": (item.meta_json or {}).get("filtered_counts", {}),
                    "filtered_items": (item.meta_json or {}).get("filtered_items", []),
                }
                for item in items
            ],
            "connection_status": connection_status,
        },
        meta={"page": page, "limit": limit, "total": total},
    )


@router.get("/{summary_id}")
def get_summary(
    summary_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    summary = db.scalar(
        select(Summary).where(
            Summary.id == summary_id,
            Summary.user_id == current_user.id,
        )
    )
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SUMMARY_NOT_FOUND", "message": "找不到這筆摘要資料。"},
        )

    items = list(
        db.scalars(
            select(SummaryItem)
            .where(SummaryItem.summary_id == summary.id)
            .order_by(SummaryItem.priority_score.desc().nullslast())
        )
    )
    connection_status = _build_connection_status(db, current_user.id, True)

    return success_response(
        {
            "id": summary.id,
            "summary_type": summary.summary_type,
            "summary_date": summary.summary_date.isoformat(),
            "summary_text": summary.summary_text,
            "source_breakdown": (summary.meta_json or {}).get("source_breakdown", {}),
            "signal_breakdown": (summary.meta_json or {}).get("signal_breakdown", {}),
            "filtered_counts": (summary.meta_json or {}).get("filtered_counts", {}),
            "filtered_items": (summary.meta_json or {}).get("filtered_items", []),
            "items": [
                {
                    "id": item.id,
                    "item_type": item.item_type,
                    "title": item.title,
                    "description": item.description,
                    "priority_score": float(item.priority_score or 0),
                    "related_source_item_id": item.related_source_item_id,
                    "meta": item.meta_json,
                    "source_type": (item.meta_json or {}).get("source_type"),
                    "source_label": (item.meta_json or {}).get("source_label"),
                    "display_label": (item.meta_json or {}).get("display_label"),
                    "source_category": (item.meta_json or {}).get("source_category"),
                }
                for item in items
            ],
            "connection_status": connection_status,
        }
    )
