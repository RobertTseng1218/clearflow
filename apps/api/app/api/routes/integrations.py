from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.integration import Integration
from app.models.user import User
from app.services.integration_service import ensure_integration_quota, get_connector, sync_integration, upsert_integration

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _serialize_dt(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


@router.get("")
def list_integrations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    integrations = list(
        db.scalars(select(Integration).where(Integration.user_id == current_user.id).order_by(Integration.created_at.desc()))
    )
    return success_response(
        {
            "items": [
                {
                    "id": item.id,
                    "provider_key": item.provider_key,
                    "status": item.status,
                    "connected_at": _serialize_dt(item.connected_at),
                    "last_synced_at": _serialize_dt(item.last_synced_at),
                    "display_timezone": "Asia/Taipei",
                    "last_sync_result": (item.meta_json or {}).get("last_sync_result"),
                    "last_sync_saved_count": (item.meta_json or {}).get("last_sync_saved_count"),
                    "last_sync_created_count": (item.meta_json or {}).get("last_sync_created_count"),
                    "last_sync_updated_count": (item.meta_json or {}).get("last_sync_updated_count"),
                    "last_sync_fetched_count": (item.meta_json or {}).get("last_sync_fetched_count"),
                    "last_sync_unchanged_count": (item.meta_json or {}).get("last_sync_unchanged_count"),
                    "last_sync_message": (item.meta_json or {}).get("last_sync_message"),
                    "meta": item.meta_json,
                }
                for item in integrations
            ]
        },
        meta={"total": len(integrations)},
    )


@router.post("/connect")
def connect_integration(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    provider_key = payload.get("provider_key")
    if provider_key not in {"gmail", "gcal"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": "不支援的來源類型，請改用 Gmail 或 Google Calendar。"},
        )
    allowed, current, max_allowed = ensure_integration_quota(db, current_user.id)
    existing = db.scalar(select(Integration).where(Integration.user_id == current_user.id, Integration.provider_key == provider_key))
    if existing is None and not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INTEGRATION_LIMIT_REACHED",
                "message": "免費版目前最多只能連接 1 個來源。若要同時使用 Gmail 與 Google Calendar，請升級個人版。",
                "details": {"current": current, "max_allowed": max_allowed},
            },
        )
    connector = get_connector(provider_key)
    return success_response({"redirect_url": connector.build_authorization_url(state=f"connect:{provider_key}"), "provider_key": provider_key})


@router.post("/callback")
def complete_integration_connect(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    provider_key = payload.get("provider_key")
    code = payload.get("code")
    if not provider_key or not code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": "缺少必要參數，請確認 provider_key 與 code 是否都有帶入。"},
        )
    allowed, current, max_allowed = ensure_integration_quota(db, current_user.id)
    existing = db.scalar(select(Integration).where(Integration.user_id == current_user.id, Integration.provider_key == provider_key))
    if existing is None and not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INTEGRATION_LIMIT_REACHED",
                "message": "免費版目前最多只能連接 1 個來源。若要同時使用 Gmail 與 Google Calendar，請升級個人版。",
                "details": {"current": current, "max_allowed": max_allowed},
            },
        )
    try:
        connector = get_connector(provider_key)
        token_payload = connector.exchange_code(code)
        integration = upsert_integration(db, user_id=current_user.id, provider_key=provider_key, token_payload=token_payload)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "OAUTH_NOT_CONFIGURED", "message": f"目前尚未完成 {provider_key} 的正式 OAuth 設定：{exc}"},
        ) from exc
    return success_response(
        {
            "id": integration.id,
            "provider_key": integration.provider_key,
            "status": integration.status,
        }
    )


@router.post("/{integration_id}/sync")
def manual_sync(integration_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    integration = db.scalar(select(Integration).where(Integration.id == integration_id, Integration.user_id == current_user.id))
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "找不到這個來源連接資料。"},
        )
    try:
        result = sync_integration(db, integration)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INTEGRATION_NOT_READY", "message": f"來源尚未完成可同步狀態，暫時無法同步：{exc}"},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INTEGRATION_RECONNECT_REQUIRED", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SYNC_FAILED", "message": "同步失敗，請稍後再試。", "details": {"reason": str(exc)}},
        ) from exc
    return success_response(
        {
            "integration_id": result.integration_id,
            "provider_key": result.provider_key,
            "sync_status": result.sync_status,
            "saved_count": result.saved_count,
            "created_count": result.created_count,
            "updated_count": result.updated_count,
            "fetched_count": result.fetched_count,
            "unchanged_count": result.unchanged_count,
            "synced_at": _serialize_dt(result.synced_at),
            "message": result.message,
        }
    )


@router.delete("/{integration_id}")
def revoke_integration(integration_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    integration = db.scalar(select(Integration).where(Integration.id == integration_id, Integration.user_id == current_user.id))
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "找不到要移除的來源連接。"},
        )
    db.delete(integration)
    db.commit()
    return success_response({"integration_id": integration_id, "deleted": True})
