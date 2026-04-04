from __future__ import annotations

from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.responses import success_response
from app.services.auth_service import upsert_user_from_google_profile
from app.services.integration_service import get_connector, upsert_integration

router = APIRouter(prefix="/auth/google", tags=["auth"])


def _parse_state(state: str | None) -> tuple[str, str]:
    raw = state or "login:gmail"
    if ":" in raw:
        mode, provider_key = raw.split(":", 1)
        mode = mode or "login"
        provider_key = provider_key or "gmail"
        return mode, provider_key
    return "login", raw or "gmail"


def _frontend_sources_url(settings) -> str:
    frontend_success_url = getattr(settings, "frontend_success_url", None) or "http://localhost:3000/auth/success"
    parts = urlsplit(frontend_success_url)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}/sources"
    return "http://localhost:3000/sources"


@router.get("/login")
def google_login(provider_key: str | None = Query(default=None)) -> dict:
    provider_key = provider_key or "gmail"
    try:
        connector = get_connector(provider_key)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": f"不支援的登入來源：{exc}"},
        ) from exc
    state = f"login:{provider_key}"
    return success_response({"redirect_url": connector.build_authorization_url(state=state), "provider_key": provider_key})


@router.get("/callback")
def google_callback(
    code: str = Query(...),
    state: str = Query("login:gmail"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    mode, provider_key = _parse_state(state)

    try:
        try:
            connector = get_connector(provider_key)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": f"不支援的登入來源：{exc}"},
            ) from exc

        token_payload = connector.exchange_code(code)
        user, access_token = upsert_user_from_google_profile(db, token_payload.profile, settings.secret_key)

        if mode == "connect":
            integration = upsert_integration(db, user_id=user.id, provider_key=provider_key, token_payload=token_payload)
            target = _frontend_sources_url(settings)
            hash_fragment = (
                f"oauth=success&provider={quote(provider_key)}&integration_id={quote(integration.id)}"
                f"&access_token={quote(access_token)}"
            )
            return RedirectResponse(url=f"{target}#{hash_fragment}", status_code=status.HTTP_302_FOUND)

    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OAUTH_NOT_CONFIGURED",
                "message": f"目前尚未啟用正式 Google OAuth，請先確認開發模式或 OAuth 設定：{exc}",
            },
        ) from exc

    return success_response(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "avatar_url": user.avatar_url,
            },
        }
    )
