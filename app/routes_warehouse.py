from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Product, StockMovement, User
from app.auth import get_current_user
from app.audit import log

router = APIRouter(prefix="/api/warehouse", tags=["warehouse"])


class ProductCreate(BaseModel):
    name: str
    color: str = ""
    article: str = ""
    quantity: int = 0
    min_stock: int = 0
    category: str = "sale"


class ProductOut(BaseModel):
    id: int
    name: str
    color: str
    article: str
    quantity: int
    image: Optional[str] = None
    min_stock: int = 0
    category: str = "sale"
    created_at: str

    class Config:
        from_attributes = True


class MovementCreate(BaseModel):
    product_id: int
    type: str  # supply or write-off
    reason: str  # поставка / ozon / wb / другое
    quantity: int
    comment: str = ""


class MovementOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    user_name: str
    type: str
    reason: str
    quantity: int
    stock_before: int
    stock_after: int
    comment: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


def _can_view(u: User):
    return u.role and (u.role.name == "admin" or u.role.can_view_warehouse)


def _can_edit(u: User):
    return u.role and (u.role.name == "admin" or u.role.can_edit_warehouse)


@router.get("/products")
def list_products(category: str = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_view(user):
        raise HTTPException(403, "Нет доступа к складу")
    q = db.query(Product)
    if category:
        q = q.filter(Product.category == category)
    return [_product_out(p) for p in q.order_by(Product.name).all()]


@router.post("/products")
def create_product(data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_edit(user):
        raise HTTPException(403, "Нет прав")
    p = Product(name=data.name, color=data.color, article=data.article, quantity=data.quantity, min_stock=data.min_stock, category=data.category)
    db.add(p)
    db.commit()
    db.refresh(p)
    log(user, "create", "product", p.id, f"Добавлен товар {p.name} ({p.article})", db=db)
    return {"id": p.id, "name": p.name, "color": p.color, "article": p.article, "quantity": p.quantity, "image": p.image, "min_stock": p.min_stock, "category": p.category, "created_at": p.created_at.isoformat()}


def _product_out(p):
    return {"id": p.id, "name": p.name, "color": p.color, "article": p.article, "quantity": p.quantity, "image": p.image, "min_stock": p.min_stock, "category": p.category, "created_at": p.created_at.isoformat()}


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_view(user):
        raise HTTPException(403, "Нет доступа к складу")
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(404, "Товар не найден")
    return _product_out(p)


@router.put("/products/{product_id}")
def update_product(product_id: int, data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_edit(user):
        raise HTTPException(403, "Нет прав")
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(404, "Товар не найден")
    p.name = data.name
    p.color = data.color
    p.article = data.article
    p.quantity = data.quantity
    p.min_stock = data.min_stock
    p.category = data.category
    db.commit()
    db.refresh(p)
    log(user, "update", "product", p.id, f"Обновлён товар {p.name}", db=db)
    return _product_out(p)


@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_edit(user):
        raise HTTPException(403, "Нет прав")
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(404, "Товар не найден")
    db.delete(p)
    db.commit()
    log(user, "delete", "product", product_id, f"Удалён товар {p.name}", db=db)
    return {"ok": True}


@router.post("/movements", response_model=MovementOut)
def create_movement(data: MovementCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_edit(user):
        raise HTTPException(403, "Нет прав")
    p = db.query(Product).get(data.product_id)
    if not p:
        raise HTTPException(404, "Товар не найден")
    qty = data.quantity
    if data.type == "write-off":
        qty = -abs(qty)
        if p.quantity + qty < 0:
            raise HTTPException(400, f"Недостаточно товара на складе: есть {p.quantity}, нужно {abs(qty)}")
    else:
        qty = abs(qty)

    stock_before = p.quantity
    p.quantity += qty
    stock_after = p.quantity
    db.commit()

    m = StockMovement(
        product_id=p.id,
        user_id=user.id,
        user_name=user.full_name or user.username,
        type=data.type,
        reason=data.reason,
        quantity=qty,
        stock_before=stock_before,
        stock_after=stock_after,
        comment=data.comment,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    log(user, "create", "stock_movement", m.id, f"{'Поставка' if data.type=='supply' else 'Списание'} {abs(qty)} шт товара {p.name}", db=db)
    return _movement_out(m, p.name)


@router.get("/movements", response_model=List[MovementOut])
def list_movements(
    product_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(user):
        raise HTTPException(403, "Нет доступа к складу")
    q = db.query(StockMovement).options(joinedload(StockMovement.product))
    if product_id:
        q = q.filter(StockMovement.product_id == product_id)
    records = q.order_by(StockMovement.created_at.desc()).offset(skip).limit(limit).all()
    return [_movement_out(m, m.product.name if m.product else "") for m in records]


def _movement_out(m: StockMovement, pname: str) -> MovementOut:
    return MovementOut(
        id=m.id,
        product_id=m.product_id,
        product_name=pname,
        user_name=m.user_name,
        type=m.type,
        reason=m.reason,
        quantity=m.quantity,
        stock_before=m.stock_before,
        stock_after=m.stock_after,
        comment=m.comment,
        created_at=m.created_at.isoformat(),
    )
