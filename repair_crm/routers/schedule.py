from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, or_
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR, TIMEZONE_OFFSET, ORDER_STATUSES
from database import get_db
from helpers import _audit, _user_context
from models.user import User
from models.attendance import Schedule
from models.order import Order
from models.client import Client

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.post("/schedule")
def save_schedule(request: Request, user_id: int = Form(0), date: str = Form(""),
                  time_from: str = Form(""), time_to: str = Form(""),
                  session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    target = session.get(User, user_id or u.id)
    if not target: raise HTTPException(400)
    try: d = datetime.strptime(date, "%Y-%m-%d")
    except ValueError: raise HTTPException(400, "Неверная дата")
    if not time_from or not time_to: raise HTTPException(400, "Укажите время")
    session.add(Schedule(user_id=target.id, date=d, time_from=time_from, time_to=time_to))
    session.commit()
    _audit("add_schedule", "schedule", None, f"{target.full_name} {date} {time_from}-{time_to}", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/schedule/bulk")
def bulk_schedule(request: Request, user_id: int = Form(0), date_from: str = Form(""),
                  date_to: str = Form(""), time_from: str = Form(""), time_to: str = Form(""),
                  workdays_only: str = Form("0"), session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    target = session.get(User, user_id or u.id)
    if not target: raise HTTPException(400)
    if not time_from or not time_to: raise HTTPException(400, "Укажите время")
    try:
        d_from = datetime.strptime(date_from, "%Y-%m-%d")
        d_to = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError: raise HTTPException(400, "Неверная дата")
    if d_to < d_from: raise HTTPException(400, "Дата «по» раньше даты «с»")
    count = 0
    cur = d_from
    while cur <= d_to:
        if workdays_only != "1" or cur.weekday() < 5:
            session.add(Schedule(user_id=target.id, date=cur, time_from=time_from, time_to=time_to))
            count += 1
        cur += timedelta(days=1)
    session.commit()
    _audit("bulk_schedule", "schedule", None, f"{target.full_name} {date_from}–{date_to} ({count} см.)", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/schedule/{sched_id}/edit")
def edit_schedule(sched_id: int, request: Request, date: str = Form(""),
                  time_from: str = Form(""), time_to: str = Form(""),
                  session: Session = Depends(get_db)):
    u = request.state.user
    if not u: raise HTTPException(403)
    s = session.get(Schedule, sched_id)
    if not s: raise HTTPException(404)
    try: d = datetime.strptime(date, "%Y-%m-%d")
    except ValueError: raise HTTPException(400, "Неверная дата")
    if not time_from or not time_to: raise HTTPException(400, "Укажите время")
    s.date = d; s.time_from = time_from; s.time_to = time_to
    session.commit()
    _audit("edit_schedule", "schedule", s.id, f"{s.user.full_name} {date} {time_from}-{time_to}", u, session)
    return RedirectResponse("/attendance", status_code=303)


@router.post("/schedule/{sched_id}/delete")
def delete_schedule(sched_id: int, request: Request, session: Session = Depends(get_db)):
    s = session.get(Schedule, sched_id)
    if not s: raise HTTPException(404)
    session.delete(s)
    session.commit()
    _audit("delete", "schedule", sched_id, s.user.full_name, request.state.user, session)
    return RedirectResponse("/attendance", status_code=303)


@router.get("/schedule", response_class=HTMLResponse)
def schedule_calendar_page(request: Request, month: str = Query(""), session: Session = Depends(get_db)):
    today = datetime.utcnow() + TIMEZONE_OFFSET
    if month:
        try:
            year, mon = map(int, month.split("-"))
            base = datetime(year, mon, 1)
        except (ValueError, TypeError):
            base = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        base = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    next_month = (base.replace(day=28) + timedelta(days=4)).replace(day=1)
    prev_month = (base - timedelta(days=1)).replace(day=1)

    orders = session.execute(
        select(Order).options(joinedload(Order.client), joinedload(Order.assignee))
        .where(
            or_(
                Order.scheduled_at.isnot(None),
                (Order.deadline.isnot(None)) & (Order.order_type == "print")
            ),
            or_(
                (Order.scheduled_at >= base) & (Order.scheduled_at < next_month),
                (Order.deadline >= base) & (Order.deadline < next_month) & (Order.order_type == "print")
            )
        )
        .order_by(Order.scheduled_at)
    ).unique().scalars().all()

    by_date = {}
    orders_json = {}
    for o in orders:
        if o.scheduled_at:
            d = o.scheduled_at.strftime("%Y-%m-%d")
            by_date.setdefault(d, []).append(o)
            orders_json.setdefault(d, []).append({
                "id": o.id, "client_name": o.client.full_name if o.client else "—",
                "printer": o.printer or "", "status": o.status,
                "order_type": o.order_type or "repair",
                "scheduled_at": o.scheduled_at.isoformat() if o.scheduled_at else "",
                "schedule_location": o.schedule_location or "",
            })
        if o.order_type == "print" and o.deadline:
            d = o.deadline.strftime("%Y-%m-%d")
            by_date.setdefault(d, []).append(o)
            if d not in orders_json or o.id not in [x["id"] for x in orders_json[d]]:
                orders_json.setdefault(d, []).append({
                    "id": o.id, "client_name": o.client.full_name if o.client else "—",
                    "printer": o.printer or "", "status": o.status,
                    "order_type": o.order_type or "repair",
                    "scheduled_at": o.deadline.isoformat() if o.deadline else "",
                    "schedule_location": o.schedule_location or "",
                })

    return templates.TemplateResponse(request, "schedule.html", {
        **_user_context(request, session),
        "orders_by_date": by_date, "orders_json": orders_json,
        "base_month": base, "next_month": next_month,
        "prev_month": prev_month, "today": today,
        "ORDER_STATUSES": ORDER_STATUSES, "timedelta": timedelta,
    })
