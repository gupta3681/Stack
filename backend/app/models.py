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
    false,
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
    # Admin flag — gates the /admin/* router. Bootstrapped via ADMIN_EMAILS
    # env var (auto-promotes matching email on next session resolve).
    # Promote-only: removing an email from ADMIN_EMAILS doesn't demote — that
    # would have to be a manual DB flip.
    is_admin: Mapped[bool] = mapped_column(
        default=False, server_default=false(), nullable=False
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ApiToken(Base):
    """Long-lived bearer token for programmatic access (CLIs, agents, MCP).

    The raw token is shown to the user exactly once at creation; we store only
    a SHA-256 digest, so a DB leak can't be turned into account takeover. Each
    token has a human-given name (e.g. "laptop", "claude-code") and a public
    prefix shown in the UI to disambiguate without revealing the secret.

    No expiration by default — these are PATs, revoked explicitly from the
    Profile UI. last_used_at lets the user spot dormant tokens to clean up.
    """

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # User-given label. Not unique — "laptop" twice is fine; the prefix
    # disambiguates them in the UI.
    name: Mapped[str] = mapped_column(String(100))
    # SHA-256 hex of the raw token. Unique so lookup is a single PK-ish hit.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # First 12 chars of the raw token (e.g. "stk_abc12345"). Shown in the list
    # view so users can tell tokens apart without revealing the secret.
    prefix: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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

    # Sharing: a topic stack can be made publicly readable via a stable slug.
    # `is_public` is the toggle; `share_slug` is the URL-safe public identifier.
    # The slug is generated on first share and kept forever (re-sharing yields
    # the same URL — Notion-style). Only topic stacks can be made public.
    is_public: Mapped[bool] = mapped_column(
        default=False, server_default=false(), nullable=False
    )
    share_slug: Mapped[str | None] = mapped_column(
        String(20), unique=True, index=True, nullable=True
    )
    # When true, the public viewer includes each task's context_md body
    # (the long-form markdown). Default false so casual sharing doesn't
    # accidentally publish private notes.
    share_context_in_public: Mapped[bool] = mapped_column(
        default=False, server_default=false(), nullable=False
    )

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
    name: Mapped[str] = mapped_column(String(500))
    # Deprecated: description is being replaced by context_md (rich markdown
    # with optional frontmatter). Kept as a column in the DB for now since
    # SQLite can't drop columns and we backfill its data into context_md;
    # new code reads/writes context_md only.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rich long-form context — markdown with optional YAML frontmatter
    # (name, description, direct_link). Backend doesn't parse the
    # frontmatter today; that's user/agent convention.
    context_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The canonical URL the task points to. Used as the primary click target
    # on the task card. Separate column (not parsed from frontmatter) so the
    # click path doesn't need to crack the markdown every render.
    direct_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending, nullable=False
    )
    priority_hint: Mapped[PriorityHint | None] = mapped_column(
        Enum(PriorityHint), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # User-set time budget for the task, in minutes. Null = no estimate.
    # Used to sum a "planned time" total per stack so visitors can see
    # if a day fits the hours available.
    estimate_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
