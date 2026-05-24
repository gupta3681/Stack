from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from .stacks import find_topic_stack, get_or_create_stack

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _resolve_target_stack_id(
    db: Session,
    user_id: int,
    stack_date: date | None,
    stack_id: int | None,
) -> int | None:
    """Translate the (stack_date | stack_id) input from a payload into a
    concrete stack_id (or None for backlog). Enforces ownership and exclusivity."""
    if stack_date is not None and stack_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Provide either stack_date or stack_id, not both.",
        )
    if stack_id is not None:
        stack = find_topic_stack(db, user_id, stack_id)
        if stack is None:
            raise HTTPException(status_code=404, detail="Stack not found")
        return stack.id
    if stack_date is not None:
        return get_or_create_stack(db, user_id, stack_date).id
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _commit_elapsed_if_running(task: models.Task) -> None:
    if task.in_progress_started_at is None:
        return
    elapsed = (_now() - task.in_progress_started_at).total_seconds()
    task.accumulated_seconds = (task.accumulated_seconds or 0) + max(0, int(elapsed))
    task.in_progress_started_at = None


def _get_owned_task(db: Session, task_id: int, user_id: int) -> models.Task:
    task = db.get(models.Task, task_id)
    if task is None or task.user_id != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _resolve_insert_position(
    db: Session, user_id: int, stack_id: int | None, hint: models.PriorityHint | None
) -> int:
    if stack_id is None:
        return _next_position(db, user_id, stack_id=None)

    if hint == models.PriorityHint.top:
        _shift_positions_from(db, user_id, stack_id, from_position=0, by=1)
        return 0
    if hint == models.PriorityHint.high:
        count = _count_tasks(db, user_id, stack_id)
        target = min(1, count)
        _shift_positions_from(db, user_id, stack_id, from_position=target, by=1)
        return target
    return _next_position(db, user_id, stack_id)


def _next_position(db: Session, user_id: int, stack_id: int | None) -> int:
    stmt = select(models.Task.position).where(
        models.Task.user_id == user_id, models.Task.stack_id == stack_id
    )
    positions = db.execute(stmt).scalars().all()
    return (max(positions) + 1) if positions else 0


def _count_tasks(db: Session, user_id: int, stack_id: int) -> int:
    stmt = select(models.Task).where(
        models.Task.user_id == user_id, models.Task.stack_id == stack_id
    )
    return len(db.execute(stmt).scalars().all())


def _shift_positions_from(
    db: Session, user_id: int, stack_id: int, from_position: int, by: int
) -> None:
    stmt = select(models.Task).where(
        models.Task.user_id == user_id,
        models.Task.stack_id == stack_id,
        models.Task.position >= from_position,
    )
    for task in db.execute(stmt).scalars().all():
        task.position += by


def _shift_in_range(
    db: Session, user_id: int, stack_id: int, low: int, high: int, by: int
) -> None:
    stmt = select(models.Task).where(
        models.Task.user_id == user_id,
        models.Task.stack_id == stack_id,
        models.Task.position >= low,
        models.Task.position <= high,
    )
    for task in db.execute(stmt).scalars().all():
        task.position += by


@router.get("/backlog", response_model=list[schemas.TaskOut])
def get_backlog(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stmt = (
        select(models.Task)
        .where(models.Task.user_id == current_user.id, models.Task.stack_id.is_(None))
        .order_by(models.Task.position, models.Task.created_at)
    )
    return db.execute(stmt).scalars().all()


@router.post("", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stack_id = _resolve_target_stack_id(
        db, current_user.id, payload.stack_date, payload.stack_id
    )

    position = _resolve_insert_position(
        db, current_user.id, stack_id, payload.priority_hint
    )
    task = models.Task(
        user_id=current_user.id,
        stack_id=stack_id,
        name=payload.name,
        context_md=payload.context_md,
        direct_link=payload.direct_link,
        due_at=payload.due_at,
        priority_hint=payload.priority_hint,
        position=position,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_task(db, task_id, current_user.id)


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    # exclude_unset lets us distinguish "field omitted" (preserve) from
    # "field=null" (clear). For non-nullable columns (name, status) we still
    # ignore null; for nullable columns (context_md, due_at) we honor it.
    fields = payload.model_dump(exclude_unset=True)

    if "name" in fields and fields["name"] is not None:
        task.name = fields["name"]
    if "context_md" in fields:
        task.context_md = fields["context_md"]
    if "direct_link" in fields:
        task.direct_link = fields["direct_link"]
    if "due_at" in fields:
        task.due_at = fields["due_at"]
    if "priority_hint" in fields:
        # Hint is purely informational once the task exists; position is set at
        # creation time and changed via drag/reorder, not via PATCH.
        task.priority_hint = fields["priority_hint"]
    if "status" in fields and fields["status"] is not None:
        task.status = fields["status"]
        if fields["status"] == models.TaskStatus.done:
            _commit_elapsed_if_running(task)
            if task.completed_at is None:
                task.completed_at = _now()
        elif fields["status"] == models.TaskStatus.cancelled:
            # Cancelling preserves completed_at — a previously-done task that
            # gets cancelled shouldn't lose its completion timestamp.
            _commit_elapsed_if_running(task)
        else:
            task.completed_at = None
            if fields["status"] != models.TaskStatus.in_progress:
                _commit_elapsed_if_running(task)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    old_stack_id = task.stack_id
    old_position = task.position
    db.delete(task)
    if old_stack_id is not None:
        _shift_positions_from(
            db, current_user.id, old_stack_id, from_position=old_position + 1, by=-1
        )
    db.commit()


@router.post("/{task_id}/move", response_model=schemas.TaskOut)
def move_task(
    task_id: int,
    payload: schemas.TaskMove,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    old_stack_id = task.stack_id
    old_position = task.position

    new_stack_id = _resolve_target_stack_id(
        db, current_user.id, payload.stack_date, payload.stack_id
    )

    if old_stack_id is not None and old_stack_id != new_stack_id:
        _shift_positions_from(
            db, current_user.id, old_stack_id, from_position=old_position + 1, by=-1
        )

    target_position = (
        payload.position
        if payload.position is not None
        else _next_position(db, current_user.id, new_stack_id)
    )
    if new_stack_id is not None and (
        old_stack_id != new_stack_id or target_position != old_position
    ):
        if old_stack_id == new_stack_id:
            if target_position < old_position:
                _shift_in_range(
                    db, current_user.id, new_stack_id, target_position, old_position - 1, by=1
                )
            elif target_position > old_position:
                _shift_in_range(
                    db, current_user.id, new_stack_id, old_position + 1, target_position, by=-1
                )
        else:
            _shift_positions_from(
                db, current_user.id, new_stack_id, from_position=target_position, by=1
            )

    task.stack_id = new_stack_id
    task.position = target_position
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/start", response_model=schemas.TaskOut)
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    if task.in_progress_started_at is None:
        task.in_progress_started_at = _now()
    task.status = models.TaskStatus.in_progress
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/pause", response_model=schemas.TaskOut)
def pause_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_owned_task(db, task_id, current_user.id)
    _commit_elapsed_if_running(task)
    if task.status == models.TaskStatus.in_progress:
        task.status = models.TaskStatus.pending
    db.commit()
    db.refresh(task)
    return task


@router.post("/reorder", response_model=list[schemas.TaskOut])
def reorder_tasks(
    payload: schemas.TaskReorder,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Reorders the tasks in a single stack.

    `ordered_ids` MUST be the complete set of task IDs currently in the named
    stack (or the backlog if `stack_date` is None). This prevents partial or
    cross-stack reorders from corrupting positions.
    """
    # Resolve the target stack — same rules as create/move.
    if payload.stack_date is not None and payload.stack_id is not None:
        raise HTTPException(
            status_code=400, detail="Provide either stack_date or stack_id, not both."
        )
    if payload.stack_id is not None:
        stack = find_topic_stack(db, current_user.id, payload.stack_id)
        if stack is None:
            raise HTTPException(status_code=404, detail="Stack not found")
        target_stack_id: int | None = stack.id
    elif payload.stack_date is not None:
        from .stacks import find_stack
        stack = find_stack(db, current_user.id, payload.stack_date)
        if stack is None:
            raise HTTPException(status_code=404, detail="Stack not found")
        target_stack_id = stack.id
    else:
        target_stack_id = None

    # Load all tasks currently in the target stack (owned by the user)
    current_stmt = select(models.Task).where(
        models.Task.user_id == current_user.id,
        models.Task.stack_id.is_(None) if target_stack_id is None
        else models.Task.stack_id == target_stack_id,
    )
    current_tasks = db.execute(current_stmt).scalars().all()
    current_ids = {t.id for t in current_tasks}

    # Validate that `ordered_ids` is exactly the set of tasks in this stack —
    # no extras (cross-stack/foreign), no omissions (partial reorder).
    requested_ids = set(payload.ordered_ids)
    if requested_ids != current_ids:
        extra = sorted(requested_ids - current_ids)
        missing = sorted(current_ids - requested_ids)
        raise HTTPException(
            status_code=400,
            detail={
                "message": "ordered_ids must match exactly the tasks in this stack",
                "extra": extra,
                "missing": missing,
            },
        )

    tasks_by_id = {t.id: t for t in current_tasks}
    for new_position, task_id in enumerate(payload.ordered_ids):
        tasks_by_id[task_id].position = new_position
    db.commit()
    return [tasks_by_id[tid] for tid in payload.ordered_ids]
