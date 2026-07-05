from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context
from models.service import Service

router = APIRouter()


@router.get("/services", response_class=HTMLResponse)
def services_page(request: Request, session: Session = Depends(get_db)):
    services = session.execute(
        select(Service).order_by(Service.name)
    ).scalars().all()
    return templates.TemplateResponse(request, "services.html", {
        **_user_context(request, session),
        "services": services,
        "services_data": [{
            "id": s.id, "name": s.name, "price": s.price,
            "description": s.description or "",
        } for s in services],
    })


@router.post("/services")
def create_service(
    request: Request,
    name: str = Form(...),
    price: float = Form(0),
    description: str = Form(""),
    session: Session = Depends(get_db),
):
    s = Service(name=name.strip(), price=price, description=description.strip())
    session.add(s)
    session.commit()
    _audit("create", "service", s.id, s.name, request.state.user, session)
    return RedirectResponse("/services", status_code=303)


@router.post("/services/{service_id}/edit")
def update_service(
    service_id: int, request: Request,
    name: str = Form(...),
    price: float = Form(0),
    description: str = Form(""),
    session: Session = Depends(get_db),
):
    s = session.get(Service, service_id)
    if not s:
        raise HTTPException(404)
    s.name = name.strip()
    s.price = price
    s.description = description.strip()
    session.commit()
    _audit("update", "service", s.id, s.name, request.state.user, session)
    return RedirectResponse("/services", status_code=303)


@router.post("/services/{service_id}/delete")
def delete_service(service_id: int, request: Request, session: Session = Depends(get_db)):
    s = session.get(Service, service_id)
    if not s:
        raise HTTPException(404)
    session.delete(s)
    session.commit()
    _audit("delete", "service", service_id, s.name, request.state.user, session)
    return RedirectResponse("/services", status_code=303)
