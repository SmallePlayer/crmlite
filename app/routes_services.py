from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.audit import log

router = APIRouter(prefix="/api/services", tags=["services"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=List[schemas.ServiceOut])
def list_services(category: str = None, db: Session = Depends(get_db)):
    q = db.query(models.Service)
    if category:
        q = q.filter(models.Service.category == category)
    return q.order_by(models.Service.name).all()


@router.post("", response_model=schemas.ServiceOut)
def create_service(data: schemas.ServiceCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    service = models.Service(**data.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    log(user, "create", "service", service.id, f"Создана услуга {service.name}", db=db)
    return service


@router.put("/{service_id}", response_model=schemas.ServiceOut)
def update_service(service_id: int, data: schemas.ServiceCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    service = db.query(models.Service).get(service_id)
    if not service:
        raise HTTPException(404, "Услуга не найдена")
    service.name = data.name
    service.price = data.price
    service.category = data.category
    db.commit()
    db.refresh(service)
    log(user, "update", "service", service.id, f"Обновлена услуга {service.name}", db=db)
    return service


@router.delete("/{service_id}")
def delete_service(service_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    service = db.query(models.Service).get(service_id)
    if not service:
        raise HTTPException(404, "Услуга не найдена")
    db.delete(service)
    db.commit()
    log(user, "delete", "service", service_id, f"Удалена услуга {service.name}", db=db)
    return {"ok": True}
