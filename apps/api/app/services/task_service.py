from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.source_data import SourceItem, Task, TaskSource
from app.services.activity_log_service import ActivityEvent, log_event

ACTION_KEYWORDS = [
    "請回覆",
    "請確認",
    "請處理",
    "請於今日",
    "請於今天",
    "請盡快",
    "回覆",
    "確認",
    "處理",
    "回傳",
    "補件",
    "核准",
    "簽核",
    "deadline",
    "due",
    "follow up",
    "follow-up",
    "reply",
    "action required",
    "verify",
    "approve",
]

PROMOTIONAL_KEYWORDS = [
    "折扣",
    "優惠",
    "活動",
    "促銷",
    "會員日",
    "限定",
    "推薦",
    "精選",
    "領券",
    "點數",
    "折抵",
    "保費",
    "電子報",
    "vip",
    "coupon",
    "sale",
    "promo",
    "promotion",
    "discount",
    "newsletter",
]

LOW_SIGNAL_NOTIFICATION_KEYWORDS = [
    "已送達",
    "已寄達",
    "配送",
    "出貨",
    "發票",
    "扣繳",
    "信用卡",
    "刷卡",
    "帳單",
    "通知",
    "收據",
    "證明",
    "代收款",
    "成交回報",
    "receipt",
    "invoice",
    "statement",
    "payment received",
    "delivered",
    "shipment",
    "tracking",
]

NEWS_REFERENCE_KEYWORDS = [
    "新聞",
    "比分",
    "直播",
    "賽事",
    "開打",
    "經典賽",
    "wbc",
    "news",
    "sports",
    "highlight",
]

CALENDAR_MEETING_KEYWORDS = [
    "會議",
    "meeting",
    "sync",
    "討論",
    "review",
    "demo",
    "訪談",
]

CALENDAR_LOOKAHEAD_DAYS = 7
CALENDAR_ARCHIVE_AFTER_HOURS = 6


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _short_text(value: str | None, limit: int = 180) -> str:
    text = _clean_text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _format_month_day(dt: datetime) -> str:
    local_dt = dt.astimezone(timezone.utc)
    return f"{local_dt.month:02d}/{local_dt.day:02d}"


def _format_zh_time(dt: datetime) -> str:
    local_dt = dt.astimezone(timezone.utc)
    hour_label = "上午" if local_dt.hour < 12 else "下午"
    display_hour = local_dt.hour % 12 or 12
    return f"{hour_label}{display_hour:02d}:{local_dt.minute:02d}"


def _task_hash(source_item: SourceItem) -> str:
    source_dt = _normalize_dt(source_item.source_timestamp)
    raw = (
        f"{source_item.user_id}|"
        f"{source_item.source_type}|"
        f"{_clean_text(source_item.title)}|"
        f"{_clean_text((source_item.content_text or '')[:200])}|"
        f"{source_dt.isoformat() if source_dt else ''}"
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _source_label(source_type: str) -> str:
    return {
        "email": "Gmail",
        "calendar_event": "Google Calendar",
    }.get(source_type, source_type)


def _email_text(source_item: SourceItem) -> str:
    return f"{source_item.title or ''} {source_item.content_text or ''}".lower()


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def classify_email_signal(source_item: SourceItem) -> str:
    text = _email_text(source_item)

    if _contains_any(text, PROMOTIONAL_KEYWORDS):
        return "marketing"

    if _contains_any(text, LOW_SIGNAL_NOTIFICATION_KEYWORDS):
        return "notification"

    if _contains_any(text, NEWS_REFERENCE_KEYWORDS):
        return "reference"

    if _contains_any(text, ACTION_KEYWORDS):
        return "actionable"

    return "reference"


def _is_true_actionable_email(source_item: SourceItem) -> bool:
    text = _email_text(source_item)
    signal = classify_email_signal(source_item)

    if signal != "actionable":
        return False

    if _contains_any(text, PROMOTIONAL_KEYWORDS):
        return False
    if _contains_any(text, LOW_SIGNAL_NOTIFICATION_KEYWORDS):
        return False
    if _contains_any(text, NEWS_REFERENCE_KEYWORDS):
        return False

    return True


def _guess_priority(source_item: SourceItem) -> str:
    now = datetime.now(timezone.utc)
    source_dt = _normalize_dt(source_item.source_timestamp) or now

    if source_item.source_type == "calendar_event":
        title_text = f"{source_item.title or ''} {source_item.content_text or ''}".lower()

        if source_dt < now:
            return "low"

        if source_dt <= now + timedelta(hours=6):
            return "high"

        if any(keyword in title_text for keyword in CALENDAR_MEETING_KEYWORDS):
            return "high" if source_dt <= now + timedelta(days=1) else "medium"

        return "medium" if source_dt <= now + timedelta(days=1) else "low"

    if _is_true_actionable_email(source_item):
        return "high"

    signal = classify_email_signal(source_item)
    if signal in {"notification", "marketing", "reference"}:
        return "low"

    return "medium"


def _guess_due_at(source_item: SourceItem):
    base = _normalize_dt(source_item.source_timestamp) or datetime.now(timezone.utc)

    if source_item.source_type == "calendar_event":
        return base

    if _is_true_actionable_email(source_item):
        return base + timedelta(hours=8)

    return None


def _calendar_stage_label(source_item: SourceItem) -> str:
    now = datetime.now(timezone.utc)
    source_dt = _normalize_dt(source_item.source_timestamp) or now

    if source_dt < now:
        return "已過行程"
    if source_dt.date() == now.date():
        return "今日行程"
    if source_dt.date() == (now + timedelta(days=1)).date():
        return "明日行程"
    return "近期行程"


def _calendar_display_hint(source_item: SourceItem) -> str | None:
    source_dt = _normalize_dt(source_item.source_timestamp)
    if source_dt is None:
        return None

    stage_label = _calendar_stage_label(source_item)
    if stage_label == "今日行程":
        return f"今天 {_format_zh_time(source_dt)} 開始"
    if stage_label == "明日行程":
        return f"明天 {_format_zh_time(source_dt)} 開始"
    if stage_label == "近期行程":
        return f"{_format_month_day(source_dt)} {_format_zh_time(source_dt)} 開始"
    return f"{_format_month_day(source_dt)} {_format_zh_time(source_dt)}"


def _calendar_description(source_item: SourceItem) -> str:
    base_text = _short_text(source_item.content_text, 160)
    if base_text:
        return base_text

    hint = _calendar_display_hint(source_item)
    if hint:
        return f"{hint}。"

    return "未提供補充說明。"


def _task_description(source_item: SourceItem) -> str:
    if source_item.source_type == "calendar_event":
        return _calendar_description(source_item)
    return _short_text(source_item.content_text, 180) or "未提供補充說明。"


def _task_title(source_item: SourceItem) -> str:
    if source_item.source_type == "calendar_event":
        title = source_item.title or "未命名事件"
        lowered = title.lower()
        if any(keyword in lowered for keyword in CALENDAR_MEETING_KEYWORDS):
            return f"會議提醒：{title}"
        return f"行程：{title}"

    return source_item.title or "待處理事項"


def _task_kind(source_item: SourceItem) -> str:
    if source_item.source_type == "calendar_event":
        return "calendar_reminder"
    return "email_followup"


def _should_generate_task(source_item: SourceItem) -> bool:
    now = datetime.now(timezone.utc)

    if source_item.source_type == "calendar_event":
        source_dt = _normalize_dt(source_item.source_timestamp) or now
        return now <= source_dt <= now + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)

    return _is_true_actionable_email(source_item)


def _desired_status(source_item: SourceItem) -> str:
    if source_item.source_type != "calendar_event":
        return "open"

    now = datetime.now(timezone.utc)
    source_dt = _normalize_dt(source_item.source_timestamp) or now
    if source_dt < now - timedelta(hours=CALENDAR_ARCHIVE_AFTER_HOURS):
        return "archived"
    return "open"


def extract_tasks_for_user(db: Session, user_id: str) -> list[Task]:
    source_items = list(
        db.scalars(
            select(SourceItem)
            .where(SourceItem.user_id == user_id)
            .order_by(
                SourceItem.source_timestamp.desc().nullslast(),
                SourceItem.created_at.desc(),
            )
            .limit(80)
        )
    )

    existing_tasks = list(
        db.scalars(
            select(Task).where(
                Task.owner_type == "user",
                Task.owner_id == user_id,
            )
        )
    )

    existing_by_hash = {
        task.task_hash: task for task in existing_tasks if task.task_hash
    }

    existing_task_ids = [task.id for task in existing_tasks if task.id]
    existing_links: set[tuple[str, str]] = set()
    if existing_task_ids:
        existing_links = {
            (task_id, source_item_id)
            for task_id, source_item_id in db.execute(
                select(TaskSource.task_id, TaskSource.source_item_id).where(
                    TaskSource.task_id.in_(existing_task_ids)
                )
            )
        }

    touched_ids: set[str] = set()
    created_or_updated: list[Task] = []

    for source_item in source_items:
        if not _should_generate_task(source_item):
            continue

        task_hash = _task_hash(source_item)
        desired_status = _desired_status(source_item)
        task = existing_by_hash.get(task_hash)

        email_signal = (
            classify_email_signal(source_item)
            if source_item.source_type == "email"
            else None
        )

        source_dt = _normalize_dt(source_item.source_timestamp)
        meta_payload = {
            "related_source_type": source_item.source_type,
            "source_label": _source_label(source_item.source_type),
            "source_title": source_item.title,
            "task_kind": _task_kind(source_item),
            "email_signal": email_signal,
            "display_label": _calendar_stage_label(source_item)
            if source_item.source_type == "calendar_event"
            else None,
            "display_hint": _calendar_display_hint(source_item)
            if source_item.source_type == "calendar_event"
            else None,
            "source_timestamp": source_dt.isoformat() if source_dt else None,
        }

        if task is None:
            task = Task(
                owner_type="user",
                owner_id=user_id,
                title=_task_title(source_item),
                description=_task_description(source_item),
                status=desired_status,
                priority=_guess_priority(source_item),
                due_at=_guess_due_at(source_item),
                source=source_item.source_type,
                created_by_type="system",
                task_hash=task_hash,
                meta_json=meta_payload,
            )
            db.add(task)
            db.flush()
        else:
            task.title = _task_title(source_item)
            task.description = _task_description(source_item)
            task.priority = _guess_priority(source_item)
            task.due_at = _guess_due_at(source_item)
            task.source = source_item.source_type
            task.status = desired_status if task.status != "done" else task.status

            meta = dict(task.meta_json or {})
            meta.update(meta_payload)
            task.meta_json = meta

        touched_ids.add(task.id)
        created_or_updated.append(task)

        link_key = (task.id, source_item.id)
        if link_key not in existing_links:
            db.add(
                TaskSource(
                    task_id=task.id,
                    source_item_id=source_item.id,
                    relation_type="derived_from",
                )
            )
            existing_links.add(link_key)

    stale_tasks = [
        task
        for task in existing_tasks
        if task.id not in touched_ids and task.status in {"open", "in_progress"}
    ]
    for task in stale_tasks:
        task.status = "archived"

    db.commit()

    log_event(
        db,
        owner_type="user",
        owner_id=user_id,
        event_type=ActivityEvent.TASK_CREATED,
        event_source="task_extractor",
        message=f"Task extraction completed with {len(created_or_updated)} active tasks.",
        related_entity_type="task_batch",
        related_entity_id=None,
        meta_json={"task_count": len(created_or_updated)},
    )
    db.commit()
    return created_or_updated