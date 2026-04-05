from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import SourceRecord, utcnow
from app.connectors.gmail import GmailConnector
from app.connectors.gcal import GoogleCalendarConnector
from app.models.integration import Integration, IntegrationToken
from app.models.source_data import SourceItem
from app.models.user import UserProfile
from app.services.activity_log_service import ActivityEvent, log_event
from app.services.plan_service import check_quota

CONNECTOR_REGISTRY = {
    "gmail": GmailConnector,
    "gcal": GoogleCalendarConnector,
}

VOLATILE_META_KEYS = {
    "etag",
    "historyId",
    "history_id",
    "internalDate",
    "internal_date",
    "lastFetchedAt",
    "last_fetched_at",
    "syncCursor",
    "sync_cursor",
    # Gmail 標籤常常只是已讀/未讀或系統分類變化，不應被視為內容更新
    "label_ids",
}


@dataclass
class IntegrationSyncResult:
    integration_id: str
    provider_key: str
    sync_status: str
    saved_count: int
    created_count: int
    updated_count: int
    fetched_count: int
    unchanged_count: int
    synced_at: object
    message: str


def get_connector(provider_key: str):
    connector_cls = CONNECTOR_REGISTRY.get(provider_key)
    if connector_cls is None:
        raise ValueError(f"Unsupported provider: {provider_key}")
    return connector_cls()


def ensure_integration_quota(db: Session, user_id: str) -> tuple[bool, int, int]:
    return check_quota(db, user_id, "active_integrations_count", amount=1)


def _provider_display_name(provider_key: str) -> str:
    if provider_key == "gmail":
        return "Gmail"
    if provider_key == "gcal":
        return "Google Calendar"
    return provider_key


def _ensure_onboarding_completed(db: Session, user_id: str) -> None:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is None:
        profile = UserProfile(user_id=user_id, onboarding_completed=True)
        db.add(profile)
        return

    if not profile.onboarding_completed:
        profile.onboarding_completed = True
        db.add(profile)


def upsert_integration(
    db: Session,
    *,
    user_id: str,
    provider_key: str,
    token_payload,
) -> Integration:
    integration = db.scalar(
        select(Integration).where(Integration.user_id == user_id, Integration.provider_key == provider_key)
    )
    if integration is None:
        integration = Integration(user_id=user_id, provider_key=provider_key, status="connected", connected_at=utcnow())
        db.add(integration)
        db.flush()
    else:
        integration.status = "connected"
        if integration.connected_at is None:
            integration.connected_at = utcnow()

    access_token = (token_payload.access_token or "").strip()
    refresh_token = (token_payload.refresh_token or "").strip() if token_payload.refresh_token else None

    if integration.token is None:
        token = IntegrationToken(
            integration_id=integration.id,
            access_token_encrypted=access_token,
            refresh_token_encrypted=refresh_token,
            expires_at=token_payload.expires_at,
            scopes=" ".join(token_payload.scopes),
        )
        db.add(token)
        db.flush()
    else:
        integration.token.access_token_encrypted = access_token
        if refresh_token:
            integration.token.refresh_token_encrypted = refresh_token
        integration.token.expires_at = token_payload.expires_at
        integration.token.scopes = " ".join(token_payload.scopes)

    _ensure_onboarding_completed(db, user_id)
    db.commit()
    db.refresh(integration)

    log_event(
        db,
        owner_type="user",
        owner_id=user_id,
        event_type=ActivityEvent.INTEGRATION_CONNECTED,
        event_source=provider_key,
        message=f"{_provider_display_name(provider_key)} 已成功連接。",
        related_entity_type="integration",
        related_entity_id=integration.id,
    )
    db.commit()
    return integration


def _normalize_text_for_hash(value: str | None) -> str:
    text = unescape(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h\d|ul|ol)>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split())


def _normalize_dt_for_hash(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _normalize_participants_for_hash(participants) -> str:
    if not participants:
        return ""

    normalized: list[str] = []
    for participant in participants:
        if isinstance(participant, dict):
            normalized.append(
                json.dumps(
                    {
                        "email": _normalize_text_for_hash(str(participant.get("email") or "")).lower(),
                        "name": _normalize_text_for_hash(str(participant.get("name") or "")),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            normalized.append(_normalize_text_for_hash(str(participant)).lower())

    normalized.sort()
    return "|".join(normalized)


def _normalize_json_value(value):
    if isinstance(value, dict):
        return {
            key: _normalize_json_value(value[key])
            for key in sorted(value.keys())
            if value[key] not in (None, "", [], {})
        }
    if isinstance(value, list):
        normalized_list = [_normalize_json_value(item) for item in value]
        try:
            return sorted(normalized_list, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
        except TypeError:
            return normalized_list
    return value


def _normalize_meta_for_hash(source_meta) -> str:
    if not isinstance(source_meta, dict):
        return ""

    cleaned: dict[str, object] = {}
    for key, value in source_meta.items():
        if key in VOLATILE_META_KEYS:
            continue
        if value in (None, "", [], {}):
            continue
        cleaned[key] = _normalize_json_value(value)

    if not cleaned:
        return ""

    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True, default=str)


def _to_source_item_hash(record: SourceRecord) -> str:
    normalized_title = _normalize_text_for_hash(record.title)
    normalized_content = _normalize_text_for_hash(record.content_text)
    normalized_dt = _normalize_dt_for_hash(record.source_timestamp)
    normalized_participants = _normalize_participants_for_hash(record.participants)
    normalized_meta = _normalize_meta_for_hash(record.source_meta)

    raw = "|".join(
        [
            record.source_type or "",
            record.external_id or "",
            normalized_title,
            normalized_content,
            normalized_dt if record.source_type == "calendar_event" else "",
            normalized_participants if record.source_type == "calendar_event" else "",
            normalized_meta,
        ]
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def _refresh_integration_access_token(db: Session, integration: Integration, connector) -> None:
    if integration.token is None:
        raise ValueError("Integration token not found")

    refresh_token = (integration.token.refresh_token_encrypted or "").strip()
    if not refresh_token:
        raise RuntimeError("來源授權已失效，請先移除來源並重新連接後再同步。")

    refreshed = connector.refresh_access_token(refresh_token)
    new_access_token = str(refreshed["access_token"]).strip()

    integration.token.access_token_encrypted = new_access_token

    expires_in = refreshed.get("expires_in")
    if isinstance(expires_in, int | float):
        integration.token.expires_at = utcnow() + timedelta(seconds=float(expires_in))

    new_scope = refreshed.get("scope")
    if isinstance(new_scope, str) and new_scope.strip():
        integration.token.scopes = new_scope.strip()

    db.add(integration.token)
    db.add(integration)
    db.commit()
    db.refresh(integration)


def _build_sync_message(
    provider_name: str,
    *,
    fetched_count: int,
    created_count: int,
    updated_count: int,
    unchanged_count: int,
) -> tuple[str, str]:
    changed_count = created_count + updated_count

    if fetched_count == 0:
        return "no_change", f"{provider_name} 已完成同步，本次沒有抓到可更新的資料。"

    if changed_count == 0:
        return "no_change", f"{provider_name} 已完成同步，本次檢查 {fetched_count} 筆資料，沒有新的重點變化。"

    parts: list[str] = []
    if created_count > 0:
        parts.append(f"新增 {created_count}")
    if updated_count > 0:
        parts.append(f"更新 {updated_count}")
    if unchanged_count > 0:
        parts.append(f"略過 {unchanged_count}")

    return "success", f"{provider_name} 同步完成，本次檢查 {fetched_count} 筆資料，" + "、".join(parts) + "。"


def sync_integration(db: Session, integration: Integration) -> IntegrationSyncResult:
    connector = get_connector(integration.provider_key)
    if integration.token is None:
        raise ValueError("Integration token not found")

    provider_name = _provider_display_name(integration.provider_key)

    log_event(
        db,
        owner_type="user",
        owner_id=integration.user_id,
        event_type=ActivityEvent.INTEGRATION_SYNC_STARTED,
        event_source=integration.provider_key,
        message=f"{provider_name} 開始同步。",
        related_entity_type="integration",
        related_entity_id=integration.id,
    )
    db.commit()

    access_token = (integration.token.access_token_encrypted or "").strip()
    try:
        records, next_cursor = connector.fetch_source_records(
            access_token=access_token,
            sync_cursor=integration.sync_cursor,
        )
    except Exception as exc:
        message = str(exc)
        needs_refresh = (
            "Invalid Credentials" in message
            or "UNAUTHENTICATED" in message
            or "401" in message
            or "invalid authentication credentials" in message.lower()
        )
        if not needs_refresh:
            raise

        _refresh_integration_access_token(db, integration, connector)
        access_token = (integration.token.access_token_encrypted or "").strip()

        records, next_cursor = connector.fetch_source_records(
            access_token=access_token,
            sync_cursor=integration.sync_cursor,
        )

    fetched_count = len(records)
    created_count = 0
    updated_count = 0
    unchanged_count = 0

    for record in records:
        existing = db.scalar(
            select(SourceItem).where(
                SourceItem.integration_id == integration.id,
                SourceItem.external_id == record.external_id,
            )
        )

        next_hash = _to_source_item_hash(record)

        if existing is None:
            existing = SourceItem(
                user_id=integration.user_id,
                integration_id=integration.id,
                source_type=record.source_type,
                external_id=record.external_id,
                title=record.title,
                content_text=record.content_text,
                source_timestamp=record.source_timestamp,
                participants_json=record.participants,
                source_meta_json=record.source_meta,
                hash_signature=next_hash,
            )
            db.add(existing)
            created_count += 1
            continue

        if existing.hash_signature == next_hash:
            unchanged_count += 1
            continue

        existing.title = record.title
        existing.content_text = record.content_text
        existing.source_timestamp = record.source_timestamp
        existing.participants_json = record.participants
        existing.source_meta_json = record.source_meta
        existing.hash_signature = next_hash
        updated_count += 1

    changed_count = created_count + updated_count
    synced_at = utcnow()
    integration.sync_cursor = next_cursor
    integration.last_synced_at = synced_at

    sync_status, message = _build_sync_message(
        provider_name,
        fetched_count=fetched_count,
        created_count=created_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
    )

    integration.meta_json = {
        **(integration.meta_json or {}),
        "last_sync_result": sync_status,
        "last_sync_saved_count": changed_count,
        "last_sync_created_count": created_count,
        "last_sync_updated_count": updated_count,
        "last_sync_fetched_count": fetched_count,
        "last_sync_unchanged_count": unchanged_count,
        "last_sync_message": message,
    }

    db.add(integration)
    _ensure_onboarding_completed(db, integration.user_id)
    db.commit()

    log_event(
        db,
        owner_type="user",
        owner_id=integration.user_id,
        event_type=ActivityEvent.INTEGRATION_SYNC_COMPLETED,
        event_source=integration.provider_key,
        message=message,
        related_entity_type="integration",
        related_entity_id=integration.id,
        meta_json={
            "fetched_count": fetched_count,
            "saved_count": changed_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "sync_status": sync_status,
        },
    )
    db.commit()

    return IntegrationSyncResult(
        integration_id=integration.id,
        provider_key=integration.provider_key,
        sync_status=sync_status,
        saved_count=changed_count,
        created_count=created_count,
        updated_count=updated_count,
        fetched_count=fetched_count,
        unchanged_count=unchanged_count,
        synced_at=synced_at,
        message=message,
    )
