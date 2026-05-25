"""Admin-only analytics endpoints.

Gated by `Depends(auth_service.require_admin)`. Non-admins (including
non-existent users) get 403. Admin status is bootstrapped via the
ADMIN_EMAILS env var — see auth.py `_auto_promote_admin`.

These endpoints are read-only. If we add destructive admin actions later
(ban-user, force-delete-stack), layer `require_session_auth` so a leaked
bearer can't, e.g., torch another user's data via a stolen admin token.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from .. import auth as auth_service
from .. import models
from ..database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Response shapes ────────────────────────────────────────────────────────


class UserStats(BaseModel):
    total: int
    active_last_7d: int
    active_last_30d: int
    admin_count: int


class TaskStats(BaseModel):
    total: int
    pending: int
    in_progress: int
    done: int
    cancelled: int
    completed_today: int
    completed_last_7d: int


class StackStats(BaseModel):
    topic_total: int
    by_kind: dict[str, int]
    public_count: int


class ApiTokenStats(BaseModel):
    total: int
    used_last_7d: int


class RecentSignup(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str | None
    created_at: datetime


class AdminStats(BaseModel):
    users: UserStats
    tasks: TaskStats
    stacks: StackStats
    api_tokens: ApiTokenStats
    recent_signups: list[RecentSignup]
    generated_at: datetime


class AdminUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str | None
    created_at: datetime
    is_admin: bool
    onboarded_at: datetime | None
    # Aggregates joined in via separate queries — not actual ORM columns.
    task_count: int = 0
    last_session_at: datetime | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/stats", response_model=AdminStats)
def admin_stats(
    db: DbSession = Depends(get_db),
    _admin: models.User = Depends(auth_service.require_admin),
):
    now = _now()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = db.execute(select(func.count(models.User.id))).scalar() or 0
    admin_count = (
        db.execute(
            select(func.count(models.User.id)).where(models.User.is_admin.is_(True))
        ).scalar()
        or 0
    )
    # "Active in last N days" = distinct user_ids with a session created in
    # that window. Sessions expire after 30d so this is bounded; using
    # created_at not expires_at because that's the actual login event.
    active_7d = (
        db.execute(
            select(func.count(func.distinct(models.Session.user_id))).where(
                models.Session.created_at >= cutoff_7d
            )
        ).scalar()
        or 0
    )
    active_30d = (
        db.execute(
            select(func.count(func.distinct(models.Session.user_id))).where(
                models.Session.created_at >= cutoff_30d
            )
        ).scalar()
        or 0
    )

    # Tasks by status: one grouped query, then unpack into named fields.
    status_rows = db.execute(
        select(models.Task.status, func.count(models.Task.id)).group_by(
            models.Task.status
        )
    ).all()
    by_status: dict[str, int] = {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "cancelled": 0,
    }
    for status_value, n in status_rows:
        # status_value is the enum on Postgres, the string on SQLite — both
        # have .value (or are already the string). Normalize.
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        by_status[key] = n
    total_tasks = sum(by_status.values())

    completed_today = (
        db.execute(
            select(func.count(models.Task.id)).where(
                models.Task.completed_at >= start_of_today
            )
        ).scalar()
        or 0
    )
    completed_7d = (
        db.execute(
            select(func.count(models.Task.id)).where(
                models.Task.completed_at >= cutoff_7d
            )
        ).scalar()
        or 0
    )

    # Stacks by kind. Topic-stack count excludes daily.
    kind_rows = db.execute(
        select(models.Stack.kind, func.count(models.Stack.id))
        .where(models.Stack.kind != models.StackKind.daily)
        .group_by(models.Stack.kind)
    ).all()
    by_kind: dict[str, int] = {}
    for kind_value, n in kind_rows:
        key = kind_value.value if hasattr(kind_value, "value") else str(kind_value)
        by_kind[key] = n
    topic_total = sum(by_kind.values())
    public_count = (
        db.execute(
            select(func.count(models.Stack.id)).where(
                models.Stack.is_public.is_(True)
            )
        ).scalar()
        or 0
    )

    token_total = (
        db.execute(select(func.count(models.ApiToken.id))).scalar() or 0
    )
    token_used_7d = (
        db.execute(
            select(func.count(models.ApiToken.id)).where(
                models.ApiToken.last_used_at >= cutoff_7d
            )
        ).scalar()
        or 0
    )

    recent = (
        db.execute(
            select(models.User)
            .order_by(models.User.created_at.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )

    return AdminStats(
        users=UserStats(
            total=total_users,
            active_last_7d=active_7d,
            active_last_30d=active_30d,
            admin_count=admin_count,
        ),
        tasks=TaskStats(
            total=total_tasks,
            pending=by_status["pending"],
            in_progress=by_status["in_progress"],
            done=by_status["done"],
            cancelled=by_status["cancelled"],
            completed_today=completed_today,
            completed_last_7d=completed_7d,
        ),
        stacks=StackStats(
            topic_total=topic_total,
            by_kind=by_kind,
            public_count=public_count,
        ),
        api_tokens=ApiTokenStats(
            total=token_total,
            used_last_7d=token_used_7d,
        ),
        recent_signups=[RecentSignup.model_validate(u) for u in recent],
        generated_at=now,
    )


@router.get("/users", response_model=list[AdminUser])
def admin_users(
    db: DbSession = Depends(get_db),
    _admin: models.User = Depends(auth_service.require_admin),
):
    """All users with per-user aggregates (task count + last session).

    No pagination. Fine at small scale; if this hits ~thousands of users we
    add limit/offset query params before the page becomes unusable.

    Never returns password_hash or any other secret — see AdminUser shape.
    """
    users = (
        db.execute(select(models.User).order_by(models.User.created_at.desc()))
        .scalars()
        .all()
    )

    # Aggregate task counts per user in one query, then index in Python.
    task_rows = db.execute(
        select(models.Task.user_id, func.count(models.Task.id)).group_by(
            models.Task.user_id
        )
    ).all()
    tasks_by_user: dict[int, int] = {uid: n for uid, n in task_rows}

    # Last session per user. Same shape — one query, then index.
    sess_rows = db.execute(
        select(models.Session.user_id, func.max(models.Session.created_at)).group_by(
            models.Session.user_id
        )
    ).all()
    last_session_by_user: dict[int, datetime] = {uid: ts for uid, ts in sess_rows}

    return [
        AdminUser(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            created_at=u.created_at,
            is_admin=u.is_admin,
            onboarded_at=u.onboarded_at,
            task_count=tasks_by_user.get(u.id, 0),
            last_session_at=last_session_by_user.get(u.id),
        )
        for u in users
    ]
