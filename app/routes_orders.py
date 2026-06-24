from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from pydantic import BaseModel
from app import models, schemas
from app.auth import get_current_user
from app.audit import log as audit_log

router = APIRouter(prefix="/api/orders", tags=["orders"], dependencies=[Depends(get_current_user)])


def _log(db: Session, order_id: int, user_id: int, user_name: str, action: str):
    db.add(models.OrderLog(order_id=order_id, user_id=user_id, user_name=user_name, action=action))


@router.get("", response_model=List[schemas.OrderOut])
def list_orders(client_id: int = None, status: str = None, db: Session = Depends(get_db)):
    q = db.query(models.Order).options(
        joinedload(models.Order.client),
        joinedload(models.Order.items).joinedload(models.OrderItem.service),
    )
    if client_id:
        q = q.filter(models.Order.client_id == client_id)
    if status:
        q = q.filter(models.Order.status == status)
    orders = q.order_by(models.Order.created_at.desc()).all()
    return [_order_to_out(o) for o in orders]


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).options(
        joinedload(models.Order.client),
        joinedload(models.Order.items).joinedload(models.OrderItem.service),
    ).get(order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    return _order_to_out(order)


@router.post("", response_model=schemas.OrderOut)
def create_order(data: schemas.OrderCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    client = db.query(models.Client).get(data.client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")

    total = sum(item.price * item.quantity for item in data.items)
    cname = data.client_name or client.full_name
    order = models.Order(
        client_id=data.client_id,
        client_name=cname,
        order_type=data.order_type,
        status="active",
        printer=data.printer,
        description=data.description,
        complaint=data.complaint,
        modeler=data.modeler,
        address=data.address,
        pickup_time=data.pickup_time,
        note=data.note,
        total_price=total,
    )
    db.add(order)
    db.flush()
    _log(db, order.id, user.id, user.full_name or user.username, f"Создан заказ ({data.order_type})")

    for item in data.items:
        service = db.query(models.Service).get(item.service_id)
        if not service:
            raise HTTPException(404, f"Услуга {item.service_id} не найдена")
        db.add(models.OrderItem(
            order_id=order.id,
            service_id=item.service_id,
            quantity=item.quantity,
            price=item.price,
        ))

    db.commit()
    db.refresh(order)
    audit_log(user, "create", "order", order.id, f"Создан заказ №{order.id} ({data.order_type})", db=db)
    order = db.query(models.Order).options(
        joinedload(models.Order.client),
        joinedload(models.Order.items).joinedload(models.OrderItem.service),
    ).get(order.id)
    return _order_to_out(order)


@router.put("/{order_id}", response_model=schemas.OrderOut)
def update_order(order_id: int, data: schemas.OrderUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).options(
        joinedload(models.Order.items),
    ).get(order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")

    if data.status is not None:
        if data.status != order.status:
            _log(db, order.id, user.id, user.full_name or user.username, f"Статус: {order.status} → {data.status}")
        order.status = data.status
    if data.client_name is not None:
        order.client_name = data.client_name
    if data.printer is not None:
        order.printer = data.printer
    if data.description is not None:
        order.description = data.description
    if data.complaint is not None:
        order.complaint = data.complaint
    if data.work_done is not None:
        order.work_done = data.work_done
    if data.parts_replaced is not None:
        order.parts_replaced = data.parts_replaced
    if data.modeler is not None:
        order.modeler = data.modeler
    if data.address is not None:
        order.address = data.address
    if data.pickup_time is not None:
        order.pickup_time = data.pickup_time
    if data.note is not None:
        order.note = data.note

    if data.items is not None:
        total = sum(item.price * item.quantity for item in data.items)
        order.total_price = total
        for old_item in order.items:
            db.delete(old_item)
        for item in data.items:
            service = db.query(models.Service).get(item.service_id)
            if not service:
                raise HTTPException(404, f"Услуга {item.service_id} не найдена")
            db.add(models.OrderItem(
                order_id=order.id,
                service_id=item.service_id,
                quantity=item.quantity,
                price=item.price,
            ))

    db.commit()
    db.refresh(order)
    audit_log(user, "update", "order", order.id, f"Обновлён заказ №{order.id}", db=db)
    order = db.query(models.Order).options(
        joinedload(models.Order.client),
        joinedload(models.Order.items).joinedload(models.OrderItem.service),
    ).get(order.id)
    return _order_to_out(order)


@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).get(order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if not user.role or not user.role.can_delete_orders:
        raise HTTPException(403, "Нет права на удаление заказов")
    _log(db, order.id, user.id, user.full_name or user.username, "Заказ удалён")
    db.delete(order)
    db.commit()
    audit_log(user, "delete", "order", order_id, f"Удалён заказ №{order_id}", db=db)
    return {"ok": True}


@router.get("/{order_id}/logs")
def get_order_logs(order_id: int, db: Session = Depends(get_db)):
    logs = db.query(models.OrderLog).filter(
        models.OrderLog.order_id == order_id
    ).order_by(models.OrderLog.created_at.asc()).all()
    return [
        {
            "id": log.id,
            "user_name": log.user_name,
            "action": log.action,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


class CommentCreate(BaseModel):
    text: str


@router.post("/{order_id}/comments")
def add_comment(order_id: int, data: CommentCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).get(order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    c = models.OrderComment(
        order_id=order.id,
        user_id=user.id,
        user_name=user.full_name or user.username,
        text=data.text,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "user_name": c.user_name, "text": c.text, "created_at": c.created_at.isoformat()}


@router.get("/{order_id}/comments")
def list_comments(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).get(order_id)
    if not order:
        raise HTTPException(404, "Заказ не найден")
    comments = db.query(models.OrderComment).filter(
        models.OrderComment.order_id == order_id
    ).order_by(models.OrderComment.created_at.asc()).all()
    return [
        {"id": c.id, "user_name": c.user_name, "text": c.text, "created_at": c.created_at.isoformat()}
        for c in comments
    ]


def _order_to_out(o: models.Order) -> schemas.OrderOut:
    return schemas.OrderOut(
        id=o.id,
        client_id=o.client_id,
        client_name=o.client_name or o.client.full_name,
        order_type=o.order_type,
        status=o.status,
        printer=o.printer,
        description=o.description,
        complaint=o.complaint,
        work_done=o.work_done,
        parts_replaced=o.parts_replaced,
        modeler=o.modeler,
        address=o.address,
        pickup_time=o.pickup_time,
        total_price=o.total_price,
        note=o.note,
        created_at=o.created_at,
        items=[
            schemas.OrderItemOut(
                id=item.id,
                service_id=item.service_id,
                service_name=item.service.name,
                quantity=item.quantity,
                price=item.price,
            )
            for item in o.items
        ],
    )
