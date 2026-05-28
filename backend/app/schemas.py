from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import PriorityHint, StackKind, TaskStatus


def _validate_url_scheme(value: str | None) -> str | None:
    """Reject anything that isn't http(s)://. Treat blank as cleared.

    Without this guard a malicious owner could store a `javascript:` URL
    as their task's direct_link; the public viewer renders it as `<a href>`
    and the owner card opens it via window.open — both paths execute the
    script in the visitor's Stack origin with their session cookie.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    lowered = trimmed.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        raise ValueError("direct_link must be an http:// or https:// URL")
    return trimmed


class TaskBase(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    # Long-form markdown with optional YAML frontmatter (name, description,
    # direct_link). The backend doesn't parse it today — agents will later.
    context_md: str | None = None
    # The URL the task points to. Used as the primary click target on cards
    # when set. Stored as a separate column for fast access. Restricted to
    # http(s) at the schema layer — see _validate_url_scheme.
    direct_link: str | None = Field(default=None, max_length=2048)
    due_at: datetime | None = None
    # Optional time budget in minutes. Summed at the stack level for the
    # "planned time" total in the header.
    estimate_minutes: int | None = Field(default=None, ge=0, le=24 * 60)

    _check_direct_link = field_validator("direct_link")(_validate_url_scheme)


class TaskCreate(TaskBase):
    # Exactly one of stack_date / stack_id may be provided.
    # - stack_date → resolves to (or creates) the daily stack for that date
    # - stack_id   → references an existing topic stack
    # - neither    → unscheduled backlog item
    stack_date: date | None = None
    stack_id: int | None = None
    priority_hint: PriorityHint | None = None


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    context_md: str | None = None
    direct_link: str | None = Field(default=None, max_length=2048)
    status: TaskStatus | None = None
    due_at: datetime | None = None
    priority_hint: PriorityHint | None = None
    estimate_minutes: int | None = Field(default=None, ge=0, le=24 * 60)

    _check_direct_link = field_validator("direct_link")(_validate_url_scheme)


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


class CompletedTaskOut(TaskOut):
    """A done task plus the context of the stack it was completed in.

    Powers the cross-stack Completed archive. The three stack_* fields are
    folded in by the endpoint so the page can show and filter by source
    without an N+1 of stack lookups. All three are null when the task lives
    in the backlog (stack_id is None).
    """

    stack_kind: StackKind | None = None
    stack_name: str | None = None
    stack_date: date | None = None


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
    share_context_in_public: bool = False


class StackUpdate(BaseModel):
    intention: str | None = None
    name: str | None = None
    share_context_in_public: bool | None = None


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

    `context_md` is only populated when the owner opts in via the
    stack-level share_context_in_public flag — see public router.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str
    context_md: str | None = None
    direct_link: str | None = None
    priority_hint: PriorityHint | None
    due_at: datetime | None
    estimate_minutes: int | None = None
    position: int


class PublicStackOut(BaseModel):
    """The shape served at GET /public/stacks/{slug} (no auth required)."""

    model_config = ConfigDict(from_attributes=True)

    kind: StackKind
    name: str
    intention: str | None
    owner_display_name: str | None
    tasks: list[PublicTaskOut]
