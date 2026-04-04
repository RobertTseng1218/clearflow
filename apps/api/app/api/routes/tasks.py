from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.source_data import SourceItem, Task, TaskSource
from app.models.user import User
from app.services.activity_log_service import ActivityEvent, log_event
from app.services.task_service import extract_tasks_for_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

VALID_STATUSES = {"open", "in_progress", "done", "snoozed", "archived"}
VALID_PRIORITIES = {"low", "medium", "high"}

PRIORITY_ORDER = case(
    (Task.priority == "high", 3),
    (Task.priority == "medium", 2),
    (Task.priority == "low", 1),
    else_=0,
)


def _task_status_label(status_value: str | None) -> str:
    return {
        "open": "進行中",
        "in_progress": "處理中",
        "done": "已完成",
        "snoozed": "稍後處理",
        "archived": "已封存",
    }.get(status_value or "", "未知狀態")


def _task_priority_label(priority_value: str | None) -> str:
    return {
        "high": "高優先",
        "medium": "中優先",
        "low": "低優先",
    }.get(priority_value or "", "未設定優先級")


def _task_payload(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "status_display": _task_status_label(task.status),
        "priority": task.priority,
        "priority_display": _task_priority_label(task.priority),
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "source": task.source,
        "source_type": (task.meta_json or {}).get("related_source_type") or task.source,
        "source_label": (task.meta_json or {}).get("source_label"),
        "task_kind": (task.meta_json or {}).get("task_kind"),
        "email_signal": (task.meta_json or {}).get("email_signal"),
        "created_by_type": task.created_by_type,
    }


def _status_change_message(task: Task, previous_status: str | None, next_status: str | None) -> str:
    title = task.title or "這筆待辦"

    if previous_status == next_status:
        return f"已更新待辦「{title}」。"
    if next_status == "done":
        return f"已將待辦「{title}」標記為完成。"
    if next_status == "snoozed":
        return f"已將待辦「{title}」改為稍後處理。"
    if next_status == "archived":
        return f"已將待辦「{title}」封存。"
    if next_status == "open":
        return f"已將待辦「{title}」恢復為進行中。"
    if next_status == "in_progress":
        return f"已將待辦「{title}」改為處理中。"
    return f"已更新待辦「{title}」的狀態。"


@router.get("")
def list_tasks(
    task_status: str | None = Query(default="active", alias="status"),
    priority: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    extract_tasks_for_user(db, current_user.id)

    query = select(Task).where(
        Task.owner_type == "user",
        Task.owner_id == current_user.id,
    )

    if task_status in (None, "", "active"):
        query = query.where(Task.status.in_(("open", "in_progress")))
    elif task_status != "all":
        if task_status not in VALID_STATUSES:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "待辦狀態格式不正確。",
                },
            )
        query = query.where(Task.status == task_status)

    if priority:
        if priority not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "待辦優先級格式不正確。",
                },
            )
        query = query.where(Task.priority == priority)

    query = query.order_by(
        PRIORITY_ORDER.desc(),
        Task.due_at.asc().nullslast(),
        Task.created_at.desc(),
    )

    items = list(db.scalars(query.offset((page - 1) * limit).limit(limit)))
    total = len(list(db.scalars(query)))

    return success_response(
        {"items": [_task_payload(task) for task in items]},
        meta={"page": page, "limit": limit, "total": total, "applied_status": task_status or "active"},
    )


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.owner_type == "user",
            Task.owner_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "找不到這筆待辦事項。"},
        )

    relations = list(db.scalars(select(TaskSource).where(TaskSource.task_id == task.id)))
    related_sources = []

    for rel in relations:
        source_item = db.get(SourceItem, rel.source_item_id)
        if source_item:
            related_sources.append(
                {
                    "source_item_id": source_item.id,
                    "source_type": source_item.source_type,
                    "title": source_item.title,
                }
            )

    payload = _task_payload(task)
    payload["related_sources"] = related_sources
    return success_response(payload)


@router.patch("/{task_id}")
def patch_task(
    task_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.owner_type == "user",
            Task.owner_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "找不到這筆待辦事項。"},
        )

    previous_status = task.status
    previous_priority = task.priority

    if "status" in payload:
        if payload["status"] not in VALID_STATUSES:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "待辦狀態格式不正確。",
                },
            )
        task.status = payload["status"]

    if "priority" in payload:
        if payload["priority"] not in VALID_PRIORITIES:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "待辦優先級格式不正確。",
                },
            )
        task.priority = payload["priority"]

    db.add(task)

    message = None
    if previous_status != task.status:
        message = _status_change_message(task, previous_status, task.status)
        log_event(
            db,
            owner_type="user",
            owner_id=current_user.id,
            event_type=ActivityEvent.TASK_STATUS_CHANGED,
            event_source="tasks_api",
            message=message,
            related_entity_type="task",
            related_entity_id=task.id,
            meta_json={
                "previous_status": previous_status,
                "next_status": task.status,
            },
        )
    elif previous_priority != task.priority:
        message = f"已更新待辦「{task.title or '這筆待辦'}」的優先級。"
        log_event(
            db,
            owner_type="user",
            owner_id=current_user.id,
            event_type=ActivityEvent.TASK_PRIORITY_CHANGED,
            event_source="tasks_api",
            message=message,
            related_entity_type="task",
            related_entity_id=task.id,
            meta_json={
                "previous_priority": previous_priority,
                "next_priority": task.priority,
            },
        )

    db.commit()
    db.refresh(task)

    return success_response(
        {
            "updated": True,
            "message": message,
            "task": _task_payload(task),
        }
    )
