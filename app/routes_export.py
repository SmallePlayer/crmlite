from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from io import BytesIO
from openpyxl import Workbook
from app.database import get_db, DATABASE_URL
from app.models import Client, Order, Task, WorkReport, Attendance, User
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/export", tags=["export"], dependencies=[Depends(get_current_user)])


def _stream(wb: Workbook, filename: str):
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/clients")
def export_clients(db: Session = Depends(get_db)):
    wb = Workbook()
    ws = wb.active
    ws.title = "Клиенты"
    ws.append(["ID", "ФИО", "Телефон", "Дата создания"])
    for c in db.query(Client).all():
        ws.append([c.id, c.full_name, c.phone, c.created_at.isoformat()])
    return _stream(wb, "clients.xlsx")


@router.get("/orders")
def export_orders(db: Session = Depends(get_db)):
    wb = Workbook()
    ws = wb.active
    ws.title = "Заказы"
    ws.append(["ID", "Клиент", "Тип", "Статус", "Сумма", "Дата"])
    orders = db.query(Order).options(joinedload(Order.client)).order_by(Order.created_at.desc()).all()
    for o in orders:
        ws.append([o.id, o.client.full_name, o.order_type, o.status, o.total_price, o.created_at.isoformat()])
    return _stream(wb, "orders.xlsx")


@router.get("/reports")
def export_reports(db: Session = Depends(get_db), _=Depends(require_admin)):
    wb = Workbook()
    ws = wb.active
    ws.title = "Отчёты"
    ws.append(["ID", "Сотрудник", "Работа", "Кол-во", "Цена", "Сумма", "Дата"])
    reports = db.query(WorkReport).options(
        joinedload(WorkReport.user), joinedload(WorkReport.task)
    ).order_by(WorkReport.created_at.desc()).all()
    for r in reports:
        ws.append([r.id, r.user.full_name or r.user.username, r.task.name, r.quantity, r.task.price, r.quantity * r.task.price, r.created_at.isoformat()])
    return _stream(wb, "reports.xlsx")


@router.get("/attendance")
def export_attendance(db: Session = Depends(get_db), _=Depends(require_admin)):
    wb = Workbook()
    ws = wb.active
    ws.title = "Отметки"
    ws.append(["ID", "Сотрудник", "Дата", "Пришёл", "Ушёл"])
    records = db.query(Attendance).options(joinedload(Attendance.user)).order_by(Attendance.created_at.desc()).all()
    for r in records:
        ws.append([r.id, r.user.full_name or r.user.username, r.date, r.check_in, r.check_out or ""])
    return _stream(wb, "attendance.xlsx")


@router.get("/database")
def export_database(_=Depends(require_admin)):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    return FileResponse(
        db_path,
        media_type="application/octet-stream",
        filename="crm_backup.db",
        headers={"Content-Disposition": "attachment; filename=crm_backup.db"},
    )
