"""App factory. Run locally with:  uvicorn app.main:app --reload"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.bugs import UnknownBugError, parse_bug_header
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.routers import admin, auth, cart, checkout, health, orders, products, test_support
from app.seed import reset_database

BUG_HEADER = "X-Bug-Switches"
TOKEN_HEADER = "X-Test-Token"
ACTIVE_BUGS_HEADER = "X-Bug-Switches-Active"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Every start begins from the seed state; on Render the disk is ephemeral anyway.
        reset_database(engine, session_factory, settings)
        yield
        engine.dispose()

    app = FastAPI(
        title="CrashCart Store API",
        version=__version__,
        description="A fictional store built to be tested. Payments are fake.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.middleware("http")
    async def bug_switches(request: Request, call_next):
        """Decide which bugs (if any) are on for this request, and echo them back so a
        test can confirm the switch really took effect."""
        try:
            bugs = parse_bug_header(
                request.headers.get(BUG_HEADER),
                request.headers.get(TOKEN_HEADER),
                settings.test_token,
            )
        except UnknownBugError as exc:
            return JSONResponse(
                status_code=400, content={"detail": {"code": "unknown_bug", "message": str(exc)}}
            )
        request.state.bugs = bugs
        response = await call_next(request)
        if bugs:
            response.headers[ACTIVE_BUGS_HEADER] = ",".join(sorted(bugs))
        return response

    # Added after the bug middleware so it wraps it: CORS headers appear even on 400s.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            BUG_HEADER,
            TOKEN_HEADER,
        ],
        expose_headers=[ACTIVE_BUGS_HEADER],
    )

    for module in (health, auth, products, cart, checkout, orders, admin, test_support):
        app.include_router(module.router)
    return app


app = create_app()
