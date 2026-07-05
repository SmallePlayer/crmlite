from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from templates_env import templates
from sqlalchemy import select, desc
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context
from models.filament import Filament, FilamentMovement

router = APIRouter()


@router.get("/filaments", response_class=HTMLResponse)
def filaments_page(request: Request, session: Session = Depends(get_db)):
    filaments = session.execute(
        select(Filament).order_by(Filament.name)
    ).scalars().all()
    movements = session.execute(
        select(FilamentMovement).options(joinedload(FilamentMovement.filament))
        .order_by(desc(FilamentMovement.created_at)).limit(30)
    ).unique().scalars().all()
    return templates.TemplateResponse(request, "filaments.html", {
        **_user_context(request, session),
        "filaments": filaments, "movements": movements,
    })


@router.post("/filaments")
def create_filament(
    request: Request,
    name: str = Form(...),
    article: str = Form(""),
    manufacturer: str = Form(""),
    type: str = Form("PLA"),
    color: str = Form(""),
    quantity: int = Form(0),
    grams_per_spool: int = Form(1000),
    session: Session = Depends(get_db),
):
    f = Filament(name=name.strip(), article=article.strip(), manufacturer=manufacturer.strip(),
                 type=type, color=color.strip(), quantity=quantity, grams_per_spool=grams_per_spool)
    session.add(f)
    session.flush()
    if quantity > 0:
        session.add(FilamentMovement(filament_id=f.id, type="in", quantity=quantity, reason="Начальный остаток"))
    session.commit()
    _audit("create", "filament", f.id, f.name, request.state.user, session)
    return RedirectResponse("/filaments", status_code=303)


@router.post("/filaments/{fid}/edit")
def edit_filament(
    fid: int, request: Request,
    name: str = Form(...),
    article: str = Form(""),
    manufacturer: str = Form(""),
    type: str = Form("PLA"),
    color: str = Form(""),
    grams_per_spool: int = Form(1000),
    min_stock: int = Form(0),
    session: Session = Depends(get_db),
):
    f = session.get(Filament, fid)
    if not f: raise HTTPException(404)
    f.name = name.strip()
    f.article = article.strip()
    f.manufacturer = manufacturer.strip()
    f.color = color.strip()
    f.type = type
    f.grams_per_spool = grams_per_spool
    f.min_stock = min_stock
    session.commit()
    _audit("update", "filament", f.id, f.name, request.state.user, session)
    return RedirectResponse("/filaments", status_code=303)


@router.post("/filaments/{fid}/delete")
def delete_filament(fid: int, request: Request, session: Session = Depends(get_db)):
    f = session.get(Filament, fid)
    if not f: raise HTTPException(404)
    session.delete(f)
    session.commit()
    _audit("delete", "filament", fid, f.name, request.state.user, session)
    return RedirectResponse("/filaments", status_code=303)


@router.post("/filaments/receive")
async def receive_filament(request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    total = 0
    for row in data:
        fid = int(row.get("id", 0))
        qty = int(row.get("quantity", 0))
        if fid <= 0 or qty <= 0: continue
        f = session.get(Filament, fid)
        if not f: continue
        f.quantity += qty
        session.add(FilamentMovement(filament_id=fid, type="in", quantity=qty, reason="Приход"))
        total += qty
    session.commit()
    if total > 0:
        _audit("receive", "filament", None, f"+{total} г.", request.state.user, session)
    return JSONResponse({"ok": True})


@router.post("/filaments/expense")
def expense_filament(
    request: Request,
    filament_id: int = Form(...),
    quantity: int = Form(...),
    reason: str = Form(""),
    session: Session = Depends(get_db),
):
    f = session.get(Filament, filament_id)
    if not f: raise HTTPException(400)
    if f.quantity < quantity: raise HTTPException(400, f"Недостаточно: {f.quantity} г.")
    f.quantity -= quantity
    session.add(FilamentMovement(filament_id=filament_id, type="out", quantity=quantity, reason=reason.strip()))
    session.commit()
    _audit("expense", "filament", filament_id, f"{f.name} −{quantity} г.", request.state.user, session)
    return RedirectResponse("/filaments", status_code=303)
