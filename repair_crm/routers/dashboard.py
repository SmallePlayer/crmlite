from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR, ORDER_STATUSES, ORDER_TYPES
from database import get_db
from helpers import _user_context
from models.user import User
from models.client import Client
from models.service import Service
from models.warehouse import Part, Product
from models.order import Order
from models.task import Task
from models.audit import AuditLog

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    active = session.execute(
        select(func.count(Order.id)).where(Order.status == "in_progress")
    ).scalar() or 0
    closed = session.execute(
        select(func.count(Order.id)).where(Order.status == "closed")
    ).scalar() or 0
    total_clients = session.execute(select(func.count(Client.id))).scalar() or 0
    total_services = session.execute(select(func.count(Service.id))).scalar() or 0
    total_parts = session.execute(select(func.count(Part.id))).scalar() or 0
    total_products = session.execute(select(func.count(Product.id))).scalar() or 0
    overdue = session.execute(
        select(func.count(Order.id))
        .where(Order.status != "closed", Order.deadline.isnot(None), Order.deadline < func.now())
    ).scalar() or 0
    due_soon = session.execute(
        select(func.count(Order.id))
        .where(Order.status != "closed", Order.deadline.isnot(None),
               Order.deadline >= func.now(), Order.deadline < func.now() + timedelta(days=3))
    ).scalar() or 0
    low_stock = session.execute(
        select(func.count(Part.id))
        .where(Part.quantity <= Part.min_stock, Part.min_stock > 0)
    ).scalar() or 0
    my_tasks = session.execute(
        select(func.count(Task.id))
        .where(Task.assigned_to == u.id, Task.status == "pending")
    ).scalar() or 0
    total_tasks = session.execute(
        select(func.count(Task.id)).where(Task.status == "pending")
    ).scalar() or 0
    recent = session.execute(
        select(Order).options(joinedload(Order.client))
        .order_by(desc(Order.created_at)).limit(15)
    ).unique().scalars().all()
    my_recent_tasks = session.execute(
        select(Task).options(joinedload(Task.creator), joinedload(Task.assignee))
        .where(Task.assigned_to == u.id, Task.status == "pending")
        .order_by(desc(Task.created_at)).limit(5)
    ).unique().scalars().all()
    recent_logs = session.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(10)
    ).scalars().all() if u.role.name == "admin" else []
    return templates.TemplateResponse(request, "index.html", {
        **_user_context(request, session),
        "active_orders": active, "closed_orders": closed,
        "total_clients": total_clients, "total_services": total_services,
        "total_parts": total_parts, "total_products": total_products,
        "low_stock": low_stock, "overdue": overdue, "due_soon": due_soon,
        "my_tasks": my_tasks, "total_tasks": total_tasks,
        "my_recent_tasks": my_recent_tasks,
        "recent_orders": recent, "recent_logs": recent_logs,
        "ORDER_STATUSES": ORDER_STATUSES, "ORDER_TYPES": ORDER_TYPES,
        "datetime": datetime,
        "last_backup": (datetime.fromtimestamp((BASE_DIR / "repair_crm.db").stat().st_mtime)
                        if (BASE_DIR / "repair_crm.db").exists() else None),
        "backup_days": ((datetime.utcnow() - datetime.fromtimestamp((BASE_DIR / "repair_crm.db").stat().st_mtime)).days
                        if (BASE_DIR / "repair_crm.db").exists() else 0),
    })
