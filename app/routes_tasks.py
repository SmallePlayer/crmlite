from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Task
from app.auth import get_current_user, require_admin
from app.audit import log

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])


class TaskCreate(BaseModel):
    name: str
    price: float
    unit: str = "шт"
    admin_controlled: bool = False


class TaskOut(BaseModel):
    id: int
    name: str
    price: float
    unit: str
    admin_controlled: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.name).all()
    return [_task_out(t) for t in tasks]


@router.post("", response_model=TaskOut)
def create_task(data: TaskCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    task = Task(name=data.name, price=data.price, unit=data.unit, admin_controlled=data.admin_controlled)
    db.add(task)
    db.commit()
    db.refresh(task)
    log(_, "create", "task", task.id, f"Создана работа {task.name}", db=db)
    return _task_out(task)


@router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(404, "Работа не найдена")
    task.name = data.name
    task.price = data.price
    task.unit = data.unit
    task.admin_controlled = data.admin_controlled
    db.commit()
    db.refresh(task)
    log(_, "update", "task", task.id, f"Обновлена работа {task.name}", db=db)
    return _task_out(task)


@router.delete("/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    task = db.query(Task).get(task_id)
    if not task:
        raise HTTPException(404, "Работа не найдена")
    db.delete(task)
    db.commit()
    log(_, "delete", "task", task_id, f"Удалена работа {task.name}", db=db)
    return {"ok": True}


def _task_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id,
        name=t.name,
        price=t.price,
        unit=t.unit,
        admin_controlled=t.admin_controlled,
        created_at=t.created_at.isoformat(),
    )
