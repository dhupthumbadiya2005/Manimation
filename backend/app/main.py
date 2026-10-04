"""FastAPI app: JSON API under /api, rendered media under /media, and the built
React app (frontend/dist) at / when it exists.

    uv run uvicorn app.main:app --reload            # dev (frontend via `npm run dev`)
    MANIMATION_DEMO=1 uv run uvicorn app.main:app   # no API calls, answers from the cookbook
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api.events import EventHub
from app.api.jobs import JobRunner
from app.api.routes import router

FRONTEND_DIST = config.REPO_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.hub.bind(asyncio.get_running_loop())
    for name in ("httpx2", "httpx", "anthropic"):
        logging.getLogger(name).setLevel(logging.WARNING)
    yield
    app.state.runner.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="MANImation Studio", lifespan=lifespan)
    app.state.hub = EventHub()
    app.state.runner = JobRunner(app.state.hub)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    media = config.settings.data_dir
    media.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media), name="media")

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith(("api/", "media/")):
                raise HTTPException(404, "not found")  # unknown API/media paths never fall through to the UI
            file = (FRONTEND_DIST / path).resolve()
            if path and file.is_file() and file.is_relative_to(FRONTEND_DIST.resolve()):
                return FileResponse(file)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
