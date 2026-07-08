from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR, ORDER_STATUSES, ORDER_TYPES, ORDER_FLOW
from database import get_db
from helpers import _audit, _user_context, _paginate, _recalc_total
from models.user import User
from models.client import Client
from models.service import Service
from models.warehouse import Part, StockMovement
from models.order import Order, OrderItem, OrderPart

router = APIRouter()


@router.get("/orders", response_class=HTMLResponse)
def orders_page(
    request: Request,
    status: str = Query(""),
    order_type: str = Query(""),
    sort: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    client: str = Query(""),
    page: int = Query(1),
    session: Session = Depends(get_db),
):
    base_q = select(Order).options(
        joinedload(Order.client), joinedload(Order.assignee),
    )
    if status:
        base_q = base_q.where(Order.status == status)
    else:
        base_q = base_q.where(Order.status != "closed")
    if order_type:
        base_q = base_q.where(Order.order_type == order_type)
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            base_q = base_q.where(Order.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            base_q = base_q.where(Order.created_at < dt + timedelta(days=1))
        except ValueError:
            pass
    if client.strip():
        like = f"%{client.strip()}%"
        base_q = base_q.where(Order.client.has(Client.full_name.ilike(like)))

    q = base_q.order_by(desc(Order.created_at))
    if sort == "oldest":
        q = base_q.order_by(Order.created_at)
    elif sort == "id_desc":
        q = base_q.order_by(desc(Order.id))
    elif sort == "id_asc":
        q = base_q.order_by(Order.id)
    elif sort == "price_desc":
        q = base_q.order_by(desc(Order.total_price))
    elif sort == "client":
        q = base_q.join(Order.client).order_by(Client.full_name)
    orders, page, pages, total = _paginate(session, q, page)

    rows = session.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    ).all()
    counts = {row[0]: row[1] for row in rows}
    for s_val in ["in_progress", "waiting_parts", "ready", "closed"]:
        counts.setdefault(s_val, 0)

    return templates.TemplateResponse(request, "orders.html", {
        **_user_context(request, session),
        "orders": orders, "current_status": status, "current_type": order_type,
        "current_sort": sort,
        "counts": counts, "page": page, "pages": pages, "total": total,
        "date_from": date_from, "date_to": date_to, "client_filter": client.strip(),
        "ORDER_STATUSES": ORDER_STATUSES, "ORDER_TYPES": ORDER_TYPES, "timedelta": timedelta,
        "now": datetime.utcnow(),
    })


@router.get("/orders/new", response_class=HTMLResponse)
def order_create_page(request: Request, session: Session = Depends(get_db)):
    clients = session.execute(
        select(Client).order_by(Client.full_name)
    ).scalars().all()
    users = session.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    ).scalars().all()
    return templates.TemplateResponse(request, "order_create.html", {
        **_user_context(request, session), "clients": clients, "users": users,
        "ORDER_TYPES": ORDER_TYPES,
    })


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail_page(order_id: int, request: Request, session: Session = Depends(get_db)):
    order = session.execute(
        select(Order)
        .options(joinedload(Order.client), joinedload(Order.items),
                 joinedload(Order.parts).joinedload(OrderPart.part),
                 joinedload(Order.assignee))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    services = session.execute(
        select(Service).order_by(Service.name)
    ).scalars().all()
    parts = session.execute(
        select(Part).order_by(Part.name, Part.article)
    ).scalars().all()
    return templates.TemplateResponse(request, "order_detail.html", {
        **_user_context(request, session),
        "order": order, "services": services, "parts": parts,
        "clients": session.execute(
            select(Client).order_by(Client.full_name)
        ).scalars().all(),
        "users": session.execute(
            select(User).where(User.is_active == True).order_by(User.full_name)
        ).scalars().all(),
        "ORDER_STATUSES": ORDER_STATUSES, "ORDER_TYPES": ORDER_TYPES,
        "ORDER_FLOW": ORDER_FLOW, "timedelta": timedelta, "now": lambda: datetime.utcnow(),
        "services_data": [{
            "id": s.id, "name": s.name, "price": s.price,
        } for s in services],
        "parts_data": [{
            "id": p.id, "name": p.name, "article": p.article,
            "purchase_price": p.purchase_price, "quantity": p.quantity,
        } for p in parts],
    })


@router.post("/orders")
def create_order(
    request: Request,
    client_id: int = Form(...),
    order_type: str = Form("repair"),
    printer: str = Form(...),
    defect: str = Form(...),
    assigned_to: int = Form(0),
    deadline: str = Form(""),
    scheduled_date: str = Form(""),
    scheduled_date_print: str = Form(""),
    scheduled_time: str = Form(""),
    scheduled_at: str = Form(""),
    schedule_location: str = Form(""),
    warranty_days: int = Form(0),
    is_warranty: bool = Form(False),
    prepaid: float = Form(0),
    estimated_price: float = Form(0),
    source: str = Form(""),
    source_custom: str = Form(""),
    session: Session = Depends(get_db),
):
    if not session.get(Client, client_id):
        raise HTTPException(400, "Клиент не найден")
    deadline_val = None
    if deadline.strip():
        try:
            deadline_val = datetime.strptime(deadline.strip(), "%Y-%m-%d")
        except ValueError:
            pass
    sched_val = None
    sched_str = scheduled_at.strip() or f"{scheduled_date.strip()}T{scheduled_time.strip()}" or f"{scheduled_date_print.strip()}T00:00"
    if sched_str and sched_str != "T" and sched_str != "T00:00":
        try:
            sched_val = datetime.strptime(sched_str.replace("T", " ")[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    order = Order(
        client_id=client_id,
        order_type=order_type,
        printer=printer.strip(),
        defect=defect.strip(),
        assigned_to=assigned_to if assigned_to > 0 else None,
        deadline=deadline_val,
        scheduled_at=sched_val,
        schedule_location=schedule_location.strip(),
        warranty_days=warranty_days,
        is_warranty=is_warranty,
        prepaid=prepaid,
        estimated_price=estimated_price,
        source=source_custom.strip() or source.strip(),
    )
    session.add(order)
    session.commit()
    _audit("create", "order", order.id, f"#{order.id} {printer.strip()}", request.state.user, session)
    return RedirectResponse(f"/orders/{order.id}", status_code=303)


@router.post("/orders/{order_id}/items")
def add_order_item(
    request: Request, order_id: int,
    name: str = Form(...),
    price: float = Form(0),
    session: Session = Depends(get_db),
):
    order = session.get(Order, order_id)
    if not order or order.status == "closed":
        raise HTTPException(400, "Нельзя добавить услугу в закрытый заказ")
    item = OrderItem(order_id=order_id, name=name.strip(), price=price)
    session.add(item)
    session.commit()
    _recalc_total(session, order_id)
    _audit("add_item", "order", order_id, f"+{name.strip()} {price}₽", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/items/{item_id}/delete")
def delete_order_item(
    request: Request, order_id: int, item_id: int,
    session: Session = Depends(get_db),
):
    order = session.get(Order, order_id)
    if not order or order.status == "closed":
        raise HTTPException(400)
    item = session.get(OrderItem, item_id)
    if not item or item.order_id != order_id:
        raise HTTPException(404)
    session.delete(item)
    session.commit()
    _recalc_total(session, order_id)
    _audit("remove_item", "order", order_id, f"-{item.name}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/parts")
def add_order_part(
    request: Request, order_id: int,
    part_id: int = Form(...),
    quantity: int = Form(1),
    price: float = Form(0),
    session: Session = Depends(get_db),
):
    order = session.get(Order, order_id)
    if not order or order.status == "closed":
        raise HTTPException(400, "Нельзя добавить запчасть в закрытый заказ")
    part = session.execute(
        select(Part).where(Part.id == part_id).with_for_update()
    ).scalar_one_or_none()
    if not part:
        raise HTTPException(400, "Запчасть не найдена")
    if part.quantity < quantity:
        raise HTTPException(400, f"Недостаточно на складе: {part.quantity} шт.")
    part.quantity -= quantity
    session.add(StockMovement(
        part_id=part_id, type="out", quantity=quantity,
        price_per_unit=price or part.purchase_price,
        reason=f"Заказ #{order_id}",
        order_id=order_id,
    ))
    session.add(OrderPart(
        order_id=order_id, part_id=part_id,
        quantity=quantity, price=price or part.purchase_price,
    ))
    session.commit()
    _recalc_total(session, order_id)
    _audit("add_part", "order", order_id, f"+{part.name} x{quantity}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/parts/{op_id}/delete")
def delete_order_part(
    request: Request, order_id: int, op_id: int,
    session: Session = Depends(get_db),
):
    order = session.get(Order, order_id)
    if not order or order.status == "closed":
        raise HTTPException(400)
    op = session.get(OrderPart, op_id)
    if not op or op.order_id != order_id:
        raise HTTPException(404)
    part = session.get(Part, op.part_id)
    if part:
        part.quantity += op.quantity
        session.add(StockMovement(
            part_id=op.part_id, type="in", quantity=op.quantity,
            price_per_unit=op.price,
            reason=f"Возврат из заказа #{order_id}",
            order_id=order_id,
        ))
    session.delete(op)
    session.commit()
    _recalc_total(session, order_id)
    _audit("remove_part", "order", order_id, f"-{part.name} x{op.quantity}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/close")
def close_order(order_id: int, request: Request, session: Session = Depends(get_db)):
    order = session.get(Order, order_id)
    if not order or order.status == "closed":
        raise HTTPException(400)
    order.status = "closed"
    order.closed_at = datetime.utcnow()
    session.commit()
    _audit("close", "order", order_id, f"#{order_id} total={order.total_price}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/status")
def change_order_status(order_id: int, request: Request,
                        new_status: str = Form(...),
                        session: Session = Depends(get_db)):
    order = session.get(Order, order_id)
    if not order or order.status == "closed" or new_status == order.status:
        raise HTTPException(400)
    if new_status not in ORDER_FLOW.get(order.status, []):
        raise HTTPException(400, f"Нельзя переключить с «{ORDER_STATUSES[order.status][0]}» на «{ORDER_STATUSES[new_status][0]}»")
    order.status = new_status
    session.commit()
    _audit("change_status", "order", order_id,
           f"#{order_id} → {ORDER_STATUSES[new_status][0]}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/reopen")
def reopen_order(order_id: int, request: Request, session: Session = Depends(get_db)):
    order = session.get(Order, order_id)
    if not order or order.status != "closed":
        raise HTTPException(400)
    order.status = "in_progress"
    order.closed_at = None
    session.commit()
    _audit("reopen", "order", order_id, f"#{order_id}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/edit")
def edit_order(
    order_id: int, request: Request,
    client_id: int = Form(...),
    order_type: str = Form("repair"),
    printer: str = Form(...),
    defect: str = Form(...),
    assigned_to: int = Form(0),
    scheduled_date: str = Form(""),
    scheduled_time: str = Form(""),
    scheduled_at: str = Form(""),
    schedule_location: str = Form(""),
    warranty_days: int = Form(0),
    is_warranty: bool = Form(False),
    prepaid: float = Form(0),
    estimated_price: float = Form(0),
    source: str = Form(""),
    source_custom: str = Form(""),
    session: Session = Depends(get_db),
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    order.client_id = client_id
    order.order_type = order_type
    order.printer = printer.strip()
    order.defect = defect.strip()
    order.assigned_to = assigned_to if assigned_to > 0 else None
    order.prepaid = prepaid
    order.estimated_price = estimated_price
    order.source = source_custom.strip() or source.strip()
    sched_str = scheduled_at.strip()
    if sched_str:
        try:
            order.scheduled_at = datetime.strptime(sched_str.replace("T", " ")[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            order.scheduled_at = None
    else:
        d = scheduled_date.strip()
        t = scheduled_time.strip()
        if d:
            try:
                order.scheduled_at = datetime.strptime(f"{d} {t or '00:00'}", "%Y-%m-%d %H:%M")
            except ValueError:
                order.scheduled_at = None
        else:
            order.scheduled_at = None
    order.schedule_location = schedule_location.strip()
    order.warranty_days = warranty_days
    order.is_warranty = is_warranty
    session.commit()
    _audit("edit", "order", order_id, f"#{order_id}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/{order_id}/confirm")
def toggle_confirm(order_id: int, request: Request, session: Session = Depends(get_db)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    order.is_confirmed = not order.is_confirmed
    session.commit()
    _audit("confirm" if order.is_confirmed else "unconfirm", "order", order_id,
           f"#{order_id}", request.state.user, session)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@router.post("/orders/batch-close")
def batch_close_orders(request: Request, ids: str = Form(""), session: Session = Depends(get_db)):
    closed = 0
    for oid in [int(x) for x in ids.split(",") if x.strip().isdigit()]:
        order = session.get(Order, oid)
        if order and order.status != "closed":
            order.status = "closed"
            order.closed_at = datetime.utcnow()
            closed += 1
    session.commit()
    if closed > 0:
        _audit("batch_close", "order", None, f"Закрыто {closed} заказов", request.state.user, session)
    return RedirectResponse("/orders", status_code=303)


@router.post("/orders/batch-delete")
def batch_delete_orders(request: Request, ids: str = Form(""), session: Session = Depends(get_db)):
    deleted = 0
    for oid in [int(x) for x in ids.split(",") if x.strip().isdigit()]:
        order = session.get(Order, oid)
        if order:
            for op in order.parts:
                part = session.get(Part, op.part_id)
                if part:
                    part.quantity += op.quantity
                    session.add(StockMovement(
                        part_id=op.part_id, type="in", quantity=op.quantity,
                        price_per_unit=op.price,
                        reason=f"Возврат: удаление заказа #{oid}",
                    ))
            session.delete(order)
            deleted += 1
    session.commit()
    if deleted > 0:
        _audit("batch_delete", "order", None, f"Удалено {deleted} заказов", request.state.user, session)
    return RedirectResponse("/orders", status_code=303)


@router.get("/clients/{client_id}/orders", response_class=HTMLResponse)
def client_history(client_id: int, request: Request, session: Session = Depends(get_db)):
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(404)
    orders = session.execute(
        select(Order).options(joinedload(Order.items), joinedload(Order.parts))
        .where(Order.client_id == client_id)
        .order_by(desc(Order.created_at))
    ).unique().scalars().all()
    return templates.TemplateResponse(request, "client_history.html", {
        **_user_context(request, session), "client": client, "orders": orders,
        "ORDER_STATUSES": ORDER_STATUSES, "ORDER_TYPES": ORDER_TYPES, "timedelta": timedelta,
    })


@router.post("/orders/{order_id}/delete")
def delete_order(order_id: int, request: Request, session: Session = Depends(get_db)):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(404)
    for op in order.parts:
        part = session.get(Part, op.part_id)
        if part:
            part.quantity += op.quantity
            session.add(StockMovement(
                part_id=op.part_id, type="in", quantity=op.quantity,
                price_per_unit=op.price,
                reason=f"Возврат: удаление заказа #{order_id}",
            ))
    session.delete(order)
    session.commit()
    _audit("delete", "order", order_id, f"#{order_id}", request.state.user, session)
    return RedirectResponse("/orders", status_code=303)
