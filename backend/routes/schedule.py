"""Schedule routes — define when each playlist plays."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.database import get_db, Schedule, Playlist

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    name: str
    playlist_id: int
    start_time: str          # "HH:MM"
    end_time: str            # "HH:MM"
    days: List[int] = [0, 1, 2, 3, 4, 5, 6]   # 0=Mon … 6=Sun
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    playlist_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days: Optional[List[int]] = None
    is_active: Optional[bool] = None


@router.get("")
def list_schedules(db: Session = Depends(get_db)):
    schedules = db.query(Schedule).order_by(Schedule.start_time).all()
    return [s.to_dict() for s in schedules]


@router.post("")
def create_schedule(body: ScheduleCreate, db: Session = Depends(get_db)):
    pl = db.query(Playlist).filter(Playlist.id == body.playlist_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")

    s = Schedule(
        name        = body.name,
        playlist_id = body.playlist_id,
        start_time  = body.start_time,
        end_time    = body.end_time,
        days        = ",".join(str(d) for d in body.days),
        is_active   = body.is_active,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s.to_dict()


@router.get("/{schedule_id}")
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s.to_dict()


@router.patch("/{schedule_id}")
def update_schedule(schedule_id: int, body: ScheduleUpdate, db: Session = Depends(get_db)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if body.name is not None:
        s.name = body.name
    if body.playlist_id is not None:
        s.playlist_id = body.playlist_id
    if body.start_time is not None:
        s.start_time = body.start_time
    if body.end_time is not None:
        s.end_time = body.end_time
    if body.days is not None:
        s.days = ",".join(str(d) for d in body.days)
    if body.is_active is not None:
        s.is_active = body.is_active
    db.commit()
    db.refresh(s)
    return s.to_dict()


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(s)
    db.commit()
    return {"ok": True}
