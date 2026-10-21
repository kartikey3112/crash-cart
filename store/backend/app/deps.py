"""Shared FastAPI dependencies: settings, DB session, current user, active bug switches."""

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.bugs import Bug
from app.config import Settings
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Every business error has the same shape: {"detail": {"code": ..., "message": ...}}."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def bug_on(request: Request, bug: Bug) -> bool:
    # request.state.bugs is filled in by the bug-switch middleware in main.py.
    return bug in request.state.bugs


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "not_authenticated", "message": "Missing or invalid access token"},
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials, settings.jwt_secret)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise api_error(status.HTTP_403_FORBIDDEN, "forbidden", "Admin access required")
    return user
