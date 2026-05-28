"""
Player control routes + WebSocket endpoint.
The kiosk browser connects via WebSocket to receive real-time playlist updates.
"""

import json
import asyncio
from datetime import datetime
from typing import Set
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.database import get_db, PlayerState, Playlist, Schedule

router = APIRouter(prefix="/api/player", tags=["player"])

# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, data: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        self.active -= dead


manager = ConnectionManager()


async def push_player_update(db: Session):
    """Build the current player payload and broadcast to all connected clients."""
    state = db.query(PlayerState).filter(PlayerState.id == 1).first()
    if not state:
        return

    playlist = None
    if state.active_playlist_id:
        pl = db.query(Playlist).filter(Playlist.id == state.active_playlist_id).first()
        if pl:
            playlist = pl.to_dict(include_items=True)

    await manager.broadcast({
        "type":      "player_update",
        "state":     state.to_dict(),
        "playlist":  playlist,
        "server_ts": datetime.utcnow().isoformat(),
    })


# ── REST endpoints ────────────────────────────────────────────────────────────

class PlayerControl(BaseModel):
    active_playlist_id: Optional[int] = None
    is_paused:          Optional[bool] = None
    brightness:         Optional[int] = None
    volume:             Optional[int] = None


@router.get("/state")
def get_state(db: Session = Depends(get_db)):
    state = db.query(PlayerState).filter(PlayerState.id == 1).first()
    if not state:
        raise HTTPException(status_code=404, detail="Player state not initialised")
    playlist = None
    if state.active_playlist_id:
        pl = db.query(Playlist).filter(Playlist.id == state.active_playlist_id).first()
        if pl:
            playlist = pl.to_dict(include_items=True)
    return {"state": state.to_dict(), "playlist": playlist}


@router.patch("/state")
async def update_state(body: PlayerControl, db: Session = Depends(get_db)):
    state = db.query(PlayerState).filter(PlayerState.id == 1).first()
    if not state:
        raise HTTPException(status_code=404, detail="Player state not initialised")

    if body.active_playlist_id is not None:
        pl = db.query(Playlist).filter(Playlist.id == body.active_playlist_id).first()
        if not pl:
            raise HTTPException(status_code=404, detail="Playlist not found")
        state.active_playlist_id = body.active_playlist_id
    if body.is_paused is not None:
        state.is_paused = body.is_paused
    if body.brightness is not None:
        state.brightness = max(0, min(100, body.brightness))
    if body.volume is not None:
        state.volume = max(0, min(100, body.volume))

    state.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(state)

    await push_player_update(db)

    return state.to_dict()


@router.post("/next")
async def skip_next(db: Session = Depends(get_db)):
    """Signal the player to skip to the next item."""
    await manager.broadcast({"type": "command", "cmd": "next"})
    return {"ok": True}


@router.post("/prev")
async def skip_prev(db: Session = Depends(get_db)):
    """Signal the player to go to the previous item."""
    await manager.broadcast({"type": "command", "cmd": "prev"})
    return {"ok": True}


# ── Schedule ticker ───────────────────────────────────────────────────────────

async def schedule_tick(db_factory):
    """Background coroutine: check schedules every 30 s and switch playlists."""
    while True:
        await asyncio.sleep(30)
        db = db_factory()
        try:
            now        = datetime.now()
            time_str   = now.strftime("%H:%M")
            weekday    = now.weekday()   # 0=Mon … 6=Sun

            best: Optional[Schedule] = None
            for s in db.query(Schedule).filter(Schedule.is_active == True).all():
                days = [int(d) for d in s.days.split(",")]
                if weekday not in days:
                    continue
                if s.start_time <= time_str < s.end_time:
                    best = s
                    break

            if best:
                state = db.query(PlayerState).filter(PlayerState.id == 1).first()
                if state and state.active_playlist_id != best.playlist_id:
                    state.active_playlist_id = best.playlist_id
                    state.updated_at = datetime.utcnow()
                    db.commit()
                    await push_player_update(db)
        finally:
            db.close()


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def player_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    # Send current state immediately on connect
    state = db.query(PlayerState).filter(PlayerState.id == 1).first()
    playlist = None
    if state and state.active_playlist_id:
        pl = db.query(Playlist).filter(Playlist.id == state.active_playlist_id).first()
        if pl:
            playlist = pl.to_dict(include_items=True)
    await websocket.send_json({
        "type":     "player_update",
        "state":    state.to_dict() if state else {},
        "playlist": playlist,
        "server_ts": datetime.utcnow().isoformat(),
    })
    try:
        while True:
            # Keep alive — clients send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
