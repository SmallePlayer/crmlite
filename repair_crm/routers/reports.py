from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import json

from database import get_db
from services.reports import ReportsService
from templates_env import templates
from helpers import _user_context

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Страница со статистикой"""
    now = datetime.now()
    
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if current_user.role.name not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    report = ReportsService.generate_monthly_report(db, year, month)
    
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
    
    can_go_next = (next_year < now.year) or (next_year == now.year and next_month <= now.month)
    
    context = _user_context(request, db)
    context.update({
        "report": report,
        "year": year,
        "month": month,
        "prev_year": prev_year,
        "prev_month": prev_month,
        "next_year": next_year,
        "next_month": next_month,
        "can_go_next": can_go_next,
        "current_page": "reports"
    })
    
    return templates.TemplateResponse(request, "reports.html", context)


@router.get("/api/monthly")
async def get_monthly_report_api(
    request: Request,
    year: int = Query(...),
    month: int = Query(...),
    download: Optional[bool] = Query(False),
    db: Session = Depends(get_db)
):
    """API для получения месячного отчёта в JSON"""
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if current_user.role.name not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    report = ReportsService.generate_monthly_report(db, year, month)
    
    if download:
        month_name = ReportsService._get_month_name(month)
        filename = f"report_{month_name}_{year}.json"
        return Response(
            content=json.dumps(report, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    return JSONResponse(content=report)


@router.get("/api/email/{year}/{month}")
async def send_monthly_report_email(
    request: Request,
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """Отправка месячного отчёта на email"""
    current_user = getattr(request.state, "user", None)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    if current_user.role.name not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    report = ReportsService.generate_monthly_report(db, year, month)
    html_content = ReportsService.generate_email_html(report)
    
    return {
        "status": "success",
        "message": "Отчёт отправлен (заглушка)",
        "report": report
    }
