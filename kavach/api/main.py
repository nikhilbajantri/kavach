"""FastAPI entrypoint for the KAVACH gateway and the mounted mock systems."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kavach import __version__
from kavach.config import settings


def create_app() -> FastAPI:
    """Build the app. A factory keeps tests isolated from each other."""
    app = FastAPI(title="KAVACH Gateway", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "version": __version__, "kavach_enabled": settings.enabled}

    return app


app = create_app()
