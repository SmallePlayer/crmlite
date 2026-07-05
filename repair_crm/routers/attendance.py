import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from config import BASE_DIR, TIMEZONE_OFFSET
from database import get_db
from helpers import _audit, _user_context
from models.user import User
from models.attendance import Attendance, Schedule

router = APIRouter()


@router.get("/attendance", response_class=HTMLResponse)
def attendance_page(request: Request, month: str = Query(""), session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    today = datetime.utcnow() + TIMEZONE_OFFSET
    today_str = today.strftime("%Y-%m-%d")
    if month:
        try:
            year, mon = map(int, month.split("-"))
            base = datetime(year, mon, 1)
        except (ValueError, TypeError):
            base = today.replace(day=1)
    else:
        base = today.replace(day=1)
    next_month = (base.replace(day=28) + timedelta(days=4)).replace(day=1)
    prev_month = (base - timedelta(days=1)).replace(day=1)
    base_m = base.strftime("%Y-%m")
    next_m = next_month.strftime("%Y-%m")

    users = session.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    ).scalars().all()

    from sqlalchemy.orm import joinedload
    attendances = session.execute(
        select(Attendance).options(joinedload(Attendance.user))
        .where(Attendance.date_str >= base_m, Attendance.date_str < next_m)
        .order_by(desc(Attendance.created_at))
    ).unique().scalars().all()

    schedules = session.execute(
        select(Schedule).options(joinedload(Schedule.user))
        .where(Schedule.date >= base, Schedule.date < next_month)
        .order_by(Schedule.date, Schedule.time_from)
    ).unique().scalars().all()

    by_user_date = {}
    today_att = {}
    for a in attendances:
        by_user_date.setdefault(a.user_id, {})[a.date_str] = a
        if a.date_str == today_str:
            today_att[a.user_id] = a

    sched_map = {}
    for s in schedules:
        d = s.date.strftime("%Y-%m-%d") if isinstance(s.date, datetime) else str(s.date)[:10]
        sched_map.setdefault(d, []).append(s)

    work_hours = {}
    for a in attendances:
        if a.check_out:
            delta = (a.check_out - a.check_in).total_seconds()
            if delta > 0:
                uid = a.user_id
                if uid not in work_hours:
                    work_hours[uid] = {"hours": 0.0, "days": 0}
                work_hours[uid]["hours"] += delta / 3600
                work_hours[uid]["days"] += 1

    return templates.TemplateResponse(request, "attendance.html", {
        **_user_context(request, session),
        "users": users, "base_month": base, "next_month": next_month, "prev_month": prev_month,
        "by_user_date": by_user_date, "today_att": today_att, "today": today,
        "current_user_id": u.id, "sched_map": sched_map, "timedelta": timedelta,
        "now_utc": datetime.utcnow(), "work_hours": work_hours,
    })


@router.post("/attendance/check-in")
def check_in(request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    today_str = (datetime.utcnow() + TIMEZONE_OFFSET).strftime("%Y-%m-%d")
    existing = session.execute(
        select(Attendance).where(Attendance.user_id == u.id, Attendance.date_str == today_str)
    ).scalar_one_or_none()
    if existing:
        return RedirectResponse("/attendance", status_code=303)
    session.add(Attendance(user_id=u.id, date_str=today_str, check_in=datetime.utcnow()))
    session.commit()
    _audit("check_in", "attendance", None, f"{u.full_name} пришёл", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/check-out")
def check_out(request: Request, report: str = Form(""), session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    today_str = (datetime.utcnow() + TIMEZONE_OFFSET).strftime("%Y-%m-%d")
    a = session.execute(
        select(Attendance).where(Attendance.user_id == u.id, Attendance.date_str == today_str)
    ).scalar_one_or_none()
    if a and not a.check_out:
        a.check_out = datetime.utcnow()
        a.report = report.strip()
        session.commit()
        _audit("check_out", "attendance", None, f"{u.full_name} ушёл", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/cancel")
def cancel_check_in(request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    today_str = (datetime.utcnow() + TIMEZONE_OFFSET).strftime("%Y-%m-%d")
    a = session.execute(
        select(Attendance).where(Attendance.user_id == u.id, Attendance.date_str == today_str)
    ).scalar_one_or_none()
    if a and not a.check_out:
        session.delete(a)
        session.commit()
        _audit("cancel_check_in", "attendance", None, f"{u.full_name} отменил", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/edit")
def edit_attendance(request: Request, check_in: str = Form(""), check_out: str = Form(""),
                    report: str = Form(""), session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    today_str = (datetime.utcnow() + TIMEZONE_OFFSET).strftime("%Y-%m-%d")
    today_dt = (datetime.utcnow() + TIMEZONE_OFFSET).replace(hour=0, minute=0, second=0, microsecond=0)
    a = session.execute(
        select(Attendance).where(Attendance.user_id == u.id, Attendance.date_str == today_str)
    ).scalar_one_or_none()
    if not a: raise HTTPException(400, "Нет отметки за сегодня")
    if check_in.strip():
        try:
            h, m = map(int, check_in.split(":"))
            a.check_in = today_dt.replace(hour=h, minute=m) - TIMEZONE_OFFSET
        except ValueError: pass
    if check_out.strip():
        try:
            h, m = map(int, check_out.split(":"))
            a.check_out = today_dt.replace(hour=h, minute=m) - TIMEZONE_OFFSET
        except ValueError: pass
    a.report = report.strip()
    session.commit()
    _audit("edit_attendance", "attendance", a.id, f"{u.full_name}", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/{att_id}/admin-edit")
def admin_edit_attendance(att_id: int, request: Request, check_in: str = Form(""),
                          check_out: str = Form(""), report: str = Form(""),
                          session: Session = Depends(get_db)):
    u = request.state.user
    if not u or u.role.name != "admin": raise HTTPException(403)
    a = session.get(Attendance, att_id)
    if not a: raise HTTPException(404)
    base_date = a.date_str
    if check_in.strip():
        try:
            h, m = map(int, check_in.split(":"))
            dt = datetime.strptime(f"{base_date} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M")
            a.check_in = dt - TIMEZONE_OFFSET
        except ValueError: pass
    if check_out.strip():
        try:
            h, m = map(int, check_out.split(":"))
            dt = datetime.strptime(f"{base_date} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M")
            a.check_out = dt - TIMEZONE_OFFSET
        except ValueError: pass
    a.report = report.strip()
    session.commit()
    _audit("admin_edit_attendance", "attendance", att_id, f"{u.full_name}", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/admin/check-in")
def admin_check_in(request: Request, user_id: int = Form(...), date_str: str = Form(""),
                   check_in_time: str = Form(""), check_out_time: str = Form(""),
                   session: Session = Depends(get_db)):
    u = request.state.user
    if not u or u.role.name != "admin": raise HTTPException(403)
    target_user = session.get(User, user_id)
    if not target_user: raise HTTPException(404, "Пользователь не найден")
    if not date_str:
        date_str = (datetime.utcnow() + TIMEZONE_OFFSET).strftime("%Y-%m-%d")
    existing = session.execute(
        select(Attendance).where(Attendance.user_id == user_id, Attendance.date_str == date_str)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"У {target_user.full_name} уже есть отметка на {date_str}")
    if check_in_time.strip():
        try:
            h, m = map(int, check_in_time.split(":"))
            dt = datetime.strptime(f"{date_str} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M") - TIMEZONE_OFFSET
        except ValueError:
            dt = datetime.utcnow()
    else:
        dt = datetime.utcnow()
    att = Attendance(user_id=user_id, date_str=date_str, check_in=dt)
    if check_out_time.strip():
        try:
            h, m = map(int, check_out_time.split(":"))
            att.check_out = datetime.strptime(f"{date_str} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M") - TIMEZONE_OFFSET
        except ValueError:
            pass
    session.add(att)
    session.commit()
    action = "отметил" if not check_out_time.strip() else "создал смену для"
    _audit("admin_check_in", "attendance", att.id, f"{u.full_name} {action} {target_user.full_name}", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/{att_id}/admin-cancel")
def admin_cancel_attendance(att_id: int, request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u or u.role.name != "admin": raise HTTPException(403)
    a = session.get(Attendance, att_id)
    if not a: raise HTTPException(404)
    user_name = a.user.full_name if a.user else "?"
    session.delete(a)
    session.commit()
    _audit("admin_cancel_attendance", "attendance", att_id, f"{u.full_name} отменил для {user_name}", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/attendance/{att_id}/admin-check-out")
def admin_check_out(att_id: int, request: Request, report: str = Form(""),
                    session: Session = Depends(get_db)):
    u = request.state.user
    if not u or u.role.name != "admin": raise HTTPException(403)
    a = session.get(Attendance, att_id)
    if not a: raise HTTPException(404)
    a.check_out = datetime.utcnow()
    if report.strip():
        a.report = report.strip()
    session.commit()
    user_name = a.user.full_name if a.user else "?"
    _audit("admin_check_out", "attendance", att_id, f"{u.full_name} завершил смену {user_name}", u, session)
    return RedirectResponse("/attendance", status_code=303)
