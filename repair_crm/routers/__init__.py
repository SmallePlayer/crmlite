from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.clients import router as clients_router
from routers.services import router as services_router
from routers.orders import router as orders_router
from routers.warehouse import router as warehouse_router
from routers.products import router as products_router
from routers.filaments import router as filaments_router
from routers.prints import router as prints_router
from routers.attendance import router as attendance_router
from routers.schedule import router as schedule_router
from routers.chat import router as chat_router
from routers.tasks import router as tasks_router
from routers.users import router as users_router
from routers.audit import router as audit_router
from routers.export import router as export_router
from routers.search import router as search_router
from routers.api import router as api_router
from routers.reports import router as reports_router

__all__ = [
    'auth_router', 'dashboard_router', 'clients_router', 'services_router',
    'orders_router', 'warehouse_router', 'products_router', 'filaments_router',
    'prints_router', 'attendance_router', 'schedule_router', 'chat_router',
    'tasks_router', 'users_router', 'audit_router', 'export_router',
    'search_router', 'api_router', 'reports_router'
]
