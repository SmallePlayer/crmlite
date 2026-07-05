import math

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from templates_env import templates
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from config import BASE_DIR
from database import get_db
from helpers import _user_context
from models.user import User
from models.audit import AuditLog

router = APIRouter()


@router.get("/audit", response_class=HTMLResponse)
def audit_page(
    request: Request,
    action: str = Query(""),
    user_id: str = Query(""),
    page: int = Query(1),
    session: Session = Depends(get_db),
):
    from datetime import timedelta
    u = request.state.user
    if not u or u.role.name != "admin":
        raise HTTPException(403)

    q = select(AuditLog)
    if action.strip():
        q = q.where(AuditLog.action == action.strip())
    if user_id.strip():
        q = q.where(AuditLog.user_id == int(user_id.strip()))
    q = q.order_by(desc(AuditLog.created_at))

    PER_PAGE = 50
    total = session.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    pages = max(1, math.ceil(total / PER_PAGE))
    page = max(1, min(page, pages))
    logs = session.execute(q.offset((page - 1) * PER_PAGE).limit(PER_PAGE)).scalars().all()

    actions = session.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action).order_by(desc(func.count(AuditLog.id)))
    ).all()

    audit_users = session.execute(
        select(User).where(User.id.in_(
            select(AuditLog.user_id).where(AuditLog.user_id.isnot(None)).distinct()
        )).order_by(User.full_name)
    ).scalars().all()

    return templates.TemplateResponse(request, "audit.html", {
        **_user_context(request, session),
        "logs": logs, "page": page, "pages": pages, "total": total,
        "current_action": action.strip(), "current_user_id": user_id.strip(),
        "actions": actions, "audit_users": audit_users, "timedelta": timedelta,
    })
