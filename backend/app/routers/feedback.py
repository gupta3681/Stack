"""User-submitted feedback. Single POST endpoint; the admin read path
lives in `routers/admin.py` since it's gated separately."""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session as DbSession

from .. import auth as auth_service
from .. import models
from ..database import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    # 1-5 inclusive. The DB also enforces this via CheckConstraint so even
    # a non-Pydantic client can't write out-of-range values.
    rating: int = Field(ge=1, le=5)
    # Free-text. Generous limits so users can be detailed if they want.
    # Both fields optional — the rating alone is a valid submission.
    comments: str | None = Field(default=None, max_length=5000)
    bugs: str | None = Field(default=None, max_length=5000)


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rating: int
    comments: str | None
    bugs: str | None
    created_at: datetime


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    payload: FeedbackCreate,
    db: DbSession = Depends(get_db),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Capture feedback from the logged-in user.

    Accepts both cookie and bearer auth — a CLI / agent that wants to
    pipe in user feedback works too. No rate limit yet; if it becomes
    abusive we add per-user throttle here.
    """
    row = models.Feedback(
        user_id=current_user.id,
        rating=payload.rating,
        comments=(payload.comments or "").strip() or None,
        bugs=(payload.bugs or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
