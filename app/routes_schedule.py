from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Schedule, WorkReport, User, Task
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api", tags=["schedule"], dependencies=[Depends(get_current_user)])


class ScheduleCreate(BaseModel):
    date: str
    time_from: str
    time_to: str


class ScheduleOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    date: str
    time_from: str
    time_to: str

    class Config:
        from_attributes = True


@router.get("/schedule", response_model=List[ScheduleOut])
def list_schedule(date: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Schedule).options(joinedload(Schedule.user))
    if date:
        q = q.filter(Schedule.date == date)
    records = q.order_by(Schedule.date, Schedule.time_from).all()
    return [
        ScheduleOut(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user.full_name or r.user.username,
            date=r.date,
            time_from=r.time_from,
            time_to=r.time_to,
        )
        for r in records
    ]


@router.post("/schedule", response_model=ScheduleOut)
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rec = Schedule(user_id=user.id, date=data.date, time_from=data.time_from, time_to=data.time_to)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    rec = db.query(Schedule).options(joinedload(Schedule.user)).get(rec.id)
    return ScheduleOut(
        id=rec.id,
        user_id=rec.user_id,
        user_name=rec.user.full_name or rec.user.username,
        date=rec.date,
        time_from=rec.time_from,
        time_to=rec.time_to,
    )


@router.delete("/schedule/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    rec = db.query(Schedule).get(schedule_id)
    if not rec:
        raise HTTPException(404, "Запись не найдена")
    db.delete(rec)
    db.commit()
    return {"ok": True}


@router.get("/report/summary")
def report_summary(
    user_id: Optional[int] = None,
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(WorkReport).options(
        joinedload(WorkReport.user),
        joinedload(WorkReport.task),
    )
    if current_user.role.name != "admin" and not user_id:
        q = q.filter(WorkReport.user_id == current_user.id)
    if user_id:
        q = q.filter(WorkReport.user_id == user_id)
    if date_from:
        q = q.filter(WorkReport.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(WorkReport.created_at <= datetime.fromisoformat(date_to) + timedelta(days=1))
    reports = q.all()
    total = sum(r.quantity * r.task.price for r in reports)
    by_user = {}
    for r in reports:
        uname = r.user.full_name or r.user.username
        if uname not in by_user:
            by_user[uname] = 0
        by_user[uname] += r.quantity * r.task.price
    return {
        "total": round(total, 2),
        "count": len(reports),
        "by_user": {k: round(v, 2) for k, v in by_user.items()},
    }
