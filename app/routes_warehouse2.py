from typing import List, Optional
import os, uuid, json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.models import Product, OrderTemplate, User, Order
from app.auth import get_current_user
from app.audit import log

router = APIRouter(prefix="/api", tags=["warehouse"])

UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _can_edit_warehouse(user: User):
    return user.role and (user.role.name == "admin" or user.role.can_edit_warehouse)


# === ФОТО ТОВАРА ===

@router.post("/warehouse/products/{product_id}/upload")
def upload_product_image(product_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_edit_warehouse(user):
        raise HTTPException(403, "Нет прав")
    p = db.query(Product).get(product_id)
    if not p:
        raise HTTPException(404, "Товар не найден")
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    fname = f"prod_{product_id}_{uuid.uuid4().hex[:8]}.{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path, "wb") as f:
        f.write(file.file.read())
    p.image = f"/static/uploads/{fname}"
    db.commit()
    return {"image": p.image}


# === ТЕМПЛЕЙТЫ ЗАКАЗОВ ===

class TemplateItem(BaseModel):
    service_id: int = 0
    custom_name: Optional[str] = None
    quantity: int = 1
    price: float = 0


class TemplateCreate(BaseModel):
    name: str
    order_type: str = "repair"
    printer: Optional[str] = None
    description: Optional[str] = None
    complaint: Optional[str] = None
    modeler: Optional[str] = None
    address: Optional[str] = None
    pickup_time: Optional[str] = None
    note: Optional[str] = None
    items: Optional[List[TemplateItem]] = None


class TemplateOut(BaseModel):
    id: int
    name: str
    order_type: str
    printer: Optional[str] = None
    description: Optional[str] = None
    complaint: Optional[str] = None
    modeler: Optional[str] = None
    address: Optional[str] = None
    pickup_time: Optional[str] = None
    note: Optional[str] = None
    items: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


@router.get("/templates", response_model=List[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(OrderTemplate).order_by(OrderTemplate.name).all()


@router.post("/templates", response_model=TemplateOut)
def create_template(data: TemplateCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role = user.role
    if not role or (role.name != "admin" and not role.can_edit_orders):
        raise HTTPException(403, "Нет прав")
    d = data.model_dump()
    if d.get("items"):
        d["items"] = json.dumps(d["items"], ensure_ascii=False)
    t = OrderTemplate(**d)
    db.add(t)
    db.commit()
    db.refresh(t)
    log(user, "create", "order_template", t.id, f"Создан шаблон заказа {t.name}", db=db)
    return t


@router.post("/templates/{template_id}/apply")
def apply_template(template_id: int, order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(OrderTemplate).get(template_id)
    if not t:
        raise HTTPException(404, "Шаблон не найден")
    o = db.query(Order).get(order_id)
    if not o:
        raise HTTPException(404, "Заказ не найден")
    if t.printer is not None:
        o.printer = t.printer
    if t.description is not None:
        o.description = t.description
    if t.complaint is not None:
        o.complaint = t.complaint
    if t.modeler is not None:
        o.modeler = t.modeler
    if t.address is not None:
        o.address = t.address
    if t.pickup_time is not None:
        o.pickup_time = t.pickup_time
    if t.note is not None:
        o.note = t.note
    if t.items:
        try:
            items = json.loads(t.items)
            for old_item in o.items:
                db.delete(old_item)
            for item in items:
                db.add(models.OrderItem(
                    order_id=o.id,
                    service_id=item.get("service_id", 0),
                    custom_name=item.get("custom_name"),
                    quantity=item.get("quantity", 1),
                    price=item.get("price", 0),
                ))
            total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
            o.total_price = total
        except Exception:
            pass
    db.commit()
    return {"ok": True}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role = user.role
    if not role or (role.name != "admin" and not role.can_edit_orders):
        raise HTTPException(403, "Нет прав")
    t = db.query(OrderTemplate).get(template_id)
    if not t:
        raise HTTPException(404, "Шаблон не найден")
    db.delete(t)
    db.commit()
    log(user, "delete", "order_template", template_id, f"Удалён шаблон заказа {t.name}", db=db)
    return {"ok": True}
