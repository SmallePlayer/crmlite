from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Order, Client, Lead, WorkReport, Attendance, User, Task
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_str = now.strftime("%Y-%m-%d")
    is_admin = user.role and user.role.name == "admin"

    total_orders = db.query(func.count(Order.id)).scalar() or 0
    active_orders = db.query(func.count(Order.id)).filter(Order.status == "active").scalar() or 0
    done_orders = db.query(func.count(Order.id)).filter(Order.status == "done").scalar() or 0
    delivered_orders = db.query(func.count(Order.id)).filter(Order.status == "delivered").scalar() or 0

    month_income = (
        db.query(func.coalesce(func.sum(Order.total_price), 0))
        .filter(Order.created_at >= month_start, Order.status == "delivered")
        .scalar()
        or 0
    )

    user_month_income = (
        db.query(func.coalesce(func.sum(WorkReport.quantity * Task.price), 0))
        .select_from(WorkReport)
        .join(WorkReport.task)
        .filter(WorkReport.user_id == user.id, WorkReport.created_at >= month_start)
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
        "month_income": round(month_income, 2),
        "user_month_income": round(user_month_income, 2),
        "total_clients": total_clients,
        "total_leads": total_leads,
        "new_leads": new_leads,
        "total_employees": total_employees,
        "checked_in_today": checked_in_today,
        "my_reports_today": my_reports_today,
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
    }
