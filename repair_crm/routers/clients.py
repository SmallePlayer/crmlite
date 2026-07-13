from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context, _client_dict, _has_permission
from models.client import Client
from models.order import Order

router = APIRouter()


def _format_phone(phone: str) -> str:
    digits = ''.join(c for c in phone if c.isdigit())
    if len(digits) == 11 and digits[0] == '8':
        digits = '7' + digits[1:]
    if len(digits) == 11 and digits[0] == '7':
        return '+7' + digits[1:]
    if len(digits) == 10:
        return '+7' + digits
    return phone.strip()


@router.get("/clients", response_class=HTMLResponse)
def clients_page(request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u or not _has_permission(u, "manage_clients"):
        raise HTTPException(403)
    clients = session.execute(
        select(Client).order_by(desc(Client.created_at))
    ).scalars().all()
    return templates.TemplateResponse(request, "clients.html", {
        **_user_context(request, session),
        "clients": clients,
        "clients_data": [_client_dict(c) for c in clients],
    })


@router.post("/clients")
def create_client(
    request: Request,
    full_name: str = Form(...),
    phone: str = Form(...),
    comment: str = Form(""),
    tag: str = Form(""),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u or not _has_permission(u, "manage_clients"):
        raise HTTPException(403)
    formatted_phone = _format_phone(phone)
    existing = session.execute(
        select(Client).where(Client.phone == formatted_phone)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"Клиент с таким телефоном уже существует: {existing.full_name}")
    c = Client(full_name=full_name.strip(), phone=formatted_phone, comment=comment.strip(), tag=tag.strip())
    session.add(c)
    session.commit()
    _audit("create", "client", c.id, c.full_name, request.state.user, session)
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/{client_id}/edit")
def update_client(
    client_id: int, request: Request,
    full_name: str = Form(...),
    phone: str = Form(...),
    comment: str = Form(""),
    tag: str = Form(""),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u or not _has_permission(u, "manage_clients"):
        raise HTTPException(403)
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(404)
    formatted_phone = _format_phone(phone)
    existing = session.execute(
        select(Client).where(Client.phone == formatted_phone, Client.id != client_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, f"Клиент с таким телефоном уже существует: {existing.full_name}")
    c.full_name = full_name.strip()
    c.phone = formatted_phone
    c.comment = comment.strip()
    c.tag = tag.strip()
    session.commit()
    _audit("update", "client", c.id, c.full_name, request.state.user, session)
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/{client_id}/delete")
def delete_client(client_id: int, request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u or not _has_permission(u, "manage_clients"):
        raise HTTPException(403)
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(404)
    orders_count = session.execute(
        select(func.count(Order.id)).where(Order.client_id == client_id)
    ).scalar() or 0
    if orders_count > 0:
        raise HTTPException(400, f"Нельзя удалить клиента: у него {orders_count} заказ(ов)")
    session.delete(c)
    session.commit()
    _audit("delete", "client", client_id, c.full_name, request.state.user, session)
    return RedirectResponse("/clients", status_code=303)
