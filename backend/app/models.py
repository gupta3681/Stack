import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class PriorityHint(str, enum.Enum):
    top = "top"
    high = "high"
    normal = "normal"
    low = "low"


class StackKind(str, enum.Enum):
    daily = "daily"        # date-bound, single per (user, date)
    todo = "todo"          # generic action items
    reading = "reading"
    watching = "watching"
    listening = "listening"
    buy = "buy"
    ideas = "ideas"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Set when the user dismisses the first-run onboarding tips. NULL means the
    # tips are still shown on next visit.
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Stack(Base):
    __tablename__ = "stacks"
    # Uniqueness only matters for daily stacks (one per user per date). For
    # topic stacks, stack_date is NULL — both SQLite and Postgres treat NULL
    # as distinct, so multiple topic stacks can coexist.
    __table_args__ = (UniqueConstraint("user_id", "stack_date", name="uq_user_stackdate"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[StackKind] = mapped_column(
        Enum(StackKind), default=StackKind.daily, nullable=False, index=True
    )
    # For kind=daily: stack_date is set, name is null (date is the identity).
    # For kind=topic: stack_date is null, name is set (user-given label).
    stack_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    intention: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # No delete-orphan: setting task.stack_id=None (move to backlog) must NOT
    # delete the task. Stack deletion is handled by the FK's ondelete=SET NULL.
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="stack",
        order_by="Task.position",
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    stack_id: Mapped[int | None] = mapped_column(
        ForeignKey("stacks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending, nullable=False
    )
    priority_hint: Mapped[PriorityHint | None] = mapped_column(
        Enum(PriorityHint), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    in_progress_started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    accumulated_seconds: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    stack: Mapped["Stack | None"] = relationship(back_populates="tasks")
