from datetime import datetime
import json

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR, AVAILABLE_PERMISSIONS
from database import get_db
from helpers import _audit, _user_context, _hash_password, _validate_password
from models.user import User, Role
from models.task import Task
from models.chat import ChatMessage
from models.attendance import Attendance, Schedule
from models.order import Order

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request, session: Session = Depends(get_db)):
    from config import TIMEZONE_OFFSET
    u = request.state.user
    if not u or u.role.name != "admin":
        raise HTTPException(403)
    users = session.execute(
        select(User).options(joinedload(User.role)).order_by(User.username)
    ).unique().scalars().all()
    roles = session.execute(select(Role).order_by(Role.name)).scalars().all()
    return templates.TemplateResponse(request, "users.html", {
        **_user_context(request, session),
        "users": users, "roles": roles,
        "user_data": [{"id": x.id, "username": x.username, "full_name": x.full_name,
                        "role_name": x.role.name, "is_active": x.is_active,
                        "inn": x.inn or "", "position": x.position or "",
                        "last_login": (x.last_login + TIMEZONE_OFFSET).strftime("%d.%m.%Y %H:%M") if x.last_login else ""}
                       for x in users],
        "roles_data": [{"id": r.id, "name": r.name, "permissions": r.permissions} for r in roles],
        "timedelta": __import__("datetime").timedelta,
    })


@router.post("/roles")
async def create_role(
    request: Request,
    name: str = Form(...),
    session: Session = Depends(get_db),
):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    form = await request.form()
    perms = []
    for perm_key, _ in AVAILABLE_PERMISSIONS:
        if form.get(f"perm_{perm_key}") == "1":
            perms.append(perm_key)
    role = Role(name=name.strip(), permissions=json.dumps(perms))
    session.add(role)
    session.commit()
    _audit("create", "role", role.id, role.name, request.state.user, session)
    return RedirectResponse("/users", status_code=303)


@router.post("/roles/{role_id}/edit")
async def update_role(
    role_id: int, request: Request,
    name: str = Form(...),
    session: Session = Depends(get_db),
):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(404)
    if role.name == "admin":
        raise HTTPException(400, "Нельзя редактировать роль admin")
    form = await request.form()
    perms = []
    for perm_key, _ in AVAILABLE_PERMISSIONS:
        if form.get(f"perm_{perm_key}") == "1":
            perms.append(perm_key)
    role.name = name.strip()
    role.permissions = json.dumps(perms)
    session.commit()
    _audit("update", "role", role.id, role.name, request.state.user, session)
    return RedirectResponse("/users", status_code=303)


@router.post("/roles/{role_id}/delete")
def delete_role(role_id: int, request: Request, session: Session = Depends(get_db)):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    role = session.get(Role, role_id)
    if not role:
        raise HTTPException(404)
    if role.name == "admin":
        raise HTTPException(400, "Нельзя удалить роль admin")
    count = session.execute(
        select(func.count(User.id)).where(User.role_id == role_id)
    ).scalar()
    if count > 0:
        raise HTTPException(400, f"Роль используется {count} пользователями")
    session.delete(role)
    session.commit()
    _audit("delete", "role", role_id, role.name, request.state.user, session)
    return RedirectResponse("/users", status_code=303)


@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role_id: int = Form(...),
    inn: str = Form(""),
    position: str = Form(""),
    session: Session = Depends(get_db),
):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    existing = session.execute(
        select(User).where(User.username == username.strip())
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Пользователь с таким логином уже существует")
    pw = _validate_password(password)
    session.add(User(
        username=username.strip(),
        password_hash=_hash_password(pw),
        full_name=full_name.strip(),
        role_id=role_id,
        inn=inn.strip(),
        position=position.strip(),
    ))
    session.commit()
    _audit("create", "user", None, full_name.strip(), request.state.user, session)
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/edit")
def update_user(
    user_id: int, request: Request,
    full_name: str = Form(...),
    role_id: int = Form(...),
    inn: str = Form(""),
    position: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_db),
):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404)
    u.full_name = full_name.strip()
    u.role_id = role_id
    u.inn = inn.strip()
    u.position = position.strip()
    if password.strip():
        pw = _validate_password(password)
        u.password_hash = _hash_password(pw)
    session.commit()
    _audit("update", "user", u.id, u.full_name, request.state.user, session)
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, request: Request, session: Session = Depends(get_db)):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    u = session.get(User, user_id)
    if not u or u.username == "admin":
        raise HTTPException(400)
    u.is_active = not u.is_active
    session.commit()
    _audit("toggle", "user", u.id, f"{u.full_name} → {'active' if u.is_active else 'inactive'}", request.state.user, session)
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, request: Request, session: Session = Depends(get_db)):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    current = request.state.user
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404)
    if u.username == "admin":
        raise HTTPException(400, "Нельзя удалить администратора")
    if u.id == current.id:
        raise HTTPException(400, "Нельзя удалить самого себя")
    session.execute(select(Task).where(
        or_(Task.created_by == user_id, Task.assigned_to == user_id)
    ).with_for_update())
    for t in session.execute(
        select(Task).where(or_(Task.created_by == user_id, Task.assigned_to == user_id))
    ).scalars().all():
        session.delete(t)
    for m in session.execute(
        select(ChatMessage).where(ChatMessage.from_user_id == user_id)
    ).scalars().all():
        session.delete(m)
    for a in session.execute(
        select(Attendance).where(Attendance.user_id == user_id)
    ).scalars().all():
        session.delete(a)
    for s in session.execute(
        select(Schedule).where(Schedule.user_id == user_id)
    ).scalars().all():
        session.delete(s)
    for o in session.execute(
        select(Order).where(Order.assigned_to == user_id)
    ).scalars().all():
        o.assigned_to = None
    name = u.full_name
    session.delete(u)
    session.commit()
    _audit("delete", "user", user_id, name, current, session)
    return RedirectResponse("/users", status_code=303)
