"""Endpoints that exist only to support automated testing. All require X-Test-Token."""

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy import func, select

from app.bugs import BUG_DESCRIPTIONS, token_matches
from app.config import Settings
from app.deps import api_error, get_settings
from app.models import Coupon, Product, User
from app.schemas import BugSwitchOut, ErrorResponse, ResetOut
from app.seed import reset_database

router = APIRouter(
    prefix="/test",
    tags=["test-support"],
    responses={401: {"model": ErrorResponse}},
)


def require_test_token(
    x_test_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not token_matches(x_test_token, settings.test_token):
        raise api_error(
            status.HTTP_401_UNAUTHORIZED, "invalid_test_token", "Valid X-Test-Token required"
        )


@router.post("/reset", response_model=ResetOut, dependencies=[Depends(require_test_token)])
def reset(request: Request) -> ResetOut:
    """Restore the deterministic seed state."""
    state = request.app.state
    reset_database(state.engine, state.session_factory, state.settings)
    with state.session_factory() as fresh:
        return ResetOut(
            status="reset",
            products=fresh.scalar(select(func.count()).select_from(Product)),
            users=fresh.scalar(select(func.count()).select_from(User)),
            coupons=fresh.scalar(select(func.count()).select_from(Coupon)),
        )


@router.get("/bugs", response_model=list[BugSwitchOut], dependencies=[Depends(require_test_token)])
def list_bugs() -> list[BugSwitchOut]:
    """List every available bug switch and what it breaks."""
    return [
        BugSwitchOut(name=bug.value, description=desc) for bug, desc in BUG_DESCRIPTIONS.items()
    ]
