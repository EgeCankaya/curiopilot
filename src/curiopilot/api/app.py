"""FastAPI application factory for CurioPilot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from curiopilot.config import AppConfig, load_config
from curiopilot.storage.article_store import ArticleStore
from curiopilot.storage.url_store import URLStore

log = logging.getLogger(__name__)


def create_app(config_path: str | Path = "config.yaml") -> FastAPI:
    """Build and return a fully configured FastAPI application."""
    config = load_config(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db_dir = Path(config.paths.database_dir)
        db_path = db_dir / "curiopilot.db"

        article_store = ArticleStore(db_path)
        await article_store.open()

        url_store = URLStore(db_path)
        await url_store.open()

        app.state.config = config
        app.state.config_path = config_path
        app.state.article_store = article_store
        app.state.url_store = url_store

        log.info("CurioPilot API started (db: %s)", db_path)
        yield

        await article_store.close()
        await url_store.close()
        log.info("CurioPilot API shut down")

    app = FastAPI(
        title="CurioPilot",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:19231"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_routes(app)
    _mount_frontend(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Import and mount all API routers."""
    from curiopilot.api.routes.articles import router as articles_router
    from curiopilot.api.routes.briefings import router as briefings_router
    from curiopilot.api.routes.feedback import router as feedback_router
    from curiopilot.api.routes.pipeline import router as pipeline_router
    from curiopilot.api.routes.search import router as search_router
    from curiopilot.api.routes.stats import router as stats_router

    app.include_router(briefings_router, prefix="/api")
    app.include_router(articles_router, prefix="/api")
    app.include_router(feedback_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")
    app.include_router(search_router, prefix="/api")
    app.include_router(pipeline_router, prefix="/api")


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built frontend SPA with catch-all fallback."""
    frontend_dir = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    if not frontend_dir.is_dir():
        log.info("Frontend dist not found at %s – skipping static mount", frontend_dir)
        return

    index_html = frontend_dir / "index.html"

    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        file_path = frontend_dir / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index_html)
