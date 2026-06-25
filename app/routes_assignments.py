from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import TaskAssignment, User
from app.auth import get_current_user
from app.audit import log

router = APIRouter(prefix="/api/task-assignments", tags=["task_assignments"])


class AssignmentCreate(BaseModel):
    title: str
    description: str = ""
    assigned_to: int


class AssignmentOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    assigned_by_name: str
    assigned_to_name: str
    assigned_to_id: int
    status: str
    created_at: str

    class Config:
        from_attributes = True


def _can_assign(user: User):
    return True  # все могут назначать (и сами себе)


@router.post("")
def create_assignment(data: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _can_assign(user):
        raise HTTPException(403, "Нет прав назначать задания")
    a = TaskAssignment(
        title=data.title,
        description=data.description,
        assigned_by=user.id,
        assigned_to=data.assigned_to,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    log(user, "create", "task_assignment", a.id, f"Назначено задание '{a.title}'", db=db)
    return _out(a)


@router.get("")
def list_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(TaskAssignment).options(
        joinedload(TaskAssignment.assigner), joinedload(TaskAssignment.assignee)
    )
    if not (user.role and (user.role.name == "admin" or _can_assign(user))):
        q = q.filter(TaskAssignment.assigned_to == user.id)
    return [_out(a) for a in q.order_by(TaskAssignment.created_at.desc()).limit(50).all()]


@router.get("/my")
def my_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = db.query(TaskAssignment).options(
        joinedload(TaskAssignment.assigner), joinedload(TaskAssignment.assignee)
    ).filter(TaskAssignment.assigned_to == user.id).order_by(TaskAssignment.created_at.desc()).all()
    return [_out(a) for a in records]


@router.put("/{assignment_id}")
def update_assignment(assignment_id: int, status: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.query(TaskAssignment).get(assignment_id)
    if not a:
        raise HTTPException(404, "Задание не найдено")
    if a.assigned_to != user.id and not _can_assign(user):
        raise HTTPException(403, "Нет прав")
    a.status = status
    db.commit()
    log(user, "update", "task_assignment", a.id, f"Статус задания '{a.title}': {status}", db=db)
    return _out(a)


def _out(a: TaskAssignment) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "assigned_by_name": a.assigner.full_name or a.assigner.username,
        "assigned_to_name": a.assignee.full_name or a.assignee.username,
        "assigned_to_id": a.assigned_to,
        "status": a.status,
        "created_at": a.created_at.isoformat(),
    }
