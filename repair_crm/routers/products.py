import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from templates_env import templates
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR, UPLOADS_DIR
from database import get_db
from helpers import _audit, _user_context
from models.warehouse import Product, ProductMovement, PackagingItem, ProductPackaging

router = APIRouter()


@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, session: Session = Depends(get_db)):
    products = session.execute(
        select(Product).order_by(Product.name, Product.article)
    ).scalars().all()
    movements = session.execute(
        select(ProductMovement).options(joinedload(ProductMovement.product))
        .order_by(desc(ProductMovement.created_at)).limit(40)
    ).unique().scalars().all()
    packaging_items = session.execute(
        select(PackagingItem).order_by(PackagingItem.name)
    ).scalars().all()
    
    parent_products = [p for p in products if p.parent_id is None]
    children_map = {}
    for p in products:
        if p.parent_id:
            if p.parent_id not in children_map:
                children_map[p.parent_id] = []
            children_map[p.parent_id].append(p)
    
    product_packaging_map = {}
    for p in products:
        links = session.execute(
            select(ProductPackaging).options(joinedload(ProductPackaging.packaging_item))
            .where(ProductPackaging.product_id == p.id)
        ).scalars().all()
        if links:
            product_packaging_map[p.id] = [{
                "id": link.id,
                "packaging_item_id": link.packaging_item_id,
                "packaging_name": link.packaging_item.name,
                "packaging_unit": link.packaging_item.unit,
                "price_per_unit": link.packaging_item.price_per_unit,
                "quantity": link.quantity,
                "cost": link.quantity * link.packaging_item.price_per_unit,
            } for link in links]
    
    return templates.TemplateResponse(request, "products.html", {
        **_user_context(request, session),
        "products": parent_products, "movements": movements,
        "children_map": children_map,
        "packaging_items": packaging_items,
        "product_packaging_map": product_packaging_map,
        "products_data": [{
            "id": p.id, "name": p.name, "article": p.article,
            "color": p.color or "", "quantity": p.quantity,
            "cost_price": p.cost_price or 0,
            "print_cost": p.print_cost or 0,
            "pack_cost": p.pack_cost or 0,
            "variants": p.variants or "[]",
            "image": p.image or "",
        } for p in products],
        "packaging_data": [{
            "id": pi.id, "name": pi.name, "unit": pi.unit,
            "price_per_unit": pi.price_per_unit,
        } for pi in packaging_items],
    })


@router.post("/products/supply")
async def products_supply(request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    total = 0
    dest = ""
    by_product = {}
    for row in data:
        pid = int(row.get("product_id", 0))
        qty = int(row.get("quantity", 0))
        per_set = int(row.get("per_set", 1))
        sets = int(row.get("sets", 1))
        destination = row.get("destination", "")
        reason = row.get("reason", "Поставка")
        if pid <= 0 or qty <= 0: continue
        by_product.setdefault(pid, {"qty": 0, "rows": []})
        by_product[pid]["qty"] += qty
        by_product[pid]["rows"].append(row)
    for pid, info in by_product.items():
        p = session.get(Product, pid)
        if not p: continue
        if p.quantity < info["qty"]:
            return JSONResponse({"error": f"Недостаточно: {p.name} ({p.quantity} шт., нужно {info['qty']})"}, status_code=400)
    for pid, info in by_product.items():
        p = session.get(Product, pid)
        if not p: continue
        for row in info["rows"]:
            qty = int(row.get("quantity", 0))
            per_set = int(row.get("per_set", 1))
            sets = int(row.get("sets", 1))
            destination = row.get("destination", "")
            reason = row.get("reason", "Поставка")
            p.quantity -= qty
            reason_text = f"{reason}: {sets} наб. × {per_set} шт." if per_set > 1 or sets > 1 else reason
            session.add(ProductMovement(product_id=pid, type="out", quantity=qty,
                          destination=destination, reason=reason_text))
            dest = destination
            total += qty
    session.commit()
    if total > 0:
        _audit("supply", "product", None, f"{dest}: −{total} шт.", request.state.user, session)
    return JSONResponse({"ok": True})


@router.post("/products/receive")
async def receive_products(request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    total = 0
    for row in data:
        name = row.get("name", "").strip()
        article = row.get("article", "").strip()
        color = row.get("color", "").strip()
        qty = int(row.get("quantity", 0))
        cost_price = float(row.get("cost_price", 0) or 0)
        print_cost = float(row.get("print_cost", 0) or 0)
        pack_cost = float(row.get("pack_cost", 0) or 0)
        if not name or not article:
            continue
        existing = session.execute(
            select(Product).where(Product.article == article)
        ).scalar_one_or_none()
        if existing:
            if qty > 0:
                existing.quantity += qty
            if color: existing.color = color
            if cost_price: existing.cost_price = cost_price
            if print_cost: existing.print_cost = print_cost
            if pack_cost: existing.pack_cost = pack_cost
            product = existing
        else:
            product = Product(name=name, article=article, color=color, quantity=qty,
                             cost_price=cost_price, print_cost=print_cost, pack_cost=pack_cost)
            session.add(product)
            session.flush()
        if qty > 0:
            session.add(ProductMovement(
                product_id=product.id, type="in", quantity=qty,
                destination="", reason="Приход",
            ))
            total += qty
    session.commit()
    if total > 0:
        _audit("receive", "product", None, f"+{total} шт.", request.state.user, session)
    return JSONResponse({"ok": True})


@router.post("/products/{product_id}/stock-out")
def product_stock_out(
    product_id: int, request: Request,
    quantity: int = Form(...),
    destination: str = Form(""),
    reason: str = Form(""),
    session: Session = Depends(get_db),
):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404)
    if p.quantity < quantity:
        raise HTTPException(400, f"Недостаточно на складе: {p.quantity} шт.")
    p.quantity -= quantity
    session.add(ProductMovement(
        product_id=product_id, type="out", quantity=quantity,
        destination=destination.strip(), reason=reason.strip(),
    ))
    session.commit()
    _audit("stock_out", "product", p.id,
           f"-{quantity} {p.name} → {destination}", request.state.user, session)
    return RedirectResponse("/products", status_code=303)


@router.post("/products/{product_id}/edit")
def update_product(
    product_id: int, request: Request,
    name: str = Form(...),
    article: str = Form(""),
    color: str = Form(""),
    cost_price: float = Form(0),
    print_cost: float = Form(0),
    pack_cost: float = Form(0),
    session: Session = Depends(get_db),
):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404)
    p.name = name.strip()
    p.article = article.strip()
    p.color = color.strip()
    p.cost_price = float(cost_price or 0)
    p.print_cost = float(print_cost or 0)
    p.pack_cost = float(pack_cost or 0)
    session.commit()
    _audit("update", "product", p.id, p.name, request.state.user, session)
    return RedirectResponse("/products", status_code=303)


@router.post("/products/{product_id}/save-variants")
async def save_product_variants(product_id: int, request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    p = session.get(Product, product_id)
    if not p: raise HTTPException(404)
    p.variants = json.dumps(data, ensure_ascii=False)
    session.commit()
    return JSONResponse({"ok": True})


@router.post("/products/{product_id}/children")
async def add_child_products(product_id: int, request: Request, session: Session = Depends(get_db)):
    """Добавление дочерних товаров (вариантов комплекта)"""
    parent = session.get(Product, product_id)
    if not parent:
        raise HTTPException(404, "Родительский товар не найден")
    
    data = await request.json()
    children = data.get("children", [])
    
    for child_data in children:
        name = child_data.get("name", "").strip()
        article = child_data.get("article", "").strip()
        quantity = int(child_data.get("quantity", 0))
        
        if not name or not article:
            continue
        
        # Проверяем существование
        existing = session.execute(
            select(Product).where(Product.article == article)
        ).scalar_one_or_none()
        
        if existing:
            existing.quantity += quantity
            existing.parent_id = product_id
        else:
            child = Product(
                name=name,
                article=article,
                quantity=quantity,
                parent_id=product_id,
                cost_price=parent.cost_price,
                print_cost=parent.print_cost,
                pack_cost=parent.pack_cost,
            )
            session.add(child)
    
    session.commit()
    _audit("add_children", "product", product_id, f"Добавлено {len(children)} вариантов", request.state.user, session)
    return JSONResponse({"ok": True})


@router.post("/products/{product_id}/delete")
def delete_product(product_id: int, request: Request, session: Session = Depends(get_db)):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404)
    movements_count = session.execute(
        select(func.count(ProductMovement.id)).where(ProductMovement.product_id == product_id)
    ).scalar() or 0
    if movements_count > 0:
        raise HTTPException(400, f"Нельзя удалить товар: есть {movements_count} записей движений")
    session.delete(p)
    session.commit()
    _audit("delete", "product", product_id, p.name, request.state.user, session)
    return RedirectResponse("/products", status_code=303)


@router.post("/products/{product_id}/upload-image")
async def upload_product_image(product_id: int, file: UploadFile = File(...),
                               session: Session = Depends(get_db)):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404)
    if not file.filename:
        raise HTTPException(400, "Файл не указан")
    ext = Path(file.filename).suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if ext not in allowed:
        raise HTTPException(400, f"Недопустимый формат: {ext}. Разрешены: {', '.join(allowed)}")
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(400, "Файл слишком большой (макс. 5 МБ)")
    safe_name = f"prod_{product_id}_{secrets.token_hex(4)}{ext}"
    filepath = UPLOADS_DIR / safe_name
    content = await file.read()
    filepath.write_bytes(content)
    p.image = safe_name
    session.commit()
    return RedirectResponse("/products", status_code=303)


@router.post("/packaging/create")
async def create_packaging_item(request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    name = data.get("name", "").strip()
    unit = data.get("unit", "шт").strip()
    price = float(data.get("price_per_unit", 0) or 0)
    if not name:
        return JSONResponse({"error": "Укажите название"}, status_code=400)
    if unit not in ("шт", "м²"):
        unit = "шт"
    item = PackagingItem(name=name, unit=unit, price_per_unit=price)
    session.add(item)
    session.commit()
    _audit("create", "packaging", item.id, name, request.state.user, session)
    return JSONResponse({"ok": True, "id": item.id})


@router.post("/packaging/{item_id}/edit")
async def edit_packaging_item(item_id: int, request: Request, session: Session = Depends(get_db)):
    data = await request.json()
    item = session.get(PackagingItem, item_id)
    if not item:
        raise HTTPException(404)
    name = data.get("name", "").strip()
    unit = data.get("unit", "шт").strip()
    price = float(data.get("price_per_unit", 0) or 0)
    if not name:
        return JSONResponse({"error": "Укажите название"}, status_code=400)
    if unit not in ("шт", "м²"):
        unit = "шт"
    item.name = name
    item.unit = unit
    item.price_per_unit = price
    session.commit()
    _audit("update", "packaging", item.id, name, request.state.user, session)
    return JSONResponse({"ok": True})


@router.post("/packaging/{item_id}/delete")
def delete_packaging_item(item_id: int, request: Request, session: Session = Depends(get_db)):
    item = session.get(PackagingItem, item_id)
    if not item:
        raise HTTPException(404)
    used = session.execute(
        select(func.count(ProductPackaging.id)).where(ProductPackaging.packaging_item_id == item_id)
    ).scalar() or 0
    if used > 0:
        raise HTTPException(400, f"Нельзя удалить: используется в {used} товар(ах)")
    session.delete(item)
    session.commit()
    _audit("delete", "packaging", item.id, item.name, request.state.user, session)
    return RedirectResponse("/products", status_code=303)


@router.post("/products/{product_id}/save-packaging")
async def save_product_packaging(product_id: int, request: Request, session: Session = Depends(get_db)):
    p = session.get(Product, product_id)
    if not p:
        raise HTTPException(404)
    data = await request.json()
    items = data.get("items", [])
    
    existing = session.execute(
        select(ProductPackaging).where(ProductPackaging.product_id == product_id)
    ).scalars().all()
    for link in existing:
        session.delete(link)
    
    total_cost = 0.0
    for row in items:
        pkg_id = int(row.get("packaging_item_id", 0))
        qty = float(row.get("quantity", 0) or 0)
        if pkg_id <= 0 or qty <= 0:
            continue
        pkg_item = session.get(PackagingItem, pkg_id)
        if not pkg_item:
            continue
        link = ProductPackaging(
            product_id=product_id,
            packaging_item_id=pkg_id,
            quantity=qty,
        )
        session.add(link)
        total_cost += qty * pkg_item.price_per_unit
    
    p.pack_cost = total_cost
    session.commit()
    _audit("update_packaging", "product", product_id, f"Упаковка: {total_cost:.2f} ₽", request.state.user, session)
    return JSONResponse({"ok": True, "pack_cost": total_cost})
