from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    agent_kind: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    namespace: Mapped[str] = mapped_column(String(128))
    image: Mapped[str] = mapped_column(String(256))
    job_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt: Mapped[str] = mapped_column(Text)

    events: Mapped[list["Event"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Event.id"
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    kind: Mapped[str] = mapped_column(String(32))  # prompt|tool|stdout|stderr|status|finish
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[Run] = relationship(back_populates="events")
