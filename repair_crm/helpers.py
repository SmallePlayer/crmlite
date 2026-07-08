import hashlib
import json
import math
import secrets
from datetime import datetime

from fastapi import HTTPException, Request
from jose import jwt
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from config import SECRET_KEY, TOKEN_EXPIRY, PER_PAGE
from database import engine
from models.user import User, Role
from models.audit import AuditLog
from models.notification import Notification
from models.client import Client
from models.order import Order, OrderItem, OrderPart


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return salt + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    salt, dk_hex = stored.split(":", 1)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex() == dk_hex


def _create_token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow().timestamp() + TOKEN_EXPIRY},
        SECRET_KEY, algorithm="HS256",
    )


def _get_user_from_request(request: Request) -> User | None:
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        return None
    with Session(engine) as s:
        return s.execute(
            select(User).options(joinedload(User.role)).where(User.id == user_id)
        ).unique().scalar_one_or_none()


def _has_permission(user: User | None, perm: str) -> bool:
    if not user or not user.is_active:
        return False
    if user.role.name == "admin":
        return True
    perms = json.loads(user.role.permissions) if user.role.permissions else []
    return perm in perms


def _check_perm(request: Request, perm: str):
    if not _has_permission(request.state.user, perm):
        raise HTTPException(403, "Недостаточно прав")


def _validate_password(pw: str) -> str:
    pw = pw.strip()
    if " " in pw:
        raise HTTPException(400, "Пароль не должен содержать пробелы")
    if len(pw) < 4:
        raise HTTPException(400, "Пароль должен быть не короче 4 символов")
    return pw


def _audit(action: str, entity_type: str, entity_id: int | None = None,
           details: str = "", user: User | None = None, session: Session | None = None):
    a = AuditLog(
        user_id=user.id if user else None,
        user_name=user.full_name if user else "Система",
        action=action, entity_type=entity_type,
        entity_id=entity_id, details=details,
    )
    if session is not None:
        session.add(a)
        try:
            _notify_all(f"{action}: {entity_type}", details or "", "", session)
        except Exception:
            pass
        try:
            session.commit()
        except Exception:
            import traceback
            traceback.print_exc()
    else:
        with Session(engine) as s:
            s.add(a)
            s.commit()
        _notify_all(f"{action}: {entity_type}", details or "", "", None)


def _notify(user_id: int, title: str, text: str = "", link: str = "", session: Session | None = None):
    n = Notification(user_id=user_id, title=title, text=text, link=link)
    if session is not None:
        session.add(n)
    else:
        with Session(engine) as s:
            s.add(n)
            s.commit()


def _notify_all(title: str, text: str = "", link: str = "", session: Session | None = None):
    pass


def _user_context(request: Request, session: Session | None = None) -> dict:
    u = getattr(request.state, "user", None)
    if not u:
        return {"user": None, "is_admin": False, "can_manage_users": False, "unread_count": 0}
    unread = 0
    if session is not None:
        unread = session.execute(
            select(func.count(Notification.id))
            .where(Notification.user_id == u.id, Notification.is_read == False)
        ).scalar() or 0
    else:
        try:
            with Session(engine) as s:
                unread = s.execute(
                    select(func.count(Notification.id))
                    .where(Notification.user_id == u.id, Notification.is_read == False)
                ).scalar() or 0
        except Exception:
            pass
    return {
        "user": u,
        "is_admin": u.role.name == "admin",
        "can_manage_users": _has_permission(u, "manage_users"),
        "can_manage_clients": _has_permission(u, "manage_clients"),
        "can_manage_orders": _has_permission(u, "manage_orders"),
        "can_manage_warehouse": _has_permission(u, "manage_warehouse"),
        "can_manage_products": _has_permission(u, "manage_products"),
        "unread_count": unread,
    }


def _paginate(session, q, page: int):
    count_q = select(func.count()).select_from(q.subquery())
    total = session.execute(count_q).scalar() or 0
    pages = max(1, math.ceil(total / PER_PAGE))
    page = max(1, min(page, pages))
    items = session.execute(q.offset((page - 1) * PER_PAGE).limit(PER_PAGE)).unique().scalars().all()
    return items, page, pages, total


def _client_dict(c: Client) -> dict:
    return {"id": c.id, "full_name": c.full_name, "phone": c.phone, "comment": c.comment or ""}


def _recalc_total(session: Session, order_id: int):
    items_sum = session.execute(
        select(func.coalesce(func.sum(OrderItem.price), 0))
        .where(OrderItem.order_id == order_id)
    ).scalar() or 0.0
    parts_sum = session.execute(
        select(func.coalesce(func.sum(OrderPart.quantity * OrderPart.price), 0))
        .where(OrderPart.order_id == order_id)
    ).scalar() or 0.0
    order = session.get(Order, order_id)
    if order:
        order.total_price = float(items_sum) + float(parts_sum)
        session.commit()


def _seed_data():
    from models.client import Client
    from models.service import Service
    from models.warehouse import Part, Product, StockMovement, ProductMovement
    from models.filament import Filament, FilamentMovement

    with Session(engine) as s:
        if s.execute(select(func.count(User.id))).scalar() > 0:
            return
        admin_role = Role(name="admin", permissions='["*"]')
        manager_role = Role(name="manager", permissions=json.dumps([
            "manage_clients", "manage_services", "manage_orders",
            "manage_warehouse", "manage_products",
        ]))
        worker_role = Role(name="worker", permissions=json.dumps([
            "manage_orders", "manage_warehouse", "manage_products",
        ]))
        s.add_all([admin_role, manager_role, worker_role])
        s.flush()
        s.add(User(
            username="admin", password_hash=_hash_password("admin"),
            full_name="Администратор", role_id=admin_role.id,
            inn="770000000000", position="Старший мастер",
        ))
        clients = [
            Client(full_name="Иван Петров", phone="+7 (999) 123-45-67", comment="Постоянный клиент"),
            Client(full_name="Сергей Иванов", phone="+7 (916) 555-33-22", comment=""),
            Client(full_name="Анна Смирнова", phone="+7 (903) 777-88-99", comment="Студия 3D-печати"),
            Client(full_name="ООО «Прототип»", phone="+7 (495) 111-22-33", comment="Юр. лицо, договор №12"),
            Client(full_name="Дмитрий Козлов", phone="+7 (926) 444-55-66", comment="Срочные ремонты"),
        ]
        s.add_all(clients)
        services = [
            Service(name="Диагностика", price=500, description="Полная проверка принтера"),
            Service(name="Замена хотэнда", price=1500, description="Замена нагревательного блока"),
            Service(name="Чистка сопла", price=300, description="Механическая чистка засора"),
            Service(name="Замена терморезистора", price=800, description="NTC 100K"),
            Service(name="Ремонт платы управления", price=3500, description="Диагностика и пайка"),
            Service(name="Калибровка стола", price=600, description="Ручная + авто"),
            Service(name="Замена ремня осей", price=1200, description="GT2 6мм"),
            Service(name="Прошивка Marlin", price=1000, description="Обновление прошивки"),
        ]
        s.add_all(services)
        print_services = [
            Service(name="3D печать (PLA)", price=5, description="За грамм, пластик PLA"),
            Service(name="3D печать (PETG)", price=7, description="За грамм, пластик PETG"),
            Service(name="3D печать (ABS)", price=8, description="За грамм, пластик ABS"),
            Service(name="Постобработка", price=300, description="Удаление поддержек, шлифовка"),
            Service(name="3D моделирование", price=1500, description="Создание модели с нуля"),
        ]
        s.add_all(print_services)
        parts = [
            Part(name="Хотэнд Ender 3", article="HT-E3-V2", purchase_price=450, quantity=15, min_stock=3),
            Part(name="Термистор NTC 100K", article="NTC-100K", purchase_price=120, quantity=30, min_stock=5),
            Part(name="Сопло 0.4мм", article="NOZ-04-BR", purchase_price=80, quantity=50, min_stock=10),
            Part(name="Ремень GT2 6мм", article="GT2-6MM", purchase_price=250, quantity=8, min_stock=2),
            Part(name="Вентилятор 40x40x10", article="FAN-4010", purchase_price=180, quantity=20, min_stock=5),
            Part(name="Нагревательный картридж", article="HTR-24V40", purchase_price=350, quantity=12, min_stock=3),
        ]
        s.add_all(parts)
        products = [
            Product(name="PLA пластик красный", article="PLA-RED-1KG", color="Красный", quantity=25),
            Product(name="PLA пластик чёрный", article="PLA-BLK-1KG", color="Чёрный", quantity=40),
            Product(name="PETG прозрачный", article="PETG-CLR-1KG", color="Прозрачный", quantity=15),
            Product(name="ABS белый", article="ABS-WHT-1KG", color="Белый", quantity=10),
        ]
        s.add_all(products)
        filaments = [
            Filament(name="PLA красный", type="PLA", color="Красный", quantity=2000, min_stock=500),
            Filament(name="PLA чёрный", type="PLA", color="Чёрный", quantity=3000, min_stock=500),
            Filament(name="PETG прозрачный", type="PETG", color="Прозрачный", quantity=1500, min_stock=300),
            Filament(name="ABS белый", type="ABS", color="Белый", quantity=1000, min_stock=300),
        ]
        s.add_all(filaments)
        s.flush()
        for f in filaments:
            s.add(FilamentMovement(filament_id=f.id, type="in", quantity=f.quantity, reason="Начальный остаток"))
        s.flush()
        for p in parts:
            s.add(StockMovement(part_id=p.id, type="in", quantity=p.quantity,
                                price_per_unit=p.purchase_price, reason="Начальный остаток"))
        for p in products:
            s.add(ProductMovement(product_id=p.id, type="in", quantity=p.quantity,
                                  destination="", reason="Начальный остаток"))
        s.commit()
