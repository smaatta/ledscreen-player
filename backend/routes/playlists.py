"""Playlist CRUD and item ordering routes."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.database import get_db, Playlist, PlaylistItem, Media

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


class PlaylistCreate(BaseModel):
    name: str
    description: str = ""


class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None


class ItemAdd(BaseModel):
    media_id: int
    duration: int = 10
    transition: str = "fade"


class ItemUpdate(BaseModel):
    duration: Optional[int] = None
    transition: Optional[str] = None


class ItemsReorder(BaseModel):
    item_ids: List[int]


@router.get("")
def list_playlists(db: Session = Depends(get_db)):
    playlists = db.query(Playlist).order_by(Playlist.created_at).all()
    return [p.to_dict() for p in playlists]


@router.post("")
def create_playlist(body: PlaylistCreate, db: Session = Depends(get_db)):
    pl = Playlist(name=body.name, description=body.description)
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return pl.to_dict(include_items=True)


@router.get("/{playlist_id}")
def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    pl = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return pl.to_dict(include_items=True)


@router.patch("/{playlist_id}")
def update_playlist(playlist_id: int, body: PlaylistUpdate, db: Session = Depends(get_db)):
    pl = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if body.name is not None:
        pl.name = body.name
    if body.description is not None:
        pl.description = body.description
    if body.is_default is not None:
        pl.is_default = body.is_default
    pl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pl)
    return pl.to_dict(include_items=True)


@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    pl = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if pl.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default playlist")
    db.delete(pl)
    db.commit()
    return {"ok": True}


# ── Playlist Items ────────────────────────────────────────────────────────────

@router.post("/{playlist_id}/items")
def add_item(playlist_id: int, body: ItemAdd, db: Session = Depends(get_db)):
    pl = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    media = db.query(Media).filter(Media.id == body.media_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")

    max_order = max((item.order for item in pl.items), default=-1)
    item = PlaylistItem(
        playlist_id = playlist_id,
        media_id    = body.media_id,
        order       = max_order + 1,
        duration    = body.duration,
        transition  = body.transition,
    )
    db.add(item)
    pl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item.to_dict()


@router.patch("/{playlist_id}/items/{item_id}")
def update_item(playlist_id: int, item_id: int, body: ItemUpdate, db: Session = Depends(get_db)):
    item = db.query(PlaylistItem).filter(
        PlaylistItem.id == item_id,
        PlaylistItem.playlist_id == playlist_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.duration is not None:
        item.duration = body.duration
    if body.transition is not None:
        item.transition = body.transition
    db.commit()
    db.refresh(item)
    return item.to_dict()


@router.delete("/{playlist_id}/items/{item_id}")
def remove_item(playlist_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.query(PlaylistItem).filter(
        PlaylistItem.id == item_id,
        PlaylistItem.playlist_id == playlist_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    pl = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if pl:
        pl.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{playlist_id}/items/reorder")
def reorder_items(playlist_id: int, body: ItemsReorder, db: Session = Depends(get_db)):
    """Reorder by providing the full list of item_ids in the desired order."""
    for idx, item_id in enumerate(body.item_ids):
        item = db.query(PlaylistItem).filter(
            PlaylistItem.id == item_id,
            PlaylistItem.playlist_id == playlist_id
        ).first()
        if item:
            item.order = idx
    pl = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if pl:
        pl.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
