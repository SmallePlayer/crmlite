from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from services.reports import ReportsService
from templates_env import templates
from models import User

router = APIRouter(prefix="/reports", tags=["reports"])


def get_current_user_from_request(request: Request) -> User:
    """Получает текущего пользователя из request"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    return user


@router.get("/", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Страница со статистикой"""
    now = datetime.now()
    
    # Если не указаны год/месяц, используем текущий
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    current_user = get_current_user_from_request(request)
    
    # Проверяем права (только админ и менеджер)
    if current_user.role.name not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    # Генерируем отчёт
    report = ReportsService.generate_monthly_report(db, year, month)
    
    # Навигация по месяцам
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    # Ограничиваем будущее
    can_go_next = (next_year < now.year) or (next_year == now.year and next_month <= now.month)
    
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "user": current_user,
            "report": report,
            "year": year,
            "month": month,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "can_go_next": can_go_next,
            "current_page": "reports"
        }
    )


@router.get("/api/monthly")
async def get_monthly_report_api(
    request: Request,
    year: int = Query(...),
    month: int = Query(...),
    db: Session = Depends(get_db)
):
    """API для получения месячного отчёта в JSON"""
    current_user = get_current_user_from_request(request)
    
    # Проверяем права
    if current_user.role.name not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    report = ReportsService.generate_monthly_report(db, year, month)
    return JSONResponse(content=report)


@router.get("/api/email/{year}/{month}")
async def send_monthly_report_email(
    request: Request,
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """Отправка месячного отчёта на email"""
    current_user = get_current_user_from_request(request)
    
    # Проверяем права
    if current_user.role.name != 'admin':
        raise HTTPException(status_code=403, detail="Только администратор может отправлять отчёты")
    
    # Генерируем отчёт
    report = ReportsService.generate_monthly_report(db, year, month)
    
    # Формируем HTML для email
    html_content = ReportsService.generate_email_html(report)
    
    # Отправляем email (заглушка - нужно реализовать отправку)
    # TODO: Реализовать отправку email через SMTP
    # await send_email(
    #     to="your-email@example.com",
    #     subject=f"Ежемесячный отчёт - {report['period']['month_name']} {year}",
    #     html_content=html_content
    # )
    
    return {
        "status": "success",
        "message": "Отчёт отправлен (заглушка)",
        "report": report
    }
