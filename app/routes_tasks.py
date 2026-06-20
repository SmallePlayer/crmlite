from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])


class TaskCreate(BaseModel):
    name: str
    price: float
    unit: str = "шт"


class TaskOut(BaseModel):
    id: int
    name: str
    price: float
    unit: str
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.name).all()
    return [_task_out(t) for t in tasks]


@router.post("", response_model=TaskOut)
def create_task(data: TaskCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    task = Task(name=data.name, price=data.price, unit=data.unit)
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(404, "Работа не найдена")
    task.name = data.name
    task.price = data.price
    task.unit = data.unit
    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(404, "Работа не найдена")
    db.delete(task)
    db.commit()
    return {"ok": True}


def _task_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id,
        name=t.name,
        price=t.price,
        unit=t.unit,
        created_at=t.created_at.isoformat(),
    )
