"""Database engine and session factory (SQLite via SQLAlchemy 2.x)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> Engine:
    # FastAPI runs sync endpoints in a thread pool, so SQLite must allow cross-thread use.
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if database_url in ("sqlite://", "sqlite:///:memory:"):
        # An in-memory DB lives inside one connection; StaticPool shares that connection.
        kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
