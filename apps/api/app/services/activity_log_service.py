from __future__ import annotations

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
    event = ActivityLog(
        owner_type=owner_type,
        owner_id=owner_id,
        event_type=event_type,
        event_source=event_source,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        meta_json=meta_json or {},
    )
    db.add(event)
    return event
