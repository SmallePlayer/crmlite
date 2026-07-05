import io
import os
import smtplib
import secrets
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from fastapi import APIRouter, Depends, Request, HTTPException, Query, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from templates_env import templates
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload
from fpdf import FPDF

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context, _get_user_from_request
from models.user import User
from models.order import Order, OrderItem, OrderPart
from models.task import Task
from models.filament import Filament

router = APIRouter()


@router.get("/orders/{order_id}/receipt", response_class=HTMLResponse)
def order_receipt(order_id: int, request: Request, format: str = Query("html"),
                  session: Session = Depends(get_db)):
    order = session.execute(
        select(Order)
        .options(joinedload(Order.client), joinedload(Order.items),
                 joinedload(Order.parts).joinedload(OrderPart.part),
                 joinedload(Order.assignee))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(404)
    admin = session.execute(
        select(User).where(User.username == "admin")
    ).scalar_one_or_none()
    line_items = []
    for item in order.items:
        line_items.append((item.name, 1, item.price, item.price))
    for op in order.parts:
        if op.part:
            line_items.append((f"{op.part.name} ({op.part.article})", op.quantity, op.price, op.quantity * op.price))

    html = templates.env.get_template("receipt.html").render(
        order=order, line_items=line_items, admin=admin)

    if format == "pdf":
        pdf = _build_receipt_pdf(order, line_items, admin)
        return StreamingResponse(io.BytesIO(pdf),
                                 media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename=receipt_{order.id}.pdf"})

    resp = HTMLResponse(html)
    return resp


@router.post("/orders/{order_id}/send-receipt")
def send_receipt(order_id: int, request: Request, email_to: str = Form(...),
                 session: Session = Depends(get_db)):
    order = session.execute(
        select(Order)
        .options(joinedload(Order.client), joinedload(Order.items),
                 joinedload(Order.parts).joinedload(OrderPart.part),
                 joinedload(Order.assignee))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(404)

    admin = session.execute(
        select(User).where(User.username == "admin")
    ).scalar_one_or_none()

    line_items = []
    for item in order.items:
        line_items.append((item.name, 1, item.price, item.price))
    for op in order.parts:
        if op.part:
            line_items.append((f"{op.part.name} ({op.part.article})", op.quantity, op.price, op.quantity * op.price))

    body = templates.env.get_template("receipt_email.html").render(
        order=order, line_items=line_items, admin=admin)
    subject = f"Квитанция №{order.id} — Ремонт 3D принтера"

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host:
        raise HTTPException(400, "SMTP не настроен. Укажите SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS в .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = email_to.strip()
    msg.attach(MIMEText(body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, [email_to.strip()], msg.as_string())
        server.quit()
    except Exception as e:
        raise HTTPException(400, f"Ошибка отправки: {str(e)}")

    _audit("send_receipt", "order", order_id, f"→ {email_to.strip()}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.get("/api/filaments/next-article")
def next_filament_article(session: Session = Depends(get_db)):
    articles = session.execute(
        select(Filament.article).where(Filament.article.like("FIL-%"))
    ).scalars().all()
    max_num = 0
    for a in articles:
        try:
            num = int(a.replace("FIL-", "").split()[0])
            if num > max_num: max_num = num
        except ValueError:
            pass
    return JSONResponse({"article": f"FIL-{max_num + 1:04d}"})


@router.get("/api/charts/revenue")
def chart_revenue(session: Session = Depends(get_db)):
    today = date.today()
    months = [(today.replace(day=1) - timedelta(days=i*30)).replace(day=1) for i in range(5, -1, -1)]
    data = []
    for m in months:
        next_m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
        total = session.execute(
            select(func.coalesce(func.sum(Order.total_price), 0))
            .where(Order.status == "closed", Order.closed_at >= m, Order.closed_at < next_m)
        ).scalar() or 0
        data.append({"month": m.strftime("%b %Y"), "total": float(total)})
    return JSONResponse(data)


@router.get("/api/charts/top-services")
def chart_top_services(session: Session = Depends(get_db)):
    items = session.execute(
        select(OrderItem.name, func.count(OrderItem.id), func.sum(OrderItem.price))
        .group_by(OrderItem.name).order_by(desc(func.sum(OrderItem.price))).limit(8)
    ).all()
    return JSONResponse([{"name": r[0], "count": r[1], "total": float(r[2] or 0)} for r in items])


@router.get("/api/sse/events")
async def _sse_stub():
    return JSONResponse({"events": []})


@router.get("/api/dashboard")
async def _dashboard_stub():
    return JSONResponse({})


@router.get("/api/task-assignments/my")
async def _tasks_api(request: Request, session: Session = Depends(get_db)):
    u = _get_user_from_request(request)
    if not u:
        return JSONResponse([])
    tasks = session.execute(
        select(Task).options(joinedload(Task.creator), joinedload(Task.assignee))
        .where(Task.assigned_to == u.id, Task.status == "pending")
        .order_by(desc(Task.created_at))
    ).unique().scalars().all()
    return JSONResponse([{
        "id": t.id, "title": t.title, "description": t.description,
        "created_by": t.creator.full_name if t.creator else "—",
        "assigned_to": t.assignee.full_name if t.assignee else "—",
        "status": t.status, "created_at": t.created_at.isoformat(),
    } for t in tasks])


@router.get("/api/warehouse/products")
async def _wh_products_stub():
    return JSONResponse([])


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request, session: Session = Depends(get_db)):
    from models.notification import Notification
    u = request.state.user
    if not u:
        raise HTTPException(403)
    notifs = session.execute(
        select(Notification)
        .where(Notification.user_id == u.id)
        .order_by(desc(Notification.created_at)).limit(50)
    ).scalars().all()
    return templates.TemplateResponse(request, "notifications.html", {
        **_user_context(request, session), "notifications": notifs,
    })


@router.post("/notifications/read-all")
def notifications_read_all(request: Request, session: Session = Depends(get_db)):
    from models.notification import Notification
    u = request.state.user
    if not u: raise HTTPException(403)
    for n in session.execute(
        select(Notification)
        .where(Notification.user_id == u.id, Notification.is_read == False)
    ).scalars().all():
        n.is_read = True
    session.commit()
    return RedirectResponse("/notifications", status_code=303)


def _build_receipt_pdf(order, line_items, admin=None) -> bytes:
    from fpdf.enums import XPos, YPos
    font_paths = [
        BASE_DIR / "arial.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ]
    font_file = None
    for fp in font_paths:
        if fp.exists():
            font_file = str(fp)
            break

    pdf = FPDF()
    pdf.add_page()
    if font_file:
        pdf.add_font("ArialU", "", font_file)
        pdf.add_font("ArialU", "B", font_file)
        font_name = "ArialU"
    else:
        font_name = "Helvetica"

    def money(v): return f"{v:,.0f}".replace(",", " ") + " руб."

    pdf.set_font(font_name, "B", 16)
    pdf.cell(0, 10, f"Квитанция №{order.id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(font_name, "", 10)
    pdf.cell(0, 6, f"от {order.created_at.strftime('%d.%m.%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font(font_name, "", 10)
    details = [
        ("Клиент:", order.client.full_name if order.client else "—"),
        ("Телефон:", order.client.phone if order.client else "—"),
        ("Принтер:", order.printer),
        ("Дефект:", order.defect[:80]),
    ]
    if admin:
        extra = f" (ИНН {admin.inn})" if admin.inn else ""
        details.append(("Мастер:", f"{admin.full_name}{extra}"))
    for label, value in details:
        pdf.set_font(font_name, "B", 10)
        pdf.cell(28, 6, label)
        pdf.set_font(font_name, "", 10)
        pdf.cell(0, 6, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    col_w = [10, 78, 14, 32, 38]
    headers = ["#", "Наименование", "Кол.", "Цена", "Сумма"]
    pdf.set_font(font_name, "B", 9)
    pdf.set_fill_color(230, 230, 230)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C" if i > 0 else "C")
    pdf.ln()

    pdf.set_font(font_name, "", 9)
    for idx, (name, qty, price, line_total) in enumerate(line_items, 1):
        pdf.cell(col_w[0], 6, str(idx), border=1, align="C")
        pdf.cell(col_w[1], 6, name[:50], border=1)
        pdf.cell(col_w[2], 6, str(qty), border=1, align="C")
        pdf.cell(col_w[3], 6, money(price), border=1, align="R")
        pdf.cell(col_w[4], 6, money(line_total), border=1, align="R")
        pdf.ln()

    pdf.set_font(font_name, "B", 10)
    pdf.cell(sum(col_w[:4]), 7, "ИТОГО:", border=1, align="R")
    pdf.cell(col_w[4], 7, money(order.total_price), border=1, align="R")
    pdf.ln(10)

    if order.closed_at:
        pdf.set_font(font_name, "", 9)
        pdf.cell(0, 6, f"Выполнен: {order.closed_at.strftime('%d.%m.%Y %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

    pdf.set_font(font_name, "", 9)
    pdf.cell(85, 6, "Мастер: _________________________")
    pdf.cell(85, 6, "Клиент: _________________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font(font_name, "", 8)
    pdf.cell(85, 5, "(подпись)")
    pdf.cell(85, 5, "(подпись)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return pdf.output()
