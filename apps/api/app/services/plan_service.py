from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.integration import Integration
from app.models.plan import Plan, PlanFeature, Subscription, UsageCounter

DEFAULT_PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "name": "免費版",
        "plan_type": "individual",
        "features": {
            "max_integrations": ("1", "integer"),
            "monthly_ai_quota": ("20", "integer"),
            "history_days": ("7", "integer"),
            "daily_summary_enabled": ("true", "boolean"),
            "weekly_summary_enabled": ("false", "boolean"),
            "team_space_enabled": ("false", "boolean"),
        },
    },
    "personal": {
        "name": "個人版",
        "plan_type": "individual",
        "features": {
            "max_integrations": ("3", "integer"),
            "monthly_ai_quota": ("200", "integer"),
            "history_days": ("30", "integer"),
            "daily_summary_enabled": ("true", "boolean"),
            "weekly_summary_enabled": ("true", "boolean"),
            "team_space_enabled": ("false", "boolean"),
        },
    },
    "pro": {
        "name": "專業個人版",
        "plan_type": "individual",
        "features": {
            "max_integrations": ("5", "integer"),
            "monthly_ai_quota": ("500", "integer"),
            "history_days": ("90", "integer"),
            "daily_summary_enabled": ("true", "boolean"),
            "weekly_summary_enabled": ("true", "boolean"),
            "team_space_enabled": ("false", "boolean"),
        },
    },
    "team_lite": {
        "name": "團隊 Lite",
        "plan_type": "team",
        "features": {
            "max_integrations": ("3", "integer"),
            "monthly_ai_quota": ("500", "integer"),
            "history_days": ("30", "integer"),
            "team_space_enabled": ("true", "boolean"),
        },
    },
    "team_plus": {
        "name": "團隊 Plus",
        "plan_type": "team",
        "features": {
            "max_integrations": ("5", "integer"),
            "monthly_ai_quota": ("1000", "integer"),
            "history_days": ("90", "integer"),
            "team_space_enabled": ("true", "boolean"),
        },
    },
}


def ensure_default_plans(db: Session) -> None:
    existing = {plan.plan_key: plan for plan in db.scalars(select(Plan)).all()}
    changed = False
    for plan_key, config in DEFAULT_PLANS.items():
        plan = existing.get(plan_key)
        if plan is None:
            plan = Plan(plan_key=plan_key, name=config["name"], plan_type=config["plan_type"], is_active=True)
            db.add(plan)
            db.flush()
            changed = True
        feature_map = {
            feature.feature_key: feature
            for feature in db.scalars(select(PlanFeature).where(PlanFeature.plan_id == plan.id)).all()
        }
        for feature_key, (feature_value, value_type) in config["features"].items():
            feature = feature_map.get(feature_key)
            if feature is None:
                db.add(
                    PlanFeature(
                        plan_id=plan.id,
                        feature_key=feature_key,
                        feature_value=feature_value,
                        value_type=value_type,
                    )
                )
                changed = True
    if changed:
        db.commit()


def _get_plan(db: Session, plan_key: str) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.plan_key == plan_key))
    if plan is None:
        raise ValueError(f"Plan not found: {plan_key}")
    return plan


def ensure_user_subscription(db: Session, user_id: str, default_plan_key: str = "free") -> Subscription:
    ensure_default_plans(db)
    subscription = db.scalar(
        select(Subscription).where(Subscription.owner_type == "user", Subscription.owner_id == user_id)
    )
    if subscription is None:
        plan = _get_plan(db, default_plan_key)
        subscription = Subscription(
            owner_type="user",
            owner_id=user_id,
            plan_id=plan.id,
            status="active",
            started_at=datetime.now(timezone.utc),
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
    return subscription


def get_feature_map(db: Session, plan_id: str) -> dict[str, Any]:
    features = db.scalars(select(PlanFeature).where(PlanFeature.plan_id == plan_id)).all()
    output: dict[str, Any] = {}
    for feature in features:
        raw = feature.feature_value
        if feature.value_type == "integer":
            output[feature.feature_key] = int(raw)
        elif feature.value_type == "boolean":
            output[feature.feature_key] = raw.lower() == "true"
        else:
            output[feature.feature_key] = raw
    return output


def get_current_plan_payload(db: Session, user_id: str) -> dict[str, Any]:
    subscription = ensure_user_subscription(db, user_id)
    plan = db.get(Plan, subscription.plan_id)
    features = get_feature_map(db, plan.id)
    return {
        "plan_key": plan.plan_key,
        "plan_name": plan.name,
        "status": subscription.status,
        "features": {
            "daily_summary_enabled": features.get("daily_summary_enabled", False),
            "weekly_summary_enabled": features.get("weekly_summary_enabled", False),
            "team_space_enabled": features.get("team_space_enabled", False),
        },
        "quotas": {
            "max_integrations": features.get("max_integrations", 0),
            "monthly_ai_quota": features.get("monthly_ai_quota", 0),
            "history_days": features.get("history_days", 0),
        },
    }


def get_or_create_usage_counter(db: Session, *, owner_type: str, owner_id: str, metric_key: str, period_key: str) -> UsageCounter:
    counter = db.scalar(
        select(UsageCounter).where(
            UsageCounter.owner_type == owner_type,
            UsageCounter.owner_id == owner_id,
            UsageCounter.metric_key == metric_key,
            UsageCounter.period_key == period_key,
        )
    )
    if counter is None:
        counter = UsageCounter(owner_type=owner_type, owner_id=owner_id, metric_key=metric_key, period_key=period_key)
        db.add(counter)
        db.commit()
        db.refresh(counter)
    return counter


def count_active_integrations(db: Session, user_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Integration)
            .where(Integration.user_id == user_id, Integration.status == "connected")
        )
        or 0
    )


def get_usage_payload(db: Session, user_id: str) -> dict[str, Any]:
    plan_payload = get_current_plan_payload(db, user_id)
    period_key = datetime.now(timezone.utc).strftime("%Y-%m")
    ai_counter = get_or_create_usage_counter(
        db, owner_type="user", owner_id=user_id, metric_key="monthly_ai_usage", period_key=period_key
    )
    active_integrations_count = count_active_integrations(db, user_id)
    return {
        "monthly_ai_usage": ai_counter.usage_value,
        "monthly_ai_quota": plan_payload["quotas"]["monthly_ai_quota"],
        "active_integrations_count": active_integrations_count,
        "max_integrations": plan_payload["quotas"]["max_integrations"],
        "history_days_limit": plan_payload["quotas"]["history_days"],
    }


def check_feature_enabled(db: Session, user_id: str, feature_key: str) -> bool:
    payload = get_current_plan_payload(db, user_id)
    return bool(payload["features"].get(feature_key, False))


def check_quota(db: Session, user_id: str, metric_key: str, amount: int = 1) -> tuple[bool, int, int]:
    usage_payload = get_usage_payload(db, user_id)
    quota_key_map = {
        "monthly_ai_usage": "monthly_ai_quota",
        "active_integrations_count": "max_integrations",
    }
    current = usage_payload.get(metric_key, 0)
    max_allowed = usage_payload.get(quota_key_map[metric_key], 0)
    return current + amount <= max_allowed, current, max_allowed


def increment_usage(db: Session, *, user_id: str, metric_key: str, amount: int = 1) -> UsageCounter:
    period_key = datetime.now(timezone.utc).strftime("%Y-%m") if metric_key == "monthly_ai_usage" else "lifetime"
    counter = get_or_create_usage_counter(
        db, owner_type="user", owner_id=user_id, metric_key=metric_key, period_key=period_key
    )
    counter.usage_value += amount
    db.add(counter)
    db.commit()
    db.refresh(counter)
    return counter
