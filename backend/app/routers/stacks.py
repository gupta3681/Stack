import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/stacks", tags=["stacks"])


def _generate_share_slug() -> str:
    """URL-safe ~11-char identifier, e.g. 'xK_9aP3-bRq'.

    With 8 bytes of entropy (~64 bits), collision is statistically irrelevant
    even at millions of slugs. We also enforce uniqueness at the DB level,
    so a collision would raise IntegrityError on commit — the caller retries.
    """
    return secrets.token_urlsafe(8)


def _select_stack(user_id: int, stack_date: date):
    return (
        select(models.Stack)
        .where(models.Stack.user_id == user_id, models.Stack.stack_date == stack_date)
        .options(selectinload(models.Stack.tasks))
    )


def find_stack(db: Session, user_id: int, stack_date: date) -> models.Stack | None:
    """Read-only — never auto-creates."""
    return db.execute(_select_stack(user_id, stack_date)).scalar_one_or_none()


def get_or_create_stack(db: Session, user_id: int, stack_date: date) -> models.Stack:
    """Idempotent: returns existing or creates. Safe under concurrent callers.

    Uses the uq_user_stackdate UniqueConstraint as the arbiter — if two callers
    race past the SELECT, the loser's INSERT raises IntegrityError, we roll back
    and re-select the winner's row.
    """
    stack = find_stack(db, user_id, stack_date)
    if stack is not None:
        return stack

    stack = models.Stack(user_id=user_id, stack_date=stack_date)
    db.add(stack)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        stack = find_stack(db, user_id, stack_date)
        if stack is None:
            # Race-with-resurrection shouldn't be possible — surface as 500.
            raise
        return stack
    db.refresh(stack)
    return stack


def _empty_stack_response(stack_date: date) -> schemas.StackOut:
    """Synthetic response for GETs on dates with no stack row yet.

    `id=None` is a marker meaning 'not persisted'. Frontend uses stack_date for
    all follow-up calls (PATCH intention, POST tasks), so id isn't needed.
    """
    return schemas.StackOut(
        id=None,
        kind=models.StackKind.daily,
        stack_date=stack_date,
        name=None,
        intention=None,
        tasks=[],
    )


def find_topic_stack(db: Session, user_id: int, stack_id: int) -> models.Stack | None:
    """Read-only fetch of a topic stack owned by `user_id`."""
    stmt = (
        select(models.Stack)
        .where(
            models.Stack.id == stack_id,
            models.Stack.user_id == user_id,
            models.Stack.kind != models.StackKind.daily,
        )
        .options(selectinload(models.Stack.tasks))
    )
    return db.execute(stmt).scalar_one_or_none()


@router.get("/today", response_model=schemas.StackOut)
def get_today_stack(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_or_create_stack(db, current_user.id, date.today())


@router.get("/tomorrow", response_model=schemas.StackOut)
def get_tomorrow_stack(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_or_create_stack(db, current_user.id, date.today() + timedelta(days=1))


@router.get("/overdue", response_model=list[schemas.TaskOut])
def get_overdue_tasks(
    today: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns tasks in past stacks that are still pending or in_progress.

    `today` is the client's local date — pass it as a query parameter so the
    overdue cutoff respects the user's wall clock instead of the server's
    timezone (relevant in Docker / UTC deployments at local midnight).
    Falls back to server `date.today()` if the param is omitted.
    """
    cutoff = today or date.today()
    stmt = (
        select(models.Task)
        .join(models.Stack)
        .where(
            models.Task.user_id == current_user.id,
            models.Stack.user_id == current_user.id,
            models.Stack.stack_date < cutoff,
            models.Task.status.in_(
                [models.TaskStatus.pending, models.TaskStatus.in_progress]
            ),
        )
        .order_by(models.Stack.stack_date.desc(), models.Task.position)
    )
    return db.execute(stmt).scalars().all()


@router.get("/topics", response_model=list[schemas.StackOut])
def list_topic_stacks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """All non-daily stacks owned by the user, ordered by kind then name."""
    stmt = (
        select(models.Stack)
        .where(
            models.Stack.user_id == current_user.id,
            models.Stack.kind != models.StackKind.daily,
        )
        .options(selectinload(models.Stack.tasks))
        .order_by(models.Stack.kind, models.Stack.name)
    )
    return db.execute(stmt).scalars().all()


@router.post(
    "/topics", response_model=schemas.StackOut, status_code=status.HTTP_201_CREATED
)
def create_topic_stack(
    payload: schemas.TopicStackCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.kind == models.StackKind.daily:
        raise HTTPException(
            status_code=400, detail="Daily stacks are created implicitly by date."
        )
    stack = models.Stack(
        user_id=current_user.id,
        kind=payload.kind,
        name=payload.name.strip(),
        intention=payload.intention,
    )
    db.add(stack)
    db.commit()
    db.refresh(stack)
    return stack


@router.get("/topics/{stack_id}", response_model=schemas.StackOut)
def get_topic_stack(
    stack_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stack = find_topic_stack(db, current_user.id, stack_id)
    if stack is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    return stack


@router.patch("/topics/{stack_id}", response_model=schemas.StackOut)
def update_topic_stack(
    stack_id: int,
    payload: schemas.StackUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stack = find_topic_stack(db, current_user.id, stack_id)
    if stack is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    fields = payload.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        stack.name = fields["name"].strip()
    if "intention" in fields:
        stack.intention = fields["intention"]
    if "share_context_in_public" in fields and fields["share_context_in_public"] is not None:
        stack.share_context_in_public = fields["share_context_in_public"]
    db.commit()
    db.refresh(stack)
    return stack


@router.delete("/topics/{stack_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic_stack(
    stack_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stack = find_topic_stack(db, current_user.id, stack_id)
    if stack is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    db.delete(stack)
    db.commit()


@router.post("/topics/{stack_id}/share", response_model=schemas.StackOut)
def share_topic_stack(
    stack_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Flip is_public=true. Generate share_slug if this is the first share.

    Re-sharing a previously-shared stack returns the same slug (Notion-style).
    Slug-collision retry: if our random slug happens to clash (statistically
    impossible at this scale but possible), regenerate and try again.
    """
    stack = find_topic_stack(db, current_user.id, stack_id)
    if stack is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    if stack.share_slug is None:
        # db.rollback() expires every attribute on `stack`, so is_public must
        # be re-applied inside the loop or a retried commit will write the
        # default (False) along with the new slug.
        for _ in range(5):
            stack.is_public = True
            stack.share_slug = _generate_share_slug()
            try:
                db.commit()
                break
            except IntegrityError:
                db.rollback()
        else:
            raise HTTPException(
                status_code=500, detail="Could not generate a unique share slug"
            )
    else:
        stack.is_public = True
        db.commit()
    db.refresh(stack)
    return stack


@router.post("/topics/{stack_id}/unshare", response_model=schemas.StackOut)
def unshare_topic_stack(
    stack_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Flip is_public=false. KEEP the slug so re-sharing yields the same URL."""
    stack = find_topic_stack(db, current_user.id, stack_id)
    if stack is None:
        raise HTTPException(status_code=404, detail="Stack not found")
    stack.is_public = False
    db.commit()
    db.refresh(stack)
    return stack


@router.get("/counts", response_model=schemas.StackCounts)
def stack_counts(
    today: date | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Lightweight summary for the topbar badges.

    Counts pending+in-progress tasks for today and tomorrow (so completed
    tasks don't inflate the "work to do" number). For topic stacks, counts
    the number of stacks (not items) — that's the actionable "you have N
    lists" number.
    """
    cutoff_today = today or date.today()
    cutoff_tomorrow = cutoff_today + timedelta(days=1)
    active_statuses = [models.TaskStatus.pending, models.TaskStatus.in_progress]

    def pending_count_for_date(d: date) -> int:
        stmt = (
            select(func.count(models.Task.id))
            .join(models.Stack)
            .where(
                models.Task.user_id == current_user.id,
                models.Stack.user_id == current_user.id,
                models.Stack.stack_date == d,
                models.Task.status.in_(active_statuses),
            )
        )
        return int(db.execute(stmt).scalar() or 0)

    topic_count = int(
        db.execute(
            select(func.count(models.Stack.id)).where(
                models.Stack.user_id == current_user.id,
                models.Stack.kind != models.StackKind.daily,
            )
        ).scalar()
        or 0
    )

    return schemas.StackCounts(
        today=pending_count_for_date(cutoff_today),
        tomorrow=pending_count_for_date(cutoff_tomorrow),
        topic_stacks=topic_count,
    )


@router.get("/{stack_date}", response_model=schemas.StackOut)
def get_stack(
    stack_date: date,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Read-only. Returns an empty synthetic stack if none exists for this date.

    Creation only happens via PATCH /stacks/{date} (set intention) or
    POST /tasks (first task for the date).
    """
    stack = find_stack(db, current_user.id, stack_date)
    if stack is None:
        return _empty_stack_response(stack_date)
    return stack


@router.patch("/{stack_date}", response_model=schemas.StackOut)
def update_stack(
    stack_date: date,
    payload: schemas.StackUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        # Nothing to update; don't create an empty row.
        stack = find_stack(db, current_user.id, stack_date)
        if stack is None:
            return _empty_stack_response(stack_date)
        return stack

    stack = get_or_create_stack(db, current_user.id, stack_date)
    if "intention" in fields:
        stack.intention = fields["intention"]
    db.commit()
    db.refresh(stack)
    return stack
