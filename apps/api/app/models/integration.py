from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, DateTime, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Integration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("user_id", "provider_key", name="uq_user_provider"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    connected_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    user = relationship("User", back_populates="integrations")
    token = relationship("IntegrationToken", back_populates="integration", uselist=False, cascade="all, delete-orphan")


class IntegrationToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "integration_tokens"

    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), unique=True, nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text)

    integration = relationship("Integration", back_populates="token")
