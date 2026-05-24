"""Public, no-auth-required endpoints — shareable stacks.

Kept in its own router so the auth-required /stacks routes can't accidentally
leak something here, and so the openapi schema makes the distinction obvious.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db
from ..security import check_public_read_rate_limit

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/stacks/{slug}", response_model=schemas.PublicStackOut)
def get_public_stack(slug: str, request: Request, db: Session = Depends(get_db)):
    check_public_read_rate_limit(request)
    """Read-only view of a shared stack.

    Only returns the stack if both is_public is true AND share_slug matches.
    Once unshared, the slug stops resolving until re-shared (keeping the
    same slug per the Notion-style lifecycle decision).

    Owner-internal task state (status, completed_at, in_progress timer,
    accumulated_seconds, ids) is NOT exposed — see PublicTaskOut.
    """
    stmt = (
        select(models.Stack)
        .where(
            models.Stack.share_slug == slug,
            models.Stack.is_public.is_(True),
            models.Stack.kind != models.StackKind.daily,
        )
        .options(selectinload(models.Stack.tasks))
    )
    stack = db.execute(stmt).scalar_one_or_none()
    if stack is None:
        raise HTTPException(status_code=404, detail="Stack not found")

    owner = db.get(models.User, stack.user_id)

    # Hide done/cancelled tasks — the public view shows what's queued,
    # not the operational state of the owner's workflow.
    visible_tasks = [
        t
        for t in stack.tasks
        if t.status in (models.TaskStatus.pending, models.TaskStatus.in_progress)
    ]
    visible_tasks.sort(key=lambda t: t.position)

    return schemas.PublicStackOut(
        kind=stack.kind,
        name=stack.name or "",
        intention=stack.intention,
        owner_display_name=(owner.display_name if owner else None),
        tasks=[schemas.PublicTaskOut.model_validate(t) for t in visible_tasks],
    )
