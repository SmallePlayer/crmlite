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


class ProductOut(BaseModel):
    id: int
    name: str
    color: str
    article: str
    quantity: int
    image: Optional[str] = None
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


@router.get("/products", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_view(user):
        raise HTTPException(403, "Нет доступа к складу")
    return db.query(Product).order_by(Product.name).all()


@router.post("/products", response_model=ProductOut)
def create_product(data: ProductCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_edit(user):
        raise HTTPException(403, "Нет прав")
    p = Product(name=data.name, color=data.color, article=data.article, quantity=data.quantity)
    db.add(p)
    db.commit()
    db.refresh(p)
    log(user, "create", "product", p.id, f"Добавлен товар {p.name} ({p.article})", db=db)
    return p


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_view(user):
        raise HTTPException(403, "Нет доступа к складу")
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(404, "Товар не найден")
    return p


@router.put("/products/{product_id}", response_model=ProductOut)
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
    db.commit()
    db.refresh(p)
    log(user, "update", "product", p.id, f"Обновлён товар {p.name}", db=db)
    return p


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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not _can_view(user):
        raise HTTPException(403, "Нет доступа к складу")
    q = db.query(StockMovement).options(joinedload(StockMovement.product))
    if product_id:
        q = q.filter(StockMovement.product_id == product_id)
    records = q.order_by(StockMovement.created_at.desc()).limit(100).all()
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
