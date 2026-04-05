from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.source_data import SummaryItem, Task
from app.services.plan_service import get_usage_payload
from app.services.activity_log_service import ActivityEvent
from app.services.summary_service import generate_daily_summary
from app.services.task_service import extract_tasks_for_user


def _normalize_dt(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _source_label(source_type: str | None) -> str:
    return {
        "email": "Gmail",
        "calendar_event": "Google Calendar",
    }.get(source_type or "", source_type or "未知來源")

def _serialize_dt(value):
    value = _normalize_dt(value)
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _to_taipei(value: datetime | None) -> datetime | None:
    value = _normalize_dt(value)
    if value is None:
        return None
    return value.astimezone(timezone(timedelta(hours=8)))


def _short_text(value: str | None, limit: int = 120) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"




def _highlight_identity_from_summary_item(item: SummaryItem) -> str:
    meta = item.meta_json or {}
    source_type = meta.get("source_type") or item.item_type or "unknown"

    if source_type == "email":
        thread_id = meta.get("thread_id") or meta.get("gmail_thread_id") or meta.get("dedupe_identity")
        if thread_id:
            return f"email-thread:{thread_id}"
        title = _short_text(item.title, 120)
        description = _short_text(item.description, 160)
        return f"email-fallback:{title}|{description}"

    if source_type == "calendar_event":
        related_id = item.related_source_item_id or meta.get("source_item_id")
        if related_id:
            return f"calendar:{related_id}"
        title = _short_text(item.title, 120)
        display_label = meta.get("display_label") or ""
        return f"calendar-fallback:{title}|{display_label}"

    related_id = item.related_source_item_id or item.id
    return f"{source_type}:{related_id}"

def _dedupe_summary_items(items: list[SummaryItem]) -> list[SummaryItem]:
    deduped: list[SummaryItem] = []
    seen: set[str] = set()
    for item in items:
        identity = _highlight_identity_from_summary_item(item)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(item)
    return deduped


def _item_signal(item: SummaryItem) -> str:
    meta = item.meta_json or {}
    return meta.get("source_category") or ""


def _is_future_calendar_item(item: SummaryItem) -> bool:
    meta = item.meta_json or {}
    if meta.get("source_type") != "calendar_event":
        return True
    display_label = meta.get("display_label")
    return display_label in {"今日行程", "明日行程", "近期行程"}


def _format_calendar_hint(task: Task) -> str:
    due_at = _normalize_dt(task.due_at)
    if due_at is None:
        return "近期請留意這項行程。"

    now = _to_taipei(datetime.now(timezone.utc))
    due_local = _to_taipei(due_at)
    if now is None or due_local is None:
        return "近期請留意這項行程。"
    if due_local < now:
        return "這個行程已經結束，可視情況歸檔。"
    if due_local.date() == now.date():
        return f"今天 {due_local.strftime('%H:%M')} 開始。"
    if due_local.date() == (now + timedelta(days=1)).date():
        return f"明天 {due_local.strftime('%H:%M')} 開始。"
    return f"{due_local.strftime('%m/%d %H:%M')} 開始。"


def _reminder_preview_from_tasks(tasks: list[Task]) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=1)
    items = []

    for task in tasks:
        if task.status not in {"open", "in_progress"}:
            continue

        source_type = (task.meta_json or {}).get("related_source_type") or task.source
        if source_type != "calendar_event":
            continue

        due_at = _normalize_dt(task.due_at)
        if due_at and now <= due_at <= cutoff:
            items.append(
                {
                    "id": task.id,
                    "reminder_type": "due_soon",
                    "title": task.title,
                    "message": _format_calendar_hint(task),
                    "trigger_at": _serialize_dt(due_at),
                    "status": "pending",
                    "source_type": source_type,
                    "source_label": (task.meta_json or {}).get("source_label")
                    or _source_label(source_type),
                }
            )

    items.sort(key=lambda item: item.get("trigger_at") or "")
    return items[:5]


def get_dashboard_payload(db: Session, user_id: str) -> dict:
    summary = generate_daily_summary(db, user_id)
    extract_tasks_for_user(db, user_id)

    summary_items = list(
        db.scalars(
            select(SummaryItem)
            .where(SummaryItem.summary_id == summary.id)
            .order_by(SummaryItem.priority_score.desc().nullslast())
        )
    )

    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.owner_type == "user", Task.owner_id == user_id)
            .order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc())
        )
    )

    recent_activities = list(
        db.scalars(
            select(ActivityLog)
            .where(
                ActivityLog.owner_type == "user",
                ActivityLog.owner_id == user_id,
                ActivityLog.event_type != ActivityEvent.INTEGRATION_SYNC_STARTED,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(8)
        )
    )

    email_highlights = _dedupe_summary_items([
        item
        for item in summary_items
        if (item.meta_json or {}).get("source_type") == "email"
        and _item_signal(item) == "actionable"
    ])[:4]

    event_highlights = _dedupe_summary_items([
        item
        for item in summary_items
        if (item.meta_json or {}).get("source_type") == "calendar_event"
        and _is_future_calendar_item(item)
    ])[:4]

    open_tasks = [
        task for task in tasks if task.status in {"open", "in_progress"}
    ]

    focus_tasks = sorted(
        open_tasks,
        key=lambda task: (
            0 if task.priority == "high" else 1 if task.priority == "medium" else 2,
            _normalize_dt(task.due_at).isoformat()
            if _normalize_dt(task.due_at)
            else "9999",
        ),
    )[:5]

    due_soon_count = sum(
        1 for task in open_tasks if task.due_at is not None
    )

    meta = summary.meta_json or {}
    source_breakdown = meta.get("source_breakdown", {})
    signal_breakdown = meta.get("signal_breakdown", {})
    filtered_counts = meta.get("filtered_counts", {})
    filtered_items = meta.get("filtered_items", [])

    top_highlights = []
    seen_top_identities: set[str] = set()
    for item in summary_items:
        source_type = (item.meta_json or {}).get("source_type")
        signal = _item_signal(item)

        if source_type == "email" and signal != "actionable":
            continue
        if source_type == "calendar_event" and not _is_future_calendar_item(item):
            continue

        identity = _highlight_identity_from_summary_item(item)
        if identity in seen_top_identities:
            continue
        seen_top_identities.add(identity)
        top_highlights.append(item)
        if len(top_highlights) >= 3:
            break

    return {
        "today_highlights": [
            {
                "title": item.title,
                "description": _short_text(item.description, 110),
                "priority_score": float(item.priority_score or 0),
                "related_type": item.item_type,
                "related_id": item.related_source_item_id,
                "source_type": (item.meta_json or {}).get("source_type"),
                "source_label": (item.meta_json or {}).get("source_label")
                or _source_label((item.meta_json or {}).get("source_type")),
                "display_label": (item.meta_json or {}).get("display_label"),
            }
            for item in top_highlights
        ],
        "email_highlights": [
            {
                "title": item.title,
                "description": _short_text(item.description, 130),
                "priority_score": float(item.priority_score or 0),
                "related_type": item.item_type,
                "related_id": item.related_source_item_id,
                "source_type": (item.meta_json or {}).get("source_type"),
                "source_label": (item.meta_json or {}).get("source_label")
                or _source_label((item.meta_json or {}).get("source_type")),
                "display_label": (item.meta_json or {}).get("display_label"),
            }
            for item in email_highlights
        ],
        "event_highlights": [
            {
                "title": item.title,
                "description": _short_text(item.description, 120),
                "priority_score": float(item.priority_score or 0),
                "related_type": item.item_type,
                "related_id": item.related_source_item_id,
                "source_type": (item.meta_json or {}).get("source_type"),
                "source_label": (item.meta_json or {}).get("source_label")
                or _source_label((item.meta_json or {}).get("source_type")),
                "display_label": (item.meta_json or {}).get("display_label"),
            }
            for item in event_highlights
        ],
        "daily_summary_preview": {
            "summary_id": summary.id,
            "summary_date": summary.summary_date.isoformat(),
            "summary_text_preview": _short_text(summary.summary_text, 180),
            "source_breakdown": source_breakdown,
            "signal_breakdown": signal_breakdown,
            "filtered_counts": filtered_counts,
            "filtered_items": filtered_items,
        },
        "task_preview": {
            "open_count": len(open_tasks),
            "due_soon_count": due_soon_count,
            "items": [
                {
                    "id": task.id,
                    "title": task.title,
                    "description": _short_text(task.description, 120),
                    "priority": task.priority,
                    "due_at": _serialize_dt(task.due_at),
                    "status": task.status,
                    "source": task.source,
                    "source_label": (task.meta_json or {}).get("source_label")
                    or _source_label(task.source),
                    "source_type": (task.meta_json or {}).get("related_source_type")
                    or task.source,
                    "task_kind": (task.meta_json or {}).get("task_kind"),
                    "display_hint": (
                        _format_calendar_hint(task)
                        if ((task.meta_json or {}).get("related_source_type") or task.source)
                        == "calendar_event"
                        else None
                    ),
                }
                for task in focus_tasks
            ],
        },
        "reminder_preview": {
            "items": _reminder_preview_from_tasks(open_tasks),
        },
        "recent_activity_preview": {
            "items": [
                {
                    "id": item.id,
                    "event_type": item.event_type,
                    "message": item.message,
                    "created_at": _serialize_dt(item.created_at),
                }
                for item in recent_activities
            ]
        },
        "source_overview": {
            "email_count": source_breakdown.get("email", 0),
            "calendar_count": source_breakdown.get("calendar_event", 0),
            "active_sources": sum(1 for value in source_breakdown.values() if value),
        },
        "usage_preview": get_usage_payload(db, user_id),
    }
