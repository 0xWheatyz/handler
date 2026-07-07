"""FastAPI application factory.

Run with: ``uvicorn handler.api.app:create_app --factory``. The UI and any future
integration are just clients of this — same contract as ``curl``.
"""

from __future__ import annotations

from fastapi import FastAPI

from .routes import agents, interaction, projects, shared


def create_app() -> FastAPI:
    app = FastAPI(
        title="Handler API",
        version="0.1.0",
        summary="Read layer over the Handler control database.",
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(projects.router)
    app.include_router(agents.router)
    app.include_router(interaction.router)
    app.include_router(shared.router)
    return app


app = create_app()
