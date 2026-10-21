from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.deps import get_db
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    """Liveness check. Tests poll this until the free-tier instance has woken up."""
    db.execute(text("SELECT 1"))
    return HealthOut(status="ok", version=__version__, database="ok")
