"""FastAPI application factory.

Run with: ``uvicorn handler.api.app:create_app --factory``. The UI and any future
integration are just clients of this — same contract as ``curl``. When ``ui_enabled``
(the default) the bundled web UI (Phase 3) is served same-origin from ``/`` and
``/static``; the shell is a client of the very same API, so no contract changes.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..builtin_skills import seed_builtin_skills
from ..config import get_settings
from ..db.engine import connection
from .routes import (
    agents,
    approvals,
    auth,
    claude,
    commands,
    hosts,
    interaction,
    login,
    memory,
    projects,
    schedules,
    shared,
)

_STATIC_DIR = Path(__file__).parent / "static"

_log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Seed the built-in operator skills (idempotent by name; operator edits and
    # disables survive). Best-effort: a failure here (e.g. migrations applied
    # out-of-band and not yet run) must not keep the API from serving.
    try:
        with connection() as conn:
            created = seed_builtin_skills(conn)
        if created:
            _log.info("seeded built-in skills: %s", ", ".join(created))
    except Exception:  # pragma: no cover - defensive; seeding retries next boot
        _log.warning("could not seed built-in skills", exc_info=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Handler API",
        version="0.1.0",
        summary="Read layer over the Handler control database.",
        lifespan=_lifespan,
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(agents.router)
    app.include_router(interaction.router)
    app.include_router(approvals.router)
    app.include_router(commands.router)
    app.include_router(login.router)
    app.include_router(claude.router)
    app.include_router(hosts.router)
    app.include_router(schedules.router)
    app.include_router(shared.router)
    app.include_router(memory.router)

    # Optional CORS, only for operators who host the UI on a different origin than the
    # API. Empty CORS_ORIGINS => middleware never added => behaviour identical to headless.
    if settings.cors_origin_list:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    # Serve the bundled Next.js static export same-origin. It is mounted at "/" *after*
    # every API router, so it is a fallback, not a shadow: Starlette matches the explicit
    # API routes (registered above) first and only unmatched paths — "/", the exported
    # HTML, and the "/_next/*" assets — fall through to StaticFiles. A missing file still
    # 404s (no SPA catch-all rewrite), so unknown API-looking paths behave as before.
    # The shell holds no data; all data comes from the authed API calls the browser makes
    # after the operator supplies the token.
    if settings.ui_enabled and _STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="ui")

    return app


app = create_app()
