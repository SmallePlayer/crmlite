import os
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from config import BASE_DIR, TIMEZONE_OFFSET, PUBLIC_PATHS
from database import engine, Base, get_db
from helpers import _get_user_from_request, _seed_data
from templates_env import templates
from models import *
from routers import (
    auth_router, dashboard_router, clients_router, services_router,
    orders_router, warehouse_router, products_router, filaments_router,
    prints_router, attendance_router, schedule_router, chat_router,
    tasks_router, users_router, audit_router, export_router,
    search_router, api_router,
)


SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for col, dtype in [("order_type", "VARCHAR(20) DEFAULT 'repair'"),
                           ("scheduled_at", "DATETIME"), ("schedule_location", "VARCHAR(300) DEFAULT ''"),
                           ("is_confirmed", "BOOLEAN DEFAULT 0"),
                           ("warranty_days", "INTEGER DEFAULT 0"),
                            ("is_warranty", "BOOLEAN DEFAULT 0"),
                            ("prepaid", "FLOAT DEFAULT 0"),
                            ("estimated_price", "FLOAT DEFAULT 0"),
                            ("source", "VARCHAR(100) DEFAULT ''")]:
            try:
                conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        for col, dtype in [("report", "TEXT DEFAULT ''")]:
            try:
                conn.execute(text(f"ALTER TABLE attendance ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        for col, dtype in [("last_login", "DATETIME")]:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        for col, dtype in [("to_user_id", "INTEGER")]:
            try:
                conn.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        for col, dtype in [("status", "VARCHAR(10) DEFAULT 'success'"),
                            ("waste_grams", "INTEGER DEFAULT 0"),
                            ("printer_name", "VARCHAR(200) DEFAULT ''")]:
            try:
                conn.execute(text(f"ALTER TABLE print_jobs ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        with engine.connect() as pc:
            pc.execute(text("""
                CREATE TABLE IF NOT EXISTS printers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            pc.commit()
        for col, dtype in [("cost_price", "FLOAT DEFAULT 0"),
                            ("print_cost", "FLOAT DEFAULT 0"),
                            ("pack_cost", "FLOAT DEFAULT 0"),
                            ("variants", "TEXT DEFAULT '[]'")]:
            try:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        for col, dtype in [("date_str", "VARCHAR(10) DEFAULT ''")]:
            try:
                conn.execute(text(f"ALTER TABLE attendance ADD COLUMN {col} {dtype}"))
                conn.commit()
                conn.execute(text(
                    "UPDATE attendance SET date_str = strftime('%Y-%m-%d', date) WHERE date_str = ''"
                ))
                conn.commit()
            except Exception:
                pass
        for col, dtype in [("article", "VARCHAR(100) DEFAULT ''"),
                            ("manufacturer", "VARCHAR(100) DEFAULT ''"),
                            ("grams_per_spool", "INTEGER DEFAULT 1000")]:
            try:
                conn.execute(text(f"ALTER TABLE filaments ADD COLUMN {col} {dtype}"))
                conn.commit()
            except Exception:
                pass
        with engine.connect() as nc:
            nc.execute(text("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    title VARCHAR(200) NOT NULL,
                    text TEXT DEFAULT '',
                    link VARCHAR(300) DEFAULT '',
                    is_read BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            nc.commit()
        with engine.connect() as fc:
            fc.execute(text("""
                CREATE TABLE IF NOT EXISTS filaments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    type VARCHAR(50) DEFAULT 'PLA',
                    color VARCHAR(100) DEFAULT '',
                    quantity INTEGER DEFAULT 0,
                    min_stock INTEGER DEFAULT 500,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            fc.execute(text("""
                CREATE TABLE IF NOT EXISTS filament_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filament_id INTEGER NOT NULL REFERENCES filaments(id),
                    type VARCHAR(10) NOT NULL,
                    quantity INTEGER DEFAULT 0,
                    reason VARCHAR(500) DEFAULT '',
                    order_id INTEGER REFERENCES orders(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            fc.execute(text("""
                CREATE TABLE IF NOT EXISTS print_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(300) NOT NULL,
                    filament_id INTEGER NOT NULL REFERENCES filaments(id),
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    grams INTEGER DEFAULT 0,
                    hours FLOAT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            fc.commit()
        for tbl, col in [("tasks", "assigned_to"), ("tasks", "created_by"),
                         ("attendance", "user_id"), ("order_items", "order_id"),
                         ("order_parts", "order_id"), ("orders", "client_id"),
                         ("schedules", "user_id"), ("chat_messages", "from_user_id"),
                         ("orders", "assigned_to")]:
            try:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{tbl}_{col} ON {tbl} ({col})"))
                conn.commit()
            except Exception:
                pass
    _seed_data()
    yield


app = FastAPI(title="CRM — Ремонт 3D принтеров", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(clients_router)
app.include_router(services_router)
app.include_router(orders_router)
app.include_router(warehouse_router)
app.include_router(products_router)
app.include_router(filaments_router)
app.include_router(prints_router)
app.include_router(attendance_router)
app.include_router(schedule_router)
app.include_router(chat_router)
app.include_router(tasks_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(export_router)
app.include_router(search_router)
app.include_router(api_router)


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            {"status": "error", "database": "disconnected", "detail": str(e)},
            status_code=503,
        )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static/"):
        response = await call_next(request)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response
    if path in PUBLIC_PATHS or path.startswith("/api/") or path == "/favicon.ico":
        return await call_next(request)

    user = _get_user_from_request(request)
    request.state.user = user

    if not user and path != "/login":
        return RedirectResponse("/login", status_code=303)

    return await call_next(request)


@app.exception_handler(404)
async def not_found(request: Request, _):
    return templates.TemplateResponse(request, "404.html", {
        "user": getattr(request.state, "user", None),
    }, status_code=404)


@app.exception_handler(400)
async def bad_request(request: Request, exc: HTTPException):
    return templates.TemplateResponse(request, "error.html", {
        "title": "Ошибка", "message": exc.detail or "Некорректный запрос",
        "user": getattr(request.state, "user", None), "unread_count": 0,
    }, status_code=400)


@app.exception_handler(403)
async def forbidden(request: Request, _):
    return templates.TemplateResponse(request, "error.html", {
        "title": "Доступ запрещён", "message": "У вас нет прав для этого действия",
        "user": getattr(request.state, "user", None), "unread_count": 0,
    }, status_code=403)


@app.exception_handler(500)
async def internal_error(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return templates.TemplateResponse(request, "error.html", {
        "title": "Внутренняя ошибка",
        "message": str(exc),
        "user": getattr(request.state, "user", None),
        "unread_count": 0,
    }, status_code=500)
