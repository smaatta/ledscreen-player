"""
LedscreenPlayer — FastAPI application
Run with:  uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db, SessionLocal
from backend.routes import media, playlists, schedule, player, settings

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
PLAYER_DIR = os.path.join(BASE_DIR, "player")
MEDIA_DIR  = os.path.join(BASE_DIR, "media")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    asyncio.create_task(player.schedule_tick(SessionLocal))
    yield
    # Shutdown (nothing special needed)


app = FastAPI(
    title       = "LedscreenPlayer",
    description = "Raspberry Pi digital signage for Linsn SB-8 LED sender",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# ── Static files ──────────────────────────────────────────────────────────────
app.mount("/static",              StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media/uploads",       StaticFiles(directory=os.path.join(MEDIA_DIR, "uploads")),    name="uploads")
app.mount("/media/thumbnails",    StaticFiles(directory=os.path.join(MEDIA_DIR, "thumbnails")), name="thumbnails")

# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(media.router)
app.include_router(playlists.router)
app.include_router(schedule.router)
app.include_router(player.router)
app.include_router(settings.router)


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
async def admin_ui():
    """Serve the management SPA."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/player", include_in_schema=False)
async def player_ui():
    """Serve the fullscreen kiosk player page."""
    return FileResponse(os.path.join(PLAYER_DIR, "index.html"))
