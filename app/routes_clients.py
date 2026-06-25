from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from sqlalchemy.orm import joinedload
from app.auth import get_current_user
from app.audit import log

router = APIRouter(prefix="/api/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


def _can_view_clients(user):
    return user.role and (user.role.name == "admin" or user.role.can_view_clients)


def _can_edit_clients(user):
    return user.role and (user.role.name == "admin" or user.role.can_edit_clients)


@router.get("", response_model=List[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not _can_view_clients(user):
        raise HTTPException(403, "Нет доступа к клиентам")
    return db.query(models.Client).order_by(models.Client.created_at.desc()).all()


@router.post("", response_model=schemas.ClientOut)
def create_client(data: schemas.ClientCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not _can_edit_clients(user):
        raise HTTPException(403, "Нет прав на создание клиентов")
    client = models.Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    log(user, "create", "client", client.id, f"Создан клиент {client.full_name}", db=db)
    return client


@router.get("/{client_id}", response_model=schemas.ClientOut)
def get_client(client_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not _can_view_clients(user):
        raise HTTPException(403, "Нет доступа к клиентам")
    client = db.query(models.Client).get(client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")
    return client


@router.put("/{client_id}", response_model=schemas.ClientOut)
def update_client(client_id: int, data: schemas.ClientCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not _can_edit_clients(user):
        raise HTTPException(403, "Нет прав на редактирование клиентов")
    client = db.query(models.Client).get(client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")
    client.full_name = data.full_name
    client.phone = data.phone
    db.commit()
    db.refresh(client)
    log(user, "update", "client", client.id, f"Обновлён клиент {client.full_name}", db=db)
    return client


@router.get("/{client_id}/orders")
def get_client_orders(client_id: int, db: Session = Depends(get_db)):
    client = db.query(models.Client).get(client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")
    orders = db.query(models.Order).options(
        joinedload(models.Order.items),
    ).filter(models.Order.client_id == client_id).order_by(models.Order.created_at.desc()).all()
    return [
        {
            "id": o.id,
            "client_name": o.client_name,
            "order_type": o.order_type,
            "status": o.status,
            "total_price": o.total_price,
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


@router.delete("/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    if not _can_edit_clients(user):
        raise HTTPException(403, "Нет прав на удаление клиентов")
    client = db.query(models.Client).get(client_id)
    if not client:
        raise HTTPException(404, "Клиент не найден")
    db.delete(client)
    db.commit()
    log(user, "delete", "client", client_id, f"Удалён клиент {client.full_name}", db=db)
    return {"ok": True}
