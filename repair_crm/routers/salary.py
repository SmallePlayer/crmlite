from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from templates_env import templates
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload

from config import TIMEZONE_OFFSET
from database import get_db
from helpers import _user_context
from models.user import User
from models.attendance import Attendance

router = APIRouter()


@router.get("/salary", response_class=HTMLResponse)
def salary_page(request: Request, month: str = Query(""), session: Session = Depends(get_db)):
    u = request.state.user
    if not u or u.role.name != "admin":
        raise HTTPException(403)
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

    attendances = session.execute(
        select(Attendance).options(joinedload(Attendance.user))
        .where(Attendance.date_str >= base_m, Attendance.date_str < next_m)
        .order_by(desc(Attendance.created_at))
    ).unique().scalars().all()

    salary_data = []
    for user in users:
        user_attendances = [a for a in attendances if a.user_id == user.id]
        total_hours = 0.0
        total_days = 0
        for a in user_attendances:
            if a.check_out and a.check_in:
                delta = (a.check_out - a.check_in).total_seconds()
                if delta > 0:
                    total_hours += delta / 3600
                    total_days += 1
        hourly_rate = user.hourly_rate or 0
        total_salary = total_hours * hourly_rate
        salary_data.append({
            "user": user,
            "total_hours": total_hours,
            "total_days": total_days,
            "hourly_rate": hourly_rate,
            "total_salary": total_salary,
        })

    total_fund = sum(s["total_salary"] for s in salary_data)

    return templates.TemplateResponse(request, "salary.html", {
        **_user_context(request, session),
        "salary_data": salary_data,
        "base_month": base,
        "next_month": next_month,
        "prev_month": prev_month,
        "total_fund": total_fund,
        "today": today,
    })
