from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


class ActivityEvent:
    USER_LOGIN = "user_login"
    INTEGRATION_CONNECTED = "integration_connected"
    INTEGRATION_SYNC_STARTED = "integration_sync_started"
    INTEGRATION_SYNC_COMPLETED = "integration_sync_completed"
    INTEGRATION_SYNC_FAILED = "integration_sync_failed"
    SUMMARY_GENERATED = "summary_generated"
    TASK_CREATED = "task_created"
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_PRIORITY_CHANGED = "task_priority_changed"


_TASK_EXTRACTION_RE = re.compile(
    r"task\s+extraction\s+completed\s+with\s+(\d+)\s+active\s+tasks?\.?",
    re.IGNORECASE,
)


def _provider_display_name(event_source: str | None) -> str:
    return {
        "gmail": "Gmail",
        "gcal": "Google Calendar",
        "google": "Google",
        "summary_engine": "摘要整理",
        "task_extractor": "待辦整理",
    }.get(event_source or "", event_source or "系統")


def _format_sync_completed_message(event_source: str | None, meta_json: dict[str, Any]) -> str:
    provider_name = _provider_display_name(event_source)
    fetched_count = meta_json.get("fetched_count")
    created_count = meta_json.get("created_count")
    updated_count = meta_json.get("updated_count")
    unchanged_count = meta_json.get("unchanged_count")

    if not any(
        isinstance(value, int)
        for value in [fetched_count, created_count, updated_count, unchanged_count]
    ):
        return f"{provider_name} 已完成同步。"

    fetched_count = int(fetched_count or 0)
    created_count = int(created_count or 0)
    updated_count = int(updated_count or 0)
    unchanged_count = int(unchanged_count or 0)
    changed_count = created_count + updated_count

    if fetched_count == 0:
        return f"{provider_name} 已完成同步，本次沒有抓到可更新的資料。"

    if changed_count == 0:
        return f"{provider_name} 已完成同步，本次檢查 {fetched_count} 筆資料，沒有新的重點變化。"

    parts: list[str] = []
    if created_count > 0:
        parts.append(f"新增 {created_count}")
    if updated_count > 0:
        parts.append(f"更新 {updated_count}")
    if unchanged_count > 0:
        parts.append(f"略過 {unchanged_count}")

    return f"{provider_name} 同步完成，本次檢查 {fetched_count} 筆資料，" + "、".join(parts) + "。"


def _format_task_extraction_message(meta_json: dict[str, Any]) -> str:
    task_count = meta_json.get("task_count")
    if isinstance(task_count, int):
        return f"已完成待辦整理，目前保留 {task_count} 個有效待辦。"
    return "已完成待辦整理。"


def _convert_legacy_message(
    raw_message: str,
    *,
    event_type: str,
    event_source: str | None,
    meta_json: dict[str, Any],
) -> str | None:
    match = _TASK_EXTRACTION_RE.fullmatch(raw_message.strip())
    if match:
        task_count = int(match.group(1))
        return f"已完成待辦整理，目前保留 {task_count} 個有效待辦。"

    normalized = raw_message.strip().lower()
    if normalized in {"task extraction completed.", "tasks extracted."}:
        return _format_task_extraction_message(meta_json)

    if normalized in {"summary generated.", "daily summary generated."}:
        return "已完成今日摘要整理。"

    if normalized in {"sync started.", "integration sync started."}:
        return f"{_provider_display_name(event_source)} 開始同步。"

    if normalized in {"sync completed.", "integration sync completed."}:
        return _format_sync_completed_message(event_source, meta_json)

    if normalized in {"sync failed.", "integration sync failed."}:
        return f"{_provider_display_name(event_source)} 同步失敗，請稍後再試。"

    return None


def format_activity_message(
    *,
    event_type: str,
    event_source: str | None = None,
    message: str | None = None,
    meta_json: dict | None = None,
) -> str:
    """Return the user-facing activity log message in Traditional Chinese.

    Round 4.0 keeps the backend as the single source of truth for activity wording.
    Existing legacy English messages are translated here when they are read again,
    while newly created logs are also normalized before they are stored.
    """
    meta = meta_json or {}
    raw_message = (message or "").strip()

    if raw_message:
        converted = _convert_legacy_message(
            raw_message,
            event_type=event_type,
            event_source=event_source,
            meta_json=meta,
        )
        return converted or raw_message

    if event_type == ActivityEvent.USER_LOGIN:
        return "已透過 Google 完成登入。"
    if event_type == ActivityEvent.INTEGRATION_CONNECTED:
        return f"{_provider_display_name(event_source)} 已成功連接。"
    if event_type == ActivityEvent.INTEGRATION_SYNC_STARTED:
        return f"{_provider_display_name(event_source)} 開始同步。"
    if event_type == ActivityEvent.INTEGRATION_SYNC_COMPLETED:
        return _format_sync_completed_message(event_source, meta)
    if event_type == ActivityEvent.INTEGRATION_SYNC_FAILED:
        return f"{_provider_display_name(event_source)} 同步失敗，請稍後再試。"
    if event_type == ActivityEvent.SUMMARY_GENERATED:
        return "已完成今日摘要整理。"
    if event_type == ActivityEvent.TASK_CREATED:
        return _format_task_extraction_message(meta)
    if event_type == ActivityEvent.TASK_STATUS_CHANGED:
        return "已更新待辦狀態。"
    if event_type == ActivityEvent.TASK_PRIORITY_CHANGED:
        return "已更新待辦優先順序。"

    return "已完成一項系統活動。"


def log_event(
    db: Session,
    *,
    owner_type: str,
    owner_id: str,
    event_type: str,
    event_source: str | None = None,
    message: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    meta_json: dict | None = None,
) -> ActivityLog:
    normalized_meta = meta_json or {}
    event = ActivityLog(
        owner_type=owner_type,
        owner_id=owner_id,
        event_type=event_type,
        event_source=event_source,
        message=format_activity_message(
            event_type=event_type,
            event_source=event_source,
            message=message,
            meta_json=normalized_meta,
        ),
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        meta_json=normalized_meta,
    )
    db.add(event)
    return event
