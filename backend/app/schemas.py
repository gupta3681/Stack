from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import PriorityHint, StackKind, TaskStatus


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    due_at: datetime | None = None


class TaskCreate(TaskBase):
    # Exactly one of stack_date / stack_id may be provided.
    # - stack_date → resolves to (or creates) the daily stack for that date
    # - stack_id   → references an existing topic stack
    # - neither    → unscheduled backlog item
    stack_date: date | None = None
    stack_id: int | None = None
    priority_hint: PriorityHint | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus | None = None
    due_at: datetime | None = None
    priority_hint: PriorityHint | None = None


class TaskMove(BaseModel):
    # Same rules as TaskCreate: pick at most one target.
    stack_date: date | None = None
    stack_id: int | None = None
    position: int | None = None


class TaskReorder(BaseModel):
    # The stack being reordered. Use stack_date for daily or stack_id for topic.
    # Both null = backlog (unscheduled tasks).
    stack_date: date | None = None
    stack_id: int | None = None
    ordered_ids: list[int]


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stack_id: int | None
    position: int
    status: TaskStatus
    priority_hint: PriorityHint | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    in_progress_started_at: datetime | None
    accumulated_seconds: int


class StackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # id is None when the row hasn't been created yet (GET on a date with no
    # tasks/intention). Frontend keys off stack_date for all follow-up calls.
    id: int | None
    kind: StackKind = StackKind.daily
    stack_date: date | None
    name: str | None = None
    intention: str | None
    tasks: list[TaskOut]
    is_public: bool = False
    share_slug: str | None = None


class StackUpdate(BaseModel):
    intention: str | None = None
    name: str | None = None


class TopicStackCreate(BaseModel):
    kind: StackKind
    name: str = Field(min_length=1, max_length=200)
    intention: str | None = None


class StackCounts(BaseModel):
    """Small summary used by the topbar nav badges."""

    today: int
    tomorrow: int
    topic_stacks: int


class PublicTaskOut(BaseModel):
    """Read-only view of a task, exposed on a public stack page.

    Fields deliberately omitted to avoid leaking owner-internal state:
      - status, completed_at, in_progress_started_at, accumulated_seconds
      - stack_id, user_id, created_at, updated_at
    Anything that says "this is what the owner is actively doing right now"
    is omitted; visitors see what's queued, not the operational state.
    """

    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str | None
    priority_hint: PriorityHint | None
    due_at: datetime | None
    position: int


class PublicStackOut(BaseModel):
    """The shape served at GET /public/stacks/{slug} (no auth required)."""

    model_config = ConfigDict(from_attributes=True)

    kind: StackKind
    name: str
    intention: str | None
    owner_display_name: str | None
    tasks: list[PublicTaskOut]
