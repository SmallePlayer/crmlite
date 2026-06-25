from datetime import datetime, timedelta, date as date_module
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Order, Client, Lead, WorkReport, Attendance, User, Task
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(period: str = "month", db: Session = Depends(get_db), user=Depends(get_current_user)):
    now = datetime.now()
    if period == "today":
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        period_start = now - timedelta(days=now.weekday())
        period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_str = now.strftime("%Y-%m-%d")
    is_admin = user.role and user.role.name == "admin"

    total_orders = db.query(func.count(Order.id)).scalar() or 0
    active_orders = db.query(func.count(Order.id)).filter(Order.status == "active").scalar() or 0
    done_orders = db.query(func.count(Order.id)).filter(Order.status == "done").scalar() or 0
    delivered_orders = db.query(func.count(Order.id)).filter(Order.status == "delivered").scalar() or 0

    period_income = (
        db.query(func.coalesce(func.sum(Order.total_price), 0))
        .filter(Order.created_at >= period_start, Order.status == "delivered")
        .scalar()
        or 0
    )

    user_month_income = (
        db.query(func.coalesce(func.sum(WorkReport.quantity * Task.price), 0))
        .select_from(WorkReport)
        .join(WorkReport.task)
        .filter(WorkReport.user_id == user.id, WorkReport.created_at >= period_start)
        .scalar()
        or 0
    ) if not is_admin else 0

    total_clients = db.query(func.count(Client.id)).scalar() or 0
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    new_leads = db.query(func.count(Lead.id)).filter(Lead.status == "new").scalar() or 0
    total_employees = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    checked_in_today = (
        db.query(func.count(Attendance.id))
        .filter(Attendance.date == today_str, Attendance.check_out.is_(None))
        .scalar()
        or 0
    )

    my_reports_today = (
        db.query(func.count(WorkReport.id))
        .filter(WorkReport.user_id == user.id, WorkReport.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0))
        .scalar()
        or 0
    )

    recent_orders = (
        db.query(Order)
        .filter(Order.status.in_(["active", "done"]))
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )

    recent_leads = (
        db.query(Lead)
        .order_by(Lead.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "is_admin": is_admin,
        "total_orders": total_orders,
        "active_orders": active_orders,
        "done_orders": done_orders,
        "delivered_orders": delivered_orders,
        "month_income": round(period_income, 2),
        "user_month_income": round(user_month_income, 2),
        "total_clients": total_clients,
        "total_leads": total_leads,
        "new_leads": new_leads,
        "total_employees": total_employees,
        "checked_in_today": checked_in_today,
        "my_reports_today": my_reports_today,
        "period_label": {"today": "за сегодня", "week": "за неделю", "month": "за месяц", "year": "за год"}.get(period, "за месяц"),
        "recent_orders": [
            {
                "id": o.id,
                "client_name": o.client_name,
                "order_type": o.order_type,
                "status": o.status,
                "total_price": o.total_price,
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ],
        "recent_leads": [
            {
                "id": l.id,
                "name": l.name,
                "phone": l.phone,
                "service_type": l.service_type,
                "status": l.status,
                "created_at": l.created_at.isoformat(),
            }
            for l in recent_leads
        ],
        "chart_orders": _chart_orders(db),
        "chart_income": _chart_income(db),
    }


def _chart_orders(db: Session):
    days = 14
    result = []
    for i in range(days - 1, -1, -1):
        d = date_module.today() - timedelta(days=i)
        total = db.query(func.count(Order.id)).filter(func.date(Order.created_at) == d).scalar() or 0
        result.append({"date": d.isoformat(), "total": total})
    return result


def _chart_income(db: Session):
    months = 6
    result = []
    now = datetime.now()
    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        start = datetime(y, m, 1)
        if m == 12:
            end = datetime(y + 1, 1, 1)
        else:
            end = datetime(y, m + 1, 1)
        income = db.query(func.coalesce(func.sum(Order.total_price), 0)).filter(
            Order.created_at >= start, Order.created_at < end, Order.status == "delivered"
        ).scalar() or 0
        result.append({"month": f"{y}-{m:02d}", "income": round(income, 2)})
    return result
