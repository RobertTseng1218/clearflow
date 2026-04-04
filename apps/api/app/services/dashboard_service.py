from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.source_data import SummaryItem, Task
from app.services.plan_service import get_usage_payload
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


def _clean_text(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h\d|ul|ol)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split())


def _short_text(value: str | None, limit: int = 120) -> str:
    text = _clean_text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _serialize_dt(value) -> str | None:
    value = _normalize_dt(value)
    return value.isoformat() if value else None


def _task_source_type(task: Task) -> str | None:
    return (task.meta_json or {}).get("related_source_type") or task.source


def _task_source_label(task: Task) -> str:
    source_type = _task_source_type(task)
    return (task.meta_json or {}).get("source_label") or _source_label(source_type)


def _task_sort_key(task: Task) -> tuple:
    priority_rank = 0 if task.priority == "high" else 1 if task.priority == "medium" else 2
    due_at = _normalize_dt(task.due_at)
    due_rank = due_at.isoformat() if due_at else "9999-12-31T23:59:59+00:00"
    created_rank = _serialize_dt(task.created_at) or "9999-12-31T23:59:59+00:00"
    title_rank = task.title or ""
    return (priority_rank, due_rank, created_rank, title_rank)


def _task_focus_description(task: Task) -> str:
    meta = task.meta_json or {}
    hint = meta.get("display_hint")
    description = _short_text(task.description, 100)

    if task.priority == "high":
        prefix = "這是目前最需要先處理的待辦。"
    elif task.priority == "medium":
        prefix = "建議今天先處理這一項。"
    else:
        prefix = "這是目前最值得先看的待辦。"

    parts = [prefix]
    if isinstance(hint, str) and hint.strip():
        parts.append(hint.strip())
    elif _task_source_type(task) == "calendar_event":
        parts.append(_format_calendar_hint(task).rstrip("。"))

    if description:
        parts.append(description)

    return _short_text(" ".join(part for part in parts if part), 120)


def _build_task_highlight(task: Task) -> dict:
    return {
        "title": task.title,
        "description": _task_focus_description(task),
        "priority_score": 1000.0 if task.priority == "high" else 900.0 if task.priority == "medium" else 800.0,
        "related_type": "task",
        "related_id": task.id,
        "source_type": _task_source_type(task),
        "source_label": _task_source_label(task),
        "display_label": "今日優先待辦",
        "task_kind": (task.meta_json or {}).get("task_kind"),
        "due_at": _serialize_dt(task.due_at),
        "status": task.status,
        "priority": task.priority,
    }


def _summary_item_payload(item: SummaryItem, description_limit: int = 110) -> dict:
    return {
        "title": item.title,
        "description": _short_text(item.description, description_limit),
        "priority_score": float(item.priority_score or 0),
        "related_type": item.item_type,
        "related_id": item.related_source_item_id,
        "source_type": (item.meta_json or {}).get("source_type"),
        "source_label": (item.meta_json or {}).get("source_label")
        or _source_label((item.meta_json or {}).get("source_type")),
        "display_label": (item.meta_json or {}).get("display_label"),
    }

def _highlight_identity_from_task(task: Task) -> str:
    meta = task.meta_json or {}
    source_type = _task_source_type(task) or "unknown"
    related_source_item_id = meta.get("related_source_item_id") or meta.get("source_item_id")
    if related_source_item_id:
        return f"{source_type}:{related_source_item_id}"

    title = _clean_text(task.title).lower()
    return f"{source_type}:title:{title}"


def _highlight_identity_from_summary_item(item: SummaryItem) -> str:
    meta = item.meta_json or {}
    source_type = meta.get("source_type") or "unknown"
    related_source_item_id = item.related_source_item_id
    if related_source_item_id:
        return f"{source_type}:{related_source_item_id}"

    title = _clean_text(item.title).lower()
    return f"{source_type}:title:{title}"



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

    now = datetime.now(timezone.utc)
    if due_at < now:
        return "這個行程已經結束，可視情況歸檔。"
    if due_at.date() == now.date():
        return f"今天 {due_at.strftime('%H:%M')} 開始。"
    if due_at.date() == (now + timedelta(days=1)).date():
        return f"明天 {due_at.strftime('%H:%M')} 開始。"
    return f"{due_at.strftime('%m/%d %H:%M')} 開始。"


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
                    "trigger_at": due_at.isoformat(),
                    "status": "pending",
                    "source_type": source_type,
                    "source_label": (task.meta_json or {}).get("source_label")
                    or _source_label(source_type),
                }
            )

    items.sort(key=lambda item: item.get("trigger_at") or "")
    return items[:5]


def _source_overview_payload(source_breakdown: dict) -> dict:
    labels = []
    if source_breakdown.get("email"):
        labels.append("Gmail")
    if source_breakdown.get("calendar_event"):
        labels.append("Google Calendar")

    return {
        "email_count": source_breakdown.get("email", 0),
        "calendar_count": source_breakdown.get("calendar_event", 0),
        "active_sources": len(labels),
        "today_data_sources_count": len(labels),
        "today_data_source_labels": labels,
    }


def _normalize_activity_message(activity: ActivityLog) -> str:
    message = (activity.message or "").strip()
    if activity.event_type == "user_login":
        return "已透過 Google 完成登入。"

    if not message:
        return "已記錄一筆新的活動。"

    lower = message.lower()
    if "logged in via google oauth" in lower:
        return "已透過 Google 完成登入。"

    if "daily summary generated" in lower:
        return "已完成今日摘要整理。"

    if "task extraction completed" in lower:
        return "已完成待辦整理。"

    return message


def get_dashboard_payload(db: Session, user_id: str) -> dict:
    summary = generate_daily_summary(db, user_id, log_activity=False)
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
            .where(ActivityLog.owner_type == "user", ActivityLog.owner_id == user_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(20)
        )
    )

    email_highlights = [
        item
        for item in summary_items
        if (item.meta_json or {}).get("source_type") == "email"
        and _item_signal(item) == "actionable"
    ][:4]

    event_highlights = [
        item
        for item in summary_items
        if (item.meta_json or {}).get("source_type") == "calendar_event"
        and _is_future_calendar_item(item)
    ][:4]

    open_tasks = [
        task for task in tasks if task.status in {"open", "in_progress"}
    ]

    focus_tasks = sorted(open_tasks, key=_task_sort_key)[:5]

    due_soon_count = sum(
        1 for task in open_tasks if task.due_at is not None
    )

    meta = summary.meta_json or {}
    source_breakdown = meta.get("source_breakdown", {})
    signal_breakdown = meta.get("signal_breakdown", {})
    filtered_counts = meta.get("filtered_counts", {})
    filtered_items = meta.get("filtered_items", [])

    summary_identity_seen: set[str] = set()
    summary_highlights = []
    for item in summary_items:
        source_type = (item.meta_json or {}).get("source_type")
        signal = _item_signal(item)

        if source_type == "email" and signal != "actionable":
            continue
        if source_type == "calendar_event" and not _is_future_calendar_item(item):
            continue

        identity = _highlight_identity_from_summary_item(item)
        if identity in summary_identity_seen:
            continue

        summary_identity_seen.add(identity)
        summary_highlights.append(_summary_item_payload(item, 110))
        if len(summary_highlights) >= 4:
            break

    today_highlights: list[dict] = []
    task_identity = None
    task_title_identity = None
    if focus_tasks:
        primary_task = focus_tasks[0]
        today_highlights.append(_build_task_highlight(primary_task))
        task_identity = _highlight_identity_from_task(primary_task)
        task_title_identity = f"{_task_source_type(primary_task) or 'unknown'}:title:{_clean_text(primary_task.title).lower()}"

    if task_identity or task_title_identity:
        filtered_summary_highlights = []
        for item in summary_highlights:
            item_source_type = item.get('source_type') or 'unknown'
            item_identity = (
                f"{item_source_type}:{item.get('related_id')}"
                if item.get('related_id')
                else f"{item_source_type}:title:{_clean_text(item.get('title')).lower()}"
            )
            item_title_identity = f"{item_source_type}:title:{_clean_text(item.get('title')).lower()}"

            if task_identity and item_identity == task_identity:
                continue
            if task_title_identity and item_title_identity == task_title_identity:
                continue

            filtered_summary_highlights.append(item)

        summary_highlights = filtered_summary_highlights

    remaining_slots = 3 - len(today_highlights)
    if remaining_slots > 0:
        today_highlights.extend(summary_highlights[:remaining_slots])

    return {
        "today_highlights": today_highlights,
        "email_highlights": [
            _summary_item_payload(item, 130)
            for item in email_highlights
        ],
        "event_highlights": [
            _summary_item_payload(item, 120)
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
                    "due_at": task.due_at.isoformat() if task.due_at else None,
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
                    "message": _normalize_activity_message(item),
                    "created_at": item.created_at.isoformat(),
                }
                for item in recent_activities
            ]
        },
        "source_overview": _source_overview_payload(source_breakdown),
        "usage_preview": get_usage_payload(db, user_id),
    }
