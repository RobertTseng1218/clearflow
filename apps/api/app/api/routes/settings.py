from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import success_response
from app.core.security import get_current_user
from app.models.source_data import Summary
from app.models.user import User, UserProfile
from app.services.plan_service import get_current_plan_payload, get_usage_payload

router = APIRouter(prefix="/settings", tags=["settings"])


def _resolve_onboarding_state(db: Session, current_user: User, profile: UserProfile) -> bool:
    if profile.onboarding_completed:
        return True

    has_connected_integrations = any(item.status == "connected" for item in current_user.integrations)
    has_summary_history = db.scalar(
        select(Summary.id).where(Summary.user_id == current_user.id).limit(1)
    )

    if has_connected_integrations or has_summary_history is not None:
        profile.onboarding_completed = True
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return True

    return False


@router.get("")
def get_settings_payload(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    profile = current_user.profile
    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    onboarding_completed = _resolve_onboarding_state(db, current_user, profile)

    integrations = [
        {
            "id": item.id,
            "provider_key": item.provider_key,
            "status": item.status,
        }
        for item in current_user.integrations
    ]

    plan = get_current_plan_payload(db, current_user.id)
    usage = get_usage_payload(db, current_user.id)

    return success_response(
        {
            "profile": {
                "timezone": profile.timezone,
                "locale": profile.locale,
                "work_template_key": profile.work_template_key,
                "onboarding_completed": onboarding_completed,
            },
            "plan": {
                "plan_key": plan["plan_key"],
                "plan_name": plan["plan_name"],
            },
            "usage": {
                "monthly_ai_usage": usage["monthly_ai_usage"],
                "monthly_ai_quota": usage["monthly_ai_quota"],
            },
            "integrations": integrations,
            "notification_preferences": profile.notification_preference_json or {},
        }
    )


@router.patch("/notifications")
def patch_notification_settings(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    profile = current_user.profile
    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        db.flush()

    preferred_hour = payload.get("preferred_hour")
    if preferred_hour is not None:
        try:
            preferred_hour = int(preferred_hour)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "偏好時間必須是整數。"},
            ) from exc
        if preferred_hour < 0 or preferred_hour > 23:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_ERROR", "message": "偏好時間必須介於 0 到 23 之間。"},
            )

    prefs = dict(profile.notification_preference_json or {})
    if "daily_summary_enabled" in payload:
        prefs["daily_summary_enabled"] = bool(payload["daily_summary_enabled"])
    if preferred_hour is not None:
        prefs["preferred_hour"] = preferred_hour

    profile.notification_preference_json = prefs
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return success_response({"updated": True})
