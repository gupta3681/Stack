from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .. import auth as auth_service
from .. import models
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None


def _issue_session(
    db: DbSession, user: models.User, request: Request, response: Response
) -> UserOut:
    ua = request.headers.get("user-agent")
    session = auth_service.create_session(db, user, user_agent=ua)
    auth_service.set_session_cookie(response, session.id)
    return UserOut.model_validate(user)


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
):
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
