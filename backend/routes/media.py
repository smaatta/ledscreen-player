"""Media upload, listing, and deletion routes."""

import os
import uuid
import json
import shutil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db, Media

router = APIRouter(prefix="/api/media", tags=["media"])

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "media", "uploads")
THUMB_DIR  = os.path.join(BASE_DIR, "media", "thumbnails")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
VIDEO_EXTS = {".mp4", ".webm", ".ogg", ".mov", ".avi", ".mkv"}

ALLOWED_EXTS = IMAGE_EXTS | VIDEO_EXTS


def _get_media_type(ext: str) -> str:
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "unknown"


def _try_get_image_dimensions(path: str):
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _try_make_thumbnail(src: str, dest: str, size=(320, 180)):
    try:
        from PIL import Image
        with Image.open(src) as img:
            img.thumbnail(size)
            img.save(dest)
        return True
    except Exception:
        return False


@router.get("")
def list_media(db: Session = Depends(get_db)):
    items = db.query(Media).order_by(Media.created_at.desc()).all()
    return [m.to_dict() for m in items]


@router.post("")
async def upload_media(
    file: UploadFile = File(...),
    duration: int    = Form(10),
    db: Session      = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported.")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    dest_path   = os.path.join(UPLOAD_DIR, unique_name)

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size   = os.path.getsize(dest_path)
    mtype  = _get_media_type(ext)
    w, h   = (None, None)
    thumb  = None

    if mtype == "image":
        w, h = _try_get_image_dimensions(dest_path)
        thumb_name = f"thumb_{unique_name}"
        thumb_path = os.path.join(THUMB_DIR, thumb_name)
        if _try_make_thumbnail(dest_path, thumb_path):
            thumb = f"/media/thumbnails/{thumb_name}"

    media = Media(
        filename      = unique_name,
        original_name = file.filename,
        media_type    = mtype,
        file_path     = f"/media/uploads/{unique_name}",
        thumbnail     = thumb,
        size_bytes    = size,
        width         = w,
        height        = h,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media.to_dict()


@router.post("/widget")
def create_widget(
    name:          str  = Form(...),
    widget_type:   str  = Form(...),   # clock | weather | text | rss
    config:        str  = Form("{}"),  # JSON string
    db: Session         = Depends(get_db),
):
    try:
        cfg = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="config must be valid JSON")

    unique_name = f"widget_{uuid.uuid4().hex}.json"
    media = Media(
        filename      = unique_name,
        original_name = name,
        media_type    = "widget",
        file_path     = "",
        widget_config = json.dumps({"type": widget_type, **cfg}),
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media.to_dict()


@router.get("/{media_id}")
def get_media(media_id: int, db: Session = Depends(get_db)):
    m = db.query(Media).filter(Media.id == media_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Media not found")
    return m.to_dict()


@router.delete("/{media_id}")
def delete_media(media_id: int, db: Session = Depends(get_db)):
    m = db.query(Media).filter(Media.id == media_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Media not found")

    # Remove files
    for rel_path in [m.file_path, m.thumbnail]:
        if rel_path:
            abs_path = os.path.join(BASE_DIR, rel_path.lstrip("/"))
            if os.path.exists(abs_path):
                os.remove(abs_path)

    db.delete(m)
    db.commit()
    return {"ok": True}
