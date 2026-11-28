from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, LargeBinary, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JsonColumn = JSON().with_variant(JSONB(), "postgresql")


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _now() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    """One uploaded tender and everything the pipeline produced for it."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    document: Mapped[bytes] = mapped_column(LargeBinary)
    profile: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pages_done: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
