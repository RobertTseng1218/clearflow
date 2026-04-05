from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from html import unescape
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.source_data import SourceItem, Summary, SummaryItem
from app.services.activity_log_service import ActivityEvent, log_event

PROMOTIONAL_KEYWORDS = [
    "折扣",
    "優惠",
    "活動",
    "促銷",
    "會員日",
    "推薦",
    "精選",
    "領券",
    "coupon",
    "sale",
    "promo",
    "discount",
    "newsletter",
    "電子報",
    "vip",
    "點數加碼",
    "限時優惠",
    "限時搶購",
    "滿額",
    "回饋",
]

STRONG_ACTION_PHRASES = [
    "請回覆",
    "請確認",
    "請補件",
    "請完成",
    "請簽核",
    "請審核",
    "請處理",
    "待回覆",
    "待補件",
    "待處理",
    "待確認",
    "action required",
    "reply required",
    "please reply",
    "please confirm",
    "please provide",
    "approval required",
    "verify your",
]

DEADLINE_HINT_KEYWORDS = [
    "deadline",
    "due",
    "today",
    "今天",
    "今日",
    "本日",
    "截止",
    "逾期",
    "最後期限",
]

LOW_SIGNAL_NOTIFICATION_KEYWORDS = [
    "已送達",
    "已寄達",
    "配送",
    "出貨",
    "已出貨",
    "已送出",
    "已完成",
    "已入帳",
    "已確認",
    "付款已確認",
    "登入成功",
    "登入成功通知",
    "發票",
    "扣繳",
    "信用卡",
    "刷卡",
    "帳單",
    "通知",
    "receipt",
    "invoice",
    "statement",
    "payment received",
    "delivered",
    "shipment",
    "tracking",
    "login success",
    "signed in",
]

CALENDAR_MEETING_KEYWORDS = [
    "會議",
    "meeting",
    "sync",
    "討論",
    "review",
    "demo",
    "訪談",
    "檢討",
    "kickoff",
]

FILTERED_ITEM_PREVIEW_LIMIT = 5


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_text(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h\d|ul|ol)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split())


def _short_text(value: str | None, limit: int = 160) -> str:
    text = _clean_text(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _source_label(source_type: str) -> str:
    return {
        "email": "Gmail",
        "calendar_event": "Google Calendar",
    }.get(source_type, source_type)


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _source_meta(source_item: SourceItem) -> dict:
    meta = getattr(source_item, "source_meta_json", None)
    return meta if isinstance(meta, dict) else {}


def _email_thread_id(source_item: SourceItem) -> str | None:
    if source_item.source_type != "email":
        return None
    thread_id = _source_meta(source_item).get("thread_id")
    if isinstance(thread_id, str) and thread_id.strip():
        return thread_id.strip()
    return None


def _email_fallback_key(source_item: SourceItem) -> str:
    title = _clean_text(source_item.title).lower()
    preview = _clean_text(source_item.content_text).lower()[:160]
    return f"{title}|{preview}"


def _source_item_identity(source_item: SourceItem) -> str:
    if source_item.source_type == "email":
        thread_id = _email_thread_id(source_item)
        if thread_id:
            return f"email:thread:{thread_id}"
        return f"email:fallback:{_email_fallback_key(source_item)}"

    if source_item.source_type == "calendar_event":
        source_dt = _normalize_dt(source_item.source_timestamp)
        return f"calendar_event:{_clean_text(source_item.title).lower()}|{source_dt.isoformat() if source_dt else ''}"

    return f"{source_item.source_type}:{getattr(source_item, 'id', '')}"


def _dedupe_source_items(items: Iterable[SourceItem]) -> list[SourceItem]:
    deduped: list[SourceItem] = []
    seen: set[str] = set()
    for item in items:
        identity = _source_item_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(item)
    return deduped


def classify_email_signal(source_item: SourceItem) -> str:
    title_text = _clean_text(source_item.title).lower()
    preview_text = _clean_text(source_item.content_text).lower()[:240]
    combined_text = f"{title_text} {preview_text}".strip()

    if _contains_any(combined_text, PROMOTIONAL_KEYWORDS):
        return "marketing"

    title_has_strong_action = _contains_any(title_text, STRONG_ACTION_PHRASES)
    preview_has_strong_action = _contains_any(preview_text, STRONG_ACTION_PHRASES)
    preview_has_deadline_hint = _contains_any(preview_text, DEADLINE_HINT_KEYWORDS)

    title_has_low_signal = _contains_any(title_text, LOW_SIGNAL_NOTIFICATION_KEYWORDS)
    preview_has_low_signal = _contains_any(preview_text, LOW_SIGNAL_NOTIFICATION_KEYWORDS)

    if title_has_low_signal and not title_has_strong_action:
        return "notification"

    if title_has_strong_action:
        return "actionable"

    if preview_has_strong_action and preview_has_deadline_hint and not title_has_low_signal:
        return "actionable"

    if preview_has_low_signal:
        return "notification"

    if preview_has_strong_action:
        return "reference"

    return "reference"


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


def _item_priority(source_item: SourceItem) -> float:
    score = 50.0
    now = datetime.now(timezone.utc)
    source_dt = _normalize_dt(source_item.source_timestamp) or now

    if source_item.source_type == "calendar_event":
        score += 10

        if source_dt <= now:
            score -= 20
        elif source_dt <= now + timedelta(hours=6):
            score += 25
        elif source_dt <= now + timedelta(days=1):
            score += 15
        elif source_dt <= now + timedelta(days=3):
            score += 8

        title_text = f"{source_item.title or ''} {source_item.content_text or ''}".lower()
        if any(keyword in title_text for keyword in CALENDAR_MEETING_KEYWORDS):
            score += 12

        return score

    signal = classify_email_signal(source_item)
    if signal == "actionable":
        score += 26
    elif signal == "notification":
        score += 2
    elif signal == "reference":
        score -= 4
    elif signal == "marketing":
        score -= 20

    title_text = (source_item.title or "").lower()
    preview_text = _clean_text(source_item.content_text).lower()[:240]

    if any(keyword in title_text for keyword in ["urgent", "important", "逾期", "截止", "異常"]):
        score += 10

    if any(keyword in preview_text for keyword in ["today", "deadline", "今天", "截止", "逾期", "異常"]):
        score += 8

    return score


def _source_item_to_summary_item(source_item: SourceItem) -> dict:
    source_identity = _source_item_identity(source_item)
    thread_id = _email_thread_id(source_item)

    if source_item.source_type == "calendar_event":
        item_type = "calendar"
        display_label = _calendar_stage_label(source_item)
        category = "calendar_focus"
    else:
        signal = classify_email_signal(source_item)
        item_type = "email"
        display_label = {
            "actionable": "郵件跟進",
            "notification": "通知郵件",
            "marketing": "行銷郵件",
            "reference": "一般郵件",
        }.get(signal, "一般郵件")
        category = signal

    return {
        "item_type": item_type,
        "title": source_item.title or "(untitled)",
        "description": _short_text(source_item.content_text, 180),
        "priority_score": _item_priority(source_item),
        "related_source_item_id": source_item.id,
        "meta_json": {
            "source_type": source_item.source_type,
            "source_label": _source_label(source_item.source_type),
            "display_label": display_label,
            "source_category": category,
            "thread_id": thread_id,
            "dedupe_identity": source_identity,
        },
    }


def _filtered_item_payload(source_item: SourceItem) -> dict:
    signal = classify_email_signal(source_item)
    return {
        "title": source_item.title or "(untitled)",
        "description": _short_text(source_item.content_text, 120),
        "source_type": source_item.source_type,
        "source_label": _source_label(source_item.source_type),
        "display_label": "通知郵件" if signal == "notification" else "行銷郵件",
        "source_category": signal,
        "thread_id": _email_thread_id(source_item),
        "dedupe_identity": _source_item_identity(source_item),
    }


def _build_summary_text(items: Iterable[SourceItem]) -> str:
    items = list(items)
    now = datetime.now(timezone.utc)

    email_items = _dedupe_source_items(item for item in items if item.source_type == "email")
    event_items = list(item for item in items if item.source_type == "calendar_event")

    actionable_emails = [item for item in email_items if classify_email_signal(item) == "actionable"]
    notification_emails = [item for item in email_items if classify_email_signal(item) == "notification"]
    marketing_emails = [item for item in email_items if classify_email_signal(item) == "marketing"]
    today_events = [
        item for item in event_items
        if (_normalize_dt(item.source_timestamp) or now).date() == now.date()
    ]

    parts: list[str] = []

    if today_events:
        titles = "、".join(item.title for item in today_events[:2] if item.title)
        parts.append(f"今天先留意 {len(today_events)} 個行程 / 會議{f'，像是：{titles}' if titles else ''}。")
    elif event_items:
        titles = "、".join(item.title for item in event_items[:2] if item.title)
        parts.append(f"接下來有 {len(event_items)} 個近期行程{f'，像是：{titles}' if titles else ''}。")

    if actionable_emails:
        titles = "、".join(item.title for item in actionable_emails[:2] if item.title)
        parts.append(f"郵件方面有 {len(actionable_emails)} 封建議先處理{f'，包含：{titles}' if titles else ''}。")
    elif notification_emails:
        parts.append(f"另外有 {len(notification_emails)} 封通知型郵件，可視情況稍後查看。")
    elif email_items:
        parts.append(f"今天同步到 {len(email_items)} 封一般郵件，目前沒有明顯需要立即出手的內容。")

    if marketing_emails:
        parts.append(f"其餘 {len(marketing_emails)} 封促銷型內容已先幫你壓低顯示。")

    if not parts:
        return "今天目前沒有偵測到重要項目。"

    return " ".join(parts)


def _should_include_summary_item(source_item: SourceItem) -> bool:
    if source_item.source_type == "calendar_event":
        source_dt = _normalize_dt(source_item.source_timestamp)
        return source_dt is None or source_dt >= datetime.now(timezone.utc)

    signal = classify_email_signal(source_item)
    return signal in {"actionable", "reference"}


def generate_daily_summary(
    db: Session,
    user_id: str,
    summary_date: date | None = None,
    *,
    log_activity: bool = True,
) -> Summary:
    summary_date = summary_date or datetime.now(timezone.utc).date()

    items = list(
        db.scalars(
            select(SourceItem)
            .where(SourceItem.user_id == user_id)
            .order_by(
                SourceItem.source_timestamp.desc().nullslast(),
                SourceItem.created_at.desc(),
            )
            .limit(28)
        )
    )

    summary = db.scalar(
        select(Summary).where(
            Summary.user_id == user_id,
            Summary.summary_type == "daily",
            Summary.summary_date == summary_date,
        )
    )

    if summary is None:
        summary = Summary(
            user_id=user_id,
            summary_type="daily",
            summary_date=summary_date,
            status="generated",
            summary_text="",
            meta_json={},
        )
        db.add(summary)
        db.flush()
    else:
        db.execute(delete(SummaryItem).where(SummaryItem.summary_id == summary.id))

    deduped_email_items = _dedupe_source_items(
        item for item in items if item.source_type == "email"
    )
    calendar_items = [item for item in items if item.source_type == "calendar_event"]

    actionable_emails = [item for item in deduped_email_items if classify_email_signal(item) == "actionable"]
    notification_emails = [item for item in deduped_email_items if classify_email_signal(item) == "notification"]
    marketing_emails = [item for item in deduped_email_items if classify_email_signal(item) == "marketing"]
    reference_emails = [item for item in deduped_email_items if classify_email_signal(item) == "reference"]
    filtered_items = _dedupe_source_items([*notification_emails, *marketing_emails])

    summary.summary_text = _build_summary_text([*calendar_items, *deduped_email_items])
    summary.meta_json = {
        "source_count": len(items),
        "generated_from_types": sorted({item.source_type for item in items}),
        "source_breakdown": {
            "email": len(items) - len(calendar_items),
            "calendar_event": len(calendar_items),
        },
        "signal_breakdown": {
            "actionable_email": len(actionable_emails),
            "notification_email": len(notification_emails),
            "reference_email": len(reference_emails),
            "marketing_email": len(marketing_emails),
        },
        "filtered_counts": {
            "notification_email": len(notification_emails),
            "marketing_email": len(marketing_emails),
            "suppressed_total": len(filtered_items),
        },
        "filtered_items": [
            _filtered_item_payload(item)
            for item in sorted(filtered_items, key=_item_priority, reverse=True)[:FILTERED_ITEM_PREVIEW_LIMIT]
        ],
    }

    db.add(summary)
    db.flush()

    top_items = sorted([*calendar_items, *deduped_email_items], key=_item_priority, reverse=True)
    selected_items = _dedupe_source_items(
        item for item in top_items if _should_include_summary_item(item)
    )[:8]

    if not selected_items:
        selected_items = _dedupe_source_items(
            item for item in top_items
            if item.source_type != "email" or classify_email_signal(item) != "marketing"
        )[:8]

    for source_item in selected_items:
        db.add(
            SummaryItem(
                summary_id=summary.id,
                **_source_item_to_summary_item(source_item),
            )
        )

    db.commit()
    db.refresh(summary)

    if log_activity:
        log_event(
            db,
            owner_type="user",
            owner_id=user_id,
            event_type=ActivityEvent.SUMMARY_GENERATED,
            event_source="summary_engine",
            message="已完成今日摘要整理。",
            related_entity_type="summary",
            related_entity_id=summary.id,
            meta_json={
                "summary_type": "daily",
                "item_count": len(selected_items),
            },
        )
        db.commit()
    return summary
