from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import engine, Base, SessionLocal
from app.models import User, Role
from app.auth import hash_password
from app.routes_clients import router as clients_router
from app.routes_services import router as services_router
from app.routes_orders import router as orders_router
from app.routes_auth import router as auth_router
from app.routes_tasks import router as tasks_router
from app.routes_reports import router as reports_router
from app.routes_attendance import router as attendance_router
from app.routes_export import router as export_router
from app.routes_schedule import router as schedule_router
from app.routes_leads import public as leads_public, protected as leads_protected
from app.routes_audit import router as audit_router

Base.metadata.create_all(bind=engine)

db = SessionLocal()

admin_role = db.query(Role).filter(Role.name == "admin").first()
if not admin_role:
    admin_role = Role(
        name="admin",
        can_view_clients=True,
        can_edit_clients=True,
        can_view_services=True,
        can_edit_services=True,
        can_view_orders=True,
        can_edit_orders=True,
        can_delete_orders=True,
        can_manage_users=True,
    )
    db.add(admin_role)
    db.commit()
    db.refresh(admin_role)

manager_role = db.query(Role).filter(Role.name == "manager").first()
if not manager_role:
    manager_role = Role(
        name="manager",
        can_view_clients=True,
        can_edit_clients=True,
        can_view_services=True,
        can_edit_services=False,
        can_view_orders=True,
        can_edit_orders=True,
        can_manage_users=False,
    )
    db.add(manager_role)
    db.commit()
    db.refresh(manager_role)

if not db.query(User).filter(User.username == "admin").first():
    db.add(User(
        username="admin",
        hashed_password=hash_password("admin123"),
        role_id=admin_role.id,
        full_name="Администратор",
    ))
    db.commit()

db.close()

app = FastAPI(title="CRM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(services_router)
app.include_router(orders_router)
app.include_router(tasks_router)
app.include_router(reports_router)
app.include_router(attendance_router)
app.include_router(export_router)
app.include_router(schedule_router)
app.include_router(leads_public)
app.include_router(leads_protected)
app.include_router(audit_router)


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


@app.get("/login")
def login_page():
    return FileResponse("app/static/login.html")
