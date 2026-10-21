from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.deps import api_error, get_current_user, get_db, get_settings
from app.models import User
from app.schemas import ErrorResponse, LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
def register(
    body: RegisterIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> User:
    """Create a customer account. Admin accounts are only created by the seed."""
    if db.scalar(select(User).where(User.email == body.email)) is not None:
        raise api_error(status.HTTP_409_CONFLICT, "email_taken", "Email is already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password, settings.bcrypt_rounds),
        full_name=body.full_name,
        role="customer",
    )
    db.add(user)
    db.commit()
    return user


@router.post("/login", response_model=TokenOut, responses={401: {"model": ErrorResponse}})
def login(
    body: LoginIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> TokenOut:
    """Exchange email + password for a JWT. Logout is client-side: the client discards the token."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Same error for unknown email and wrong password, so attackers can't enumerate accounts.
    if user is None or not verify_password(body.password, user.password_hash):
        raise api_error(
            status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Invalid email or password"
        )
    token = create_access_token(
        user.id, user.role, settings.jwt_secret, settings.jwt_expire_minutes
    )
    return TokenOut(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserOut, responses={401: {"model": ErrorResponse}})
def me(user: User = Depends(get_current_user)) -> User:
    """Return the logged-in user."""
    return user
