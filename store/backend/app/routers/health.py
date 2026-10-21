from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.config import Settings
from app.deps import get_db, get_settings
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> HealthOut:
    """Liveness check. Tests poll this until the free-tier instance has woken up, and CI
    compares `commit` with the pushed commit to know the new deploy is live."""
    db.execute(text("SELECT 1"))
    return HealthOut(status="ok", version=__version__, database="ok", commit=settings.commit)
