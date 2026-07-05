import io
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload
import openpyxl

from config import BASE_DIR, TIMEZONE_OFFSET
from database import get_db
from models.client import Client
from models.service import Service
from models.warehouse import Part, Product, ProductMovement
from models.order import Order

router = APIRouter()


def _make_excel(headers: list[str], rows: list[list], filename: str) -> StreamingResponse:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/export/db")
def export_db(request: Request):
    if request.state.user.role.name != "admin":
        raise HTTPException(403)
    return FileResponse(BASE_DIR / "repair_crm.db", filename="repair_crm_backup.db")


@router.get("/export/clients")
def export_clients(request: Request, session: Session = Depends(get_db)):
    clients = session.execute(select(Client).order_by(Client.full_name)).scalars().all()
    rows = [[c.id, c.full_name, c.phone, c.comment, str(c.created_at)] for c in clients]
    return _make_excel(["ID", "ФИО", "Телефон", "Комментарий", "Создан"], rows, "clients.xlsx")


@router.get("/export/orders")
def export_orders(request: Request, session: Session = Depends(get_db)):
    orders = session.execute(
        select(Order).options(joinedload(Order.client))
        .order_by(desc(Order.created_at))
    ).unique().scalars().all()
    rows = [[o.id, o.client.full_name if o.client else "—", o.order_type, o.printer, o.defect, o.status,
             o.total_price, str(o.created_at), str(o.closed_at or "")] for o in orders]
    return _make_excel(["ID", "Клиент", "Тип", "Принтер", "Дефект", "Статус", "Сумма", "Создан", "Закрыт"],
                       rows, "orders.xlsx")


@router.get("/export/services")
def export_services(request: Request, session: Session = Depends(get_db)):
    services = session.execute(select(Service).order_by(Service.name)).scalars().all()
    rows = [[s.id, s.name, s.price, s.description] for s in services]
    return _make_excel(["ID", "Название", "Цена", "Описание"], rows, "services.xlsx")


@router.get("/export/parts")
def export_parts(request: Request, session: Session = Depends(get_db)):
    parts = session.execute(select(Part).order_by(Part.name)).scalars().all()
    rows = [[p.id, p.name, p.article, p.purchase_price, p.quantity, p.min_stock] for p in parts]
    return _make_excel(["ID", "Название", "Артикул", "Цена закупки", "Кол-во", "Мин. остаток"],
                       rows, "parts.xlsx")


@router.get("/export/products")
def export_products(request: Request, session: Session = Depends(get_db)):
    products = session.execute(select(Product).order_by(Product.name)).scalars().all()
    rows = [[p.id, p.name, p.article, p.color, p.quantity] for p in products]
    return _make_excel(["ID", "Название", "Артикул", "Цвет", "Кол-во"], rows, "products.xlsx")


@router.get("/export/products-weekly")
def export_products_weekly(request: Request, session: Session = Depends(get_db)):
    today = datetime.utcnow() + TIMEZONE_OFFSET
    start = today - timedelta(days=today.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return _product_report(session, start, end, "products_weekly.xlsx", "неделя")


@router.get("/export/products-monthly")
def export_products_monthly(request: Request, month: str = Query(""), session: Session = Depends(get_db)):
    today = datetime.utcnow() + TIMEZONE_OFFSET
    if month:
        try:
            year, mon = map(int, month.split("-"))
            start = datetime(year, mon, 1)
        except (ValueError, TypeError):
            start = today.replace(day=1)
    else:
        start = today.replace(day=1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return _product_report(session, start, end, "products_monthly.xlsx", f"{start.strftime('%Y-%m')}")


def _product_report(session, start, end, filename, period_label):
    products = session.execute(select(Product).order_by(Product.name)).scalars().all()
    movements = session.execute(
        select(ProductMovement).where(
            ProductMovement.created_at >= start - TIMEZONE_OFFSET,
            ProductMovement.created_at < end - TIMEZONE_OFFSET,
        )
    ).scalars().all()
    by_product = {}
    for m in movements:
        pid = m.product_id
        if pid not in by_product:
            by_product[pid] = {"in": 0, "out": 0}
        by_product[pid][m.type] += m.quantity
    rows = []
    for p in products:
        mv = by_product.get(p.id, {"in": 0, "out": 0})
        rows.append([
            p.name, p.article or "", p.color or "", p.quantity,
            mv["in"], mv["out"],
            p.cost_price if p.cost_price else "",
            round(mv["in"] * (p.cost_price or 0), 2) if p.cost_price else "",
        ])
    return _make_excel(
        ["Название", "Артикул", "Цвет", "Остаток", "Приход", "Расход", "Себест./шт", "Сумма прихода"],
        rows, filename)
