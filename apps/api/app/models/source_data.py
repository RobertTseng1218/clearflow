from __future__ import annotations

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SourceItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_items"
    __table_args__ = (UniqueConstraint("integration_id", "external_id", name="uq_integration_external_id"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    source_timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    participants_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    hash_signature: Mapped[str | None] = mapped_column(String(255))


class Summary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "summaries"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary_date: Mapped[object] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    summary_text: Mapped[str | None] = mapped_column(Text)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    items = relationship("SummaryItem", back_populates="summary", cascade="all, delete-orphan")


class SummaryItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "summary_items"

    summary_id: Mapped[str] = mapped_column(ForeignKey("summaries.id", ondelete="CASCADE"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority_score: Mapped[float | None] = mapped_column(Numeric(10, 2))
    related_source_item_id: Mapped[str | None] = mapped_column(ForeignKey("source_items.id", ondelete="SET NULL"))
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    summary = relationship("Summary", back_populates="items")


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"

    owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50))
    created_by_type: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    task_hash: Mapped[str | None] = mapped_column(String(255))
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TaskSource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_sources"
    __table_args__ = (UniqueConstraint("task_id", "source_item_id", name="uq_task_source_pair"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    source_item_id: Mapped[str] = mapped_column(ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="derived_from")
