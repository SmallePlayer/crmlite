from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from templates_env import templates
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context
from models.warehouse import Part, StockMovement
from models.order import OrderPart

router = APIRouter()


@router.get("/warehouse", response_class=HTMLResponse)
def warehouse_page(request: Request, session: Session = Depends(get_db)):
    parts = session.execute(
        select(Part).order_by(Part.name, Part.article)
    ).scalars().all()
    movements = session.execute(
        select(StockMovement).options(joinedload(StockMovement.part))
        .order_by(desc(StockMovement.created_at)).limit(40)
    ).unique().scalars().all()
    return templates.TemplateResponse(request, "warehouse.html", {
        **_user_context(request, session),
        "parts": parts, "movements": movements,
        "parts_data": [{
            "id": p.id, "name": p.name, "article": p.article,
            "purchase_price": p.purchase_price, "quantity": p.quantity,
            "min_stock": p.min_stock,
        } for p in parts],
    })


@router.post("/warehouse/receive")
async def receive_parts(request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    total = 0
    for row in data:
        name = row.get("name", "").strip()
        article = row.get("article", "").strip()
        price = float(row.get("purchase_price", 0))
        qty = int(row.get("quantity", 0))
        if not name or not article or qty <= 0:
            continue
        existing = session.execute(
            select(Part).where(Part.article == article)
        ).scalar_one_or_none()
        if existing:
            existing.quantity += qty
            if price > 0:
                existing.purchase_price = price
            part = existing
        else:
            part = Part(name=name, article=article, purchase_price=price, quantity=qty)
            session.add(part)
            session.flush()
        session.add(StockMovement(
            part_id=part.id, type="in", quantity=qty,
            price_per_unit=price or part.purchase_price,
            reason="Приход",
        ))
        total += qty
    session.commit()
    if total > 0:
        _audit("receive", "part", None, f"+{total} шт.", request.state.user, session)
    return JSONResponse({"ok": True})


@router.post("/warehouse/{part_id}/edit")
def update_part(
    part_id: int, request: Request,
    name: str = Form(...),
    purchase_price: float = Form(0),
    min_stock: int = Form(0),
    session: Session = Depends(get_db),
):
    p = session.get(Part, part_id)
    if not p:
        raise HTTPException(404)
    p.name = name.strip()
    p.purchase_price = purchase_price
    p.min_stock = min_stock
    session.commit()
    _audit("update", "part", p.id, p.name, request.state.user, session)
    return RedirectResponse("/warehouse", status_code=303)


@router.post("/warehouse/{part_id}/delete")
def delete_part(part_id: int, request: Request, session: Session = Depends(get_db)):
    p = session.get(Part, part_id)
    if not p:
        raise HTTPException(404)
    used_in_orders = session.execute(
        select(func.count(OrderPart.id)).where(OrderPart.part_id == part_id)
    ).scalar() or 0
    if used_in_orders > 0:
        raise HTTPException(400, f"Нельзя удалить запчасть: используется в {used_in_orders} заказ(ах)")
    session.delete(p)
    session.commit()
    _audit("delete", "part", part_id, p.name, request.state.user, session)
    return RedirectResponse("/warehouse", status_code=303)
