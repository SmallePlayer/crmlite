from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context
from models.filament import Filament, FilamentMovement
from models.print_job import PrintJob, Printer

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.post("/printers/add")
def add_printer(request: Request, name: str = Form(...), session: Session = Depends(get_db)):
    existing = session.execute(select(Printer).where(Printer.name == name.strip())).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "Такой принтер уже есть")
    p = Printer(name=name.strip())
    session.add(p)
    session.commit()
    _audit("create", "printer", p.id, p.name, request.state.user, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/printers/{pid}/delete")
def delete_printer(pid: int, request: Request, session: Session = Depends(get_db)):
    p = session.get(Printer, pid)
    if not p: raise HTTPException(404)
    session.delete(p)
    session.commit()
    _audit("delete", "printer", pid, p.name, request.state.user, session)
    return RedirectResponse("/prints", status_code=303)


@router.get("/prints", response_class=HTMLResponse)
def print_jobs_page(request: Request, session: Session = Depends(get_db)):
    jobs = session.execute(
        select(PrintJob).options(joinedload(PrintJob.filament), joinedload(PrintJob.creator))
        .order_by(desc(PrintJob.created_at)).limit(100)
    ).unique().scalars().all()
    filaments = session.execute(
        select(Filament).order_by(Filament.name)
    ).scalars().all()
    printers = session.execute(
        select(Printer).order_by(Printer.name)
    ).scalars().all()
    total_jobs = len(jobs)
    success_jobs = sum(1 for j in jobs if j.status == "success")
    fail_jobs = sum(1 for j in jobs if j.status == "fail")
    total_grams = sum(j.grams for j in jobs)
    success_grams = sum(j.grams for j in jobs if j.status == "success")
    fail_grams = sum(j.grams for j in jobs if j.status == "fail")
    waste_grams_total = sum(j.waste_grams for j in jobs if j.status == "fail")
    return templates.TemplateResponse(request, "prints.html", {
        **_user_context(request, session),
        "jobs": jobs, "filaments": filaments, "printers": printers,
        "total_jobs": total_jobs, "success_jobs": success_jobs, "fail_jobs": fail_jobs,
        "total_grams": total_grams, "success_grams": success_grams,
        "fail_grams": fail_grams, "waste_grams_total": waste_grams_total,
    })


@router.post("/prints")
def create_print_job(
    request: Request,
    name: str = Form(...),
    filament_id: int = Form(...),
    grams: int = Form(0),
    hours: float = Form(0),
    printer_name: str = Form(""),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u: raise HTTPException(403)
    f = session.get(Filament, filament_id)
    if not f: raise HTTPException(400, "Пластик не найден")
    if f.quantity < grams: raise HTTPException(400, f"Недостаточно пластика: {f.quantity} г.")
    f.quantity -= grams
    session.add(FilamentMovement(filament_id=filament_id, type="out", quantity=grams, reason=f"Печать: {name.strip()}"))
    session.add(PrintJob(name=name.strip(), filament_id=filament_id, created_by=u.id, grams=grams, hours=hours,
                         printer_name=printer_name.strip()))
    session.flush()
    session.commit()
    _audit("create", "print_job", None, f"{name.strip()} {grams}г", u, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/prints/{job_id}/result")
def mark_print_result(job_id: int, request: Request,
                      status: str = Form(...),
                      waste_grams: int = Form(0),
                      session: Session = Depends(get_db)):
    job = session.get(PrintJob, job_id)
    if not job: raise HTTPException(404)
    job.status = status
    job.waste_grams = waste_grams if status == "fail" else 0
    session.commit()
    _audit("mark_print", "print_job", job_id,
           f"{job.name} → {'успех' if status == 'success' else 'брак'}" +
           (f", {waste_grams} г. брак" if status == "fail" else ""),
           request.state.user, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/prints/{job_id}/edit")
def edit_print_job(job_id: int, request: Request,
                   name: str = Form(...),
                   filament_id: int = Form(...),
                   grams: int = Form(0),
                   hours: float = Form(0),
                   printer_name: str = Form(""),
                   session: Session = Depends(get_db)):
    job = session.get(PrintJob, job_id)
    if not job: raise HTTPException(404)
    old_grams = job.grams
    old_filament_id = job.filament_id
    new_filament = session.get(Filament, filament_id)
    if not new_filament: raise HTTPException(400, "Пластик не найден")
    if old_filament_id == filament_id:
        delta = old_grams - grams
        if delta < 0 and new_filament.quantity < -delta:
            raise HTTPException(400, f"Недостаточно пластика: {new_filament.quantity} г.")
        new_filament.quantity += delta
        if delta > 0:
            session.add(FilamentMovement(filament_id=filament_id, type="in", quantity=delta,
                          reason=f"Корректировка печати: {name.strip()}"))
        elif delta < 0:
            session.add(FilamentMovement(filament_id=filament_id, type="out", quantity=-delta,
                          reason=f"Корректировка печати: {name.strip()}"))
    else:
        old_f = session.get(Filament, old_filament_id)
        if old_f:
            old_f.quantity += old_grams
            session.add(FilamentMovement(filament_id=old_filament_id, type="in", quantity=old_grams,
                          reason=f"Возврат: {job.name}"))
        if new_filament.quantity < grams:
            raise HTTPException(400, f"Недостаточно пластика: {new_filament.quantity} г.")
        new_filament.quantity -= grams
        session.add(FilamentMovement(filament_id=filament_id, type="out", quantity=grams,
                      reason=f"Печать: {name.strip()}"))
    job.name = name.strip()
    job.filament_id = filament_id
    job.grams = grams
    job.hours = hours
    job.printer_name = printer_name.strip()
    session.commit()
    _audit("edit_print", "print_job", job_id, f"{job.name} {grams}г {hours}ч", request.state.user, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/prints/{job_id}/delete")
def delete_print_job(job_id: int, request: Request, session: Session = Depends(get_db)):
    job = session.get(PrintJob, job_id)
    if not job: raise HTTPException(404)
    f = session.get(Filament, job.filament_id)
    if f:
        f.quantity += job.grams
        session.add(FilamentMovement(filament_id=job.filament_id, type="in", quantity=job.grams,
                     reason=f"Аннулирована печать: {job.name}"))
    session.delete(job)
    session.commit()
    _audit("delete", "print_job", job_id, f"{job.name} {job.grams}г", request.state.user, session)
    return RedirectResponse("/prints", status_code=303)
