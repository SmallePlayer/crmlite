from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Attendance, User
from app.auth import get_current_user, require_admin
from app.audit import log

router = APIRouter(prefix="/api/attendance", tags=["attendance"], dependencies=[Depends(get_current_user)])


class AttendanceOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    date: str
    check_in: str
    check_out: Optional[str] = None
    report_text: Optional[str] = None

    class Config:
        from_attributes = True


class CheckoutData(BaseModel):
    report_text: str = ""


@router.get("", response_model=List[AttendanceOut])
def list_attendance(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Attendance).options(joinedload(Attendance.user))
    if user.role.name != "admin":
        q = q.filter(Attendance.user_id == user.id)
    records = q.order_by(Attendance.created_at.desc()).all()
    return [_att_out(r) for r in records]


@router.post("/checkin", response_model=AttendanceOut)
def check_in(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")
    existing = db.query(Attendance).filter(
        Attendance.user_id == user.id,
        Attendance.date == today,
    ).first()
    if existing:
        raise HTTPException(400, "Вы уже отметились сегодня")
    record = Attendance(user_id=user.id, date=today, check_in=now)
    db.add(record)
    db.commit()
    db.refresh(record)
    log(user, "create", "attendance", record.id, f"Отметка о приходе {today} {now}", db=db)
    record = db.query(Attendance).options(joinedload(Attendance.user)).get(record.id)
    return _att_out(record)


@router.post("/checkout", response_model=AttendanceOut)
def check_out(data: CheckoutData, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")
    record = db.query(Attendance).filter(
        Attendance.user_id == user.id,
        Attendance.date == today,
    ).first()
    if not record:
        raise HTTPException(404, "Нет отметки о приходе сегодня")
    if record.check_out:
        raise HTTPException(400, "Вы уже отметили уход")
    record.check_out = now
    record.report_text = data.report_text
    db.commit()
    db.refresh(record)
    log(user, "update", "attendance", record.id, f"Отметка об уходе {today} {now}", db=db)
    record = db.query(Attendance).options(joinedload(Attendance.user)).get(record.id)
    return _att_out(record)


@router.delete("/{record_id}")
def delete_attendance(record_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    record = db.query(Attendance).get(record_id)
    if not record:
        raise HTTPException(404, "Запись не найдена")
    db.delete(record)
    db.commit()
    log(_, "delete", "attendance", record_id, f"Удалена запись посещаемости #{record_id}", db=db)
    return {"ok": True}


def _att_out(r: Attendance) -> AttendanceOut:
    return AttendanceOut(
        id=r.id,
        user_id=r.user_id,
        user_name=r.user.full_name or r.user.username,
        date=r.date,
        check_in=r.check_in,
        check_out=r.check_out,
        report_text=r.report_text,
    )
