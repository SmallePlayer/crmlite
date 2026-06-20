from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import WorkReport, Task, User
from app import models as m
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


class ReportCreate(BaseModel):
    task_id: int
    quantity: float
    order_id: Optional[int] = None


class ReportUpdate(BaseModel):
    quantity: float


class ReportOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    task_id: int
    task_name: str
    task_price: float
    task_unit: str
    quantity: float
    total: float
    order_id: Optional[int] = None
    order_info: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[ReportOut])
def list_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(WorkReport).options(
        joinedload(WorkReport.user),
        joinedload(WorkReport.task),
        joinedload(WorkReport.order).joinedload(m.Order.client),
    )
    if user.role.name != "admin":
        q = q.filter(WorkReport.user_id == user.id)
    reports = q.order_by(WorkReport.created_at.desc()).all()
    return [_report_out(r) for r in reports]


@router.post("", response_model=ReportOut)
def create_report(data: ReportCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).get(data.task_id)
    if not task:
        raise HTTPException(404, "Работа не найдена")
    report = WorkReport(
        user_id=user.id,
        task_id=data.task_id,
        order_id=data.order_id,
        quantity=data.quantity,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    report = db.query(WorkReport).options(
        joinedload(WorkReport.user),
        joinedload(WorkReport.task),
        joinedload(WorkReport.order).joinedload(m.Order.client),
    ).get(report.id)
    return _report_out(report)


@router.put("/{report_id}", response_model=ReportOut)
def update_report(report_id: int, data: ReportUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    report = db.query(WorkReport).options(
        joinedload(WorkReport.user),
        joinedload(WorkReport.task),
        joinedload(WorkReport.order).joinedload(m.Order.client),
    ).get(report_id)
    if not report:
        raise HTTPException(404, "Отчёт не найден")
    report.quantity = data.quantity
    db.commit()
    db.refresh(report)
    return _report_out(report)


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    report = db.query(WorkReport).get(report_id)
    if not report:
        raise HTTPException(404, "Отчёт не найден")
    db.delete(report)
    db.commit()
    return {"ok": True}


def _report_out(r: WorkReport) -> ReportOut:
    oinfo = None
    if r.order:
        oinfo = f"Заказ #{r.order.id} — {r.order.client.full_name}"
    return ReportOut(
        id=r.id,
        user_id=r.user_id,
        user_name=r.user.full_name or r.user.username,
        task_id=r.task_id,
        task_name=r.task.name,
        task_price=r.task.price,
        task_unit=r.task.unit,
        quantity=r.quantity,
        total=round(r.quantity * r.task.price, 2),
        order_id=r.order_id,
        order_info=oinfo,
        created_at=r.created_at.isoformat(),
    )
