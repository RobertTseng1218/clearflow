from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plans"

    plan_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    features = relationship("PlanFeature", back_populates="plan", cascade="all, delete-orphan")


class PlanFeature(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plan_features"
    __table_args__ = (UniqueConstraint("plan_id", "feature_key", name="uq_plan_feature"),)

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")

    plan = relationship("Plan", back_populates="features")


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewal_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan = relationship("Plan")


class UsageCounter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "metric_key", "period_key", name="uq_usage_metric_period"),
    )

    owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    period_key: Mapped[str] = mapped_column(String(30), nullable=False)
    usage_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reset_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
