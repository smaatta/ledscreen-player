"""
LedscreenPlayer — Database models and setup
Uses SQLite via SQLAlchemy (sync, for simplicity on Pi)
"""

import os
import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "ledplayer.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Models ────────────────────────────────────────────────────────────────────

class Media(Base):
    __tablename__ = "media"

    id            = Column(Integer, primary_key=True, index=True)
    filename      = Column(String, unique=True, nullable=False)   # stored filename
    original_name = Column(String, nullable=False)
    media_type    = Column(String, nullable=False)                 # image | video | widget
    file_path     = Column(String, nullable=False)
    thumbnail     = Column(String, nullable=True)
    size_bytes    = Column(Integer, default=0)
    width         = Column(Integer, nullable=True)
    height        = Column(Integer, nullable=True)
    duration_secs = Column(Float, nullable=True)                  # for video
    widget_config = Column(Text, nullable=True)                   # JSON for widgets
    created_at    = Column(DateTime, default=datetime.utcnow)

    playlist_items = relationship("PlaylistItem", back_populates="media", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":            self.id,
            "filename":      self.filename,
            "original_name": self.original_name,
            "media_type":    self.media_type,
            "file_path":     self.file_path,
            "thumbnail":     self.thumbnail,
            "size_bytes":    self.size_bytes,
            "width":         self.width,
            "height":        self.height,
            "duration_secs": self.duration_secs,
            "widget_config": json.loads(self.widget_config) if self.widget_config else None,
            "created_at":    self.created_at.isoformat(),
        }


class Playlist(Base):
    __tablename__ = "playlists"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    description = Column(String, default="")
    is_default  = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items     = relationship("PlaylistItem", back_populates="playlist",
                             order_by="PlaylistItem.order", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="playlist", cascade="all, delete-orphan")

    def to_dict(self, include_items=False):
        d = {
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "is_default":  self.is_default,
            "item_count":  len(self.items),
            "created_at":  self.created_at.isoformat(),
            "updated_at":  self.updated_at.isoformat(),
        }
        if include_items:
            d["items"] = [item.to_dict() for item in self.items]
        return d


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id          = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    media_id    = Column(Integer, ForeignKey("media.id"), nullable=False)
    order       = Column(Integer, default=0)
    duration    = Column(Integer, default=10)    # display seconds (images/widgets)
    transition  = Column(String, default="fade") # fade | slide | none
    loop        = Column(Boolean, default=False) # loop video indefinitely

    playlist = relationship("Playlist", back_populates="items")
    media    = relationship("Media", back_populates="playlist_items")

    def to_dict(self):
        return {
            "id":          self.id,
            "playlist_id": self.playlist_id,
            "media_id":    self.media_id,
            "order":       self.order,
            "duration":    self.duration,
            "transition":  self.transition,
            "loop":        self.loop,
            "media":       self.media.to_dict() if self.media else None,
        }


class Schedule(Base):
    __tablename__ = "schedules"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=False)
    start_time  = Column(String, nullable=False)   # "HH:MM"
    end_time    = Column(String, nullable=False)   # "HH:MM"
    days        = Column(String, default="0,1,2,3,4,5,6")  # comma-sep weekday ints
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    playlist = relationship("Playlist", back_populates="schedules")

    def to_dict(self):
        return {
            "id":          self.id,
            "name":        self.name,
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist.name if self.playlist else None,
            "start_time":  self.start_time,
            "end_time":    self.end_time,
            "days":        [int(d) for d in self.days.split(",")],
            "is_active":   self.is_active,
            "created_at":  self.created_at.isoformat(),
        }


class PlayerState(Base):
    __tablename__ = "player_state"

    id                 = Column(Integer, primary_key=True, default=1)
    active_playlist_id = Column(Integer, ForeignKey("playlists.id"), nullable=True)
    is_paused          = Column(Boolean, default=False)
    brightness         = Column(Integer, default=100)   # 0–100
    volume             = Column(Integer, default=50)    # 0–100
    updated_at         = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "active_playlist_id": self.active_playlist_id,
            "is_paused":          self.is_paused,
            "brightness":         self.brightness,
            "volume":             self.volume,
            "updated_at":         self.updated_at.isoformat(),
        }


def init_db():
    """Create all tables and seed with a default playlist."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Ensure a default playlist exists
        if not db.query(Playlist).first():
            default_pl = Playlist(name="Default Playlist", description="Auto-created default", is_default=True)
            db.add(default_pl)
            db.flush()
            # Seed player state
            state = PlayerState(id=1, active_playlist_id=default_pl.id)
            db.add(state)
            db.commit()
    finally:
        db.close()
