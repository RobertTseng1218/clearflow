from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User, UserProfile
from app.services.activity_log_service import ActivityEvent, log_event
from app.services.plan_service import ensure_user_subscription


def upsert_user_from_google_profile(db: Session, profile: dict[str, str], secret_key: str) -> tuple[User, str]:
    provider_user_id = profile["provider_user_id"]
    user = db.scalar(
        select(User).where(User.auth_provider == "google", User.auth_provider_user_id == provider_user_id)
    )
    if user is None:
        user = User(
            email=profile["email"],
            name=profile.get("name"),
            avatar_url=profile.get("avatar_url"),
            auth_provider="google",
            auth_provider_user_id=provider_user_id,
            status="active",
        )
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.id))
    else:
        user.email = profile["email"]
        user.name = profile.get("name")
        user.avatar_url = profile.get("avatar_url")

    db.commit()
    db.refresh(user)
    ensure_user_subscription(db, user.id)
    log_event(
        db,
        owner_type="user",
        owner_id=user.id,
        event_type=ActivityEvent.USER_LOGIN,
        event_source="google_oauth",
        message="User logged in via Google OAuth.",
        related_entity_type="user",
        related_entity_id=user.id,
    )
    db.commit()
    token = create_access_token(user.id, secret_key=secret_key)
    return user, token
