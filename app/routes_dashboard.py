from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Order, Client, Lead, WorkReport, Attendance, User
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_str = now.strftime("%Y-%m-%d")

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

    recent_orders = (
        db.query(Order)
        .filter(Order.status.in_(["active", "done"]))
        .order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_orders": total_orders,
        "active_orders": active_orders,
        "done_orders": done_orders,
        "delivered_orders": delivered_orders,
        "month_income": round(month_income, 2),
        "total_clients": total_clients,
        "total_leads": total_leads,
        "new_leads": new_leads,
        "total_employees": total_employees,
        "checked_in_today": checked_in_today,
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
    }
