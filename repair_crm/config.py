import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'repair_crm.db'}")
if DB_URL.startswith("sqlite:///"):
    DB_URL = f"sqlite:///{BASE_DIR / DB_URL.replace('sqlite:///', '')}"

SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-change-me")
TOKEN_EXPIRY = 30 * 24 * 3600

_tz_offset = int(os.getenv("TZ_OFFSET", "3"))
TIMEZONE_OFFSET = timedelta(hours=_tz_offset)

UPLOADS_DIR = BASE_DIR / "static" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

PER_PAGE = 20

ORDER_STATUSES = {
    "in_progress": ("В работе", "warning text-dark"),
    "waiting_parts": ("Ожидает запчастей", "info"),
    "ready": ("Готов к выдаче", "primary"),
    "closed": ("Закрыт", "success"),
}

ORDER_TYPES = {
    "repair": ("Ремонт", "tools"),
    "print": ("3D печать", "printer"),
}

ORDER_FLOW = {
    "in_progress": ["waiting_parts", "ready", "closed"],
    "waiting_parts": ["in_progress", "ready", "closed"],
    "ready": ["in_progress", "closed"],
    "closed": ["in_progress"],
}

AVAILABLE_PERMISSIONS = [
    ("manage_users", "Управление пользователями"),
    ("manage_clients", "Управление клиентами"),
    ("manage_services", "Управление услугами"),
    ("manage_orders", "Управление заказами"),
    ("manage_warehouse", "Управление складом запчастей"),
    ("manage_products", "Управление складом товаров"),
    ("view_audit", "Просмотр аудита"),
]

PUBLIC_PATHS = {"/login", "/api/sse/events", "/api/dashboard",
                "/api/task-assignments", "/api/warehouse/products"}
