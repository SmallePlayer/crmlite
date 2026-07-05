from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from templates_env import templates
from sqlalchemy import select, desc, or_
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR
from database import get_db
from helpers import _user_context
from models.client import Client
from models.order import Order
from models.warehouse import Part, Product
from models.service import Service

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = Query(""), session: Session = Depends(get_db)):
    results = {"clients": [], "orders": [], "parts": [], "products": [], "services": []}
    if q:
        like = f"%{q.strip()}%"
        results["clients"] = session.execute(
            select(Client).where(or_(Client.full_name.ilike(like), Client.phone.ilike(like)))
            .limit(20)
        ).scalars().all()
        results["orders"] = session.execute(
            select(Order).options(joinedload(Order.client))
            .where(or_(Order.printer.ilike(like), Order.defect.ilike(like),
                       Order.client.has(Client.full_name.ilike(like))))
            .order_by(desc(Order.created_at)).limit(20)
        ).unique().scalars().all()
        results["parts"] = session.execute(
            select(Part).where(or_(Part.name.ilike(like), Part.article.ilike(like))).limit(20)
        ).scalars().all()
        results["products"] = session.execute(
            select(Product).where(or_(Product.name.ilike(like), Product.article.ilike(like))).limit(20)
        ).scalars().all()
        results["services"] = session.execute(
            select(Service).where(Service.name.ilike(like)).limit(20)
        ).scalars().all()
    return templates.TemplateResponse(request, "search.html", {
        **_user_context(request, session), "q": q.strip(), "results": results,
        "total": sum(len(v) for v in results.values()),
    })
