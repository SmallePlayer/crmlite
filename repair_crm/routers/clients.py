from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context, _client_dict
from models.client import Client

router = APIRouter()


@router.get("/clients", response_class=HTMLResponse)
def clients_page(request: Request, session: Session = Depends(get_db)):
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
    session: Session = Depends(get_db),
):
    c = Client(full_name=full_name.strip(), phone=phone.strip(), comment=comment.strip())
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
    session: Session = Depends(get_db),
):
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(404)
    c.full_name = full_name.strip()
    c.phone = phone.strip()
    c.comment = comment.strip()
    session.commit()
    _audit("update", "client", c.id, c.full_name, request.state.user, session)
    return RedirectResponse("/clients", status_code=303)


@router.post("/clients/{client_id}/delete")
def delete_client(client_id: int, request: Request, session: Session = Depends(get_db)):
    c = session.get(Client, client_id)
    if not c:
        raise HTTPException(404)
    session.delete(c)
    session.commit()
    _audit("delete", "client", client_id, c.full_name, request.state.user, session)
    return RedirectResponse("/clients", status_code=303)
