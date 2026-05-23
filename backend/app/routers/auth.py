from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .. import auth as auth_service
from .. import models
from ..database import get_db
from ..security import check_login_rate_limit, check_signup_rate_limit


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None
    onboarded_at: datetime | None = None

    @computed_field
    @property
    def onboarded(self) -> bool:
        return self.onboarded_at is not None


def _issue_session(
    db: DbSession, user: models.User, request: Request, response: Response
) -> UserOut:
    ua = request.headers.get("user-agent")
    _, token = auth_service.create_session(db, user, user_agent=ua)
    auth_service.set_session_cookie(response, token)
    return UserOut.model_validate(user)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
):
    check_signup_rate_limit(request)
    existing = db.execute(
        select(models.User).where(models.User.email == payload.email.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = models.User(
        email=payload.email.lower(),
        password_hash=auth_service.hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_session(db, user, request, response)


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
):
    check_login_rate_limit(request, payload.email)
    user = db.execute(
        select(models.User).where(models.User.email == payload.email.lower())
    ).scalar_one_or_none()
    if user is None or not auth_service.verify_password(payload.password, user.password_hash):
        # Same message for both cases to avoid revealing whether email is registered.
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return _issue_session(db, user, request, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: DbSession = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias=auth_service.SESSION_COOKIE_NAME),
):
    if session_token:
        auth_service.revoke_session(db, session_token)
    auth_service.clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(auth_service.get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    db: DbSession = Depends(get_db),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    # exclude_unset → distinguish "field omitted" from "field=null".
    # display_name is nullable, so null clears it.
    fields = payload.model_dump(exclude_unset=True)
    if "display_name" in fields:
        value = fields["display_name"]
        current_user.display_name = value.strip() if isinstance(value, str) else value
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    db: DbSession = Depends(get_db),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    # Verify the current password BEFORE allowing the change. Without this a
    # hijacked session could lock the real owner out by changing their password.
    if not auth_service.verify_password(
        payload.current_password, current_user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400, detail="New password must differ from the current one"
        )
    current_user.password_hash = auth_service.hash_password(payload.new_password)
    db.commit()


@router.post("/me/onboarded", response_model=UserOut)
def complete_onboarding(
    db: DbSession = Depends(get_db),
    current_user: models.User = Depends(auth_service.get_current_user),
):
    """Mark the first-run onboarding tips as dismissed for this user.

    Idempotent: re-calling on an already-onboarded user is a no-op (we keep
    the original timestamp so we know when they first finished).
    """
    if current_user.onboarded_at is None:
        current_user.onboarded_at = _now()
        db.commit()
        db.refresh(current_user)
    return current_user
