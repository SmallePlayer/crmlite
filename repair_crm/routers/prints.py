from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR, PER_PAGE
from database import get_db
from helpers import _audit, _user_context, _paginate
from models.filament import Filament, FilamentMovement
from models.print_job import PrintJob, Printer

router = APIRouter()


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
def print_jobs_page(request: Request, page: int = Query(1), session: Session = Depends(get_db)):
    q = select(PrintJob).options(joinedload(PrintJob.filament), joinedload(PrintJob.creator))
    q = q.order_by(desc(PrintJob.created_at))
    jobs, page, pages, total = _paginate(session, q, page)
    filaments = session.execute(
        select(Filament).order_by(Filament.name)
    ).scalars().all()
    printers = session.execute(
        select(Printer).order_by(Printer.name)
    ).scalars().all()
    all_jobs = session.execute(
        select(PrintJob).order_by(desc(PrintJob.created_at)).limit(1000)
    ).scalars().all()
    total_jobs = len(all_jobs)
    success_jobs = sum(1 for j in all_jobs if j.status == "success")
    fail_jobs = sum(1 for j in all_jobs if j.status == "fail")
    total_grams = sum(j.grams for j in all_jobs)
    success_grams = sum(j.grams for j in all_jobs if j.status == "success")
    fail_grams = sum(j.grams for j in all_jobs if j.status == "fail")
    waste_grams_total = sum(j.waste_grams for j in all_jobs if j.status == "fail")
    return templates.TemplateResponse(request, "prints.html", {
        **_user_context(request, session),
        "jobs": jobs, "filaments": filaments, "printers": printers,
        "page": page, "pages": pages, "total": total,
        "total_jobs": total_jobs, "success_jobs": success_jobs, "fail_jobs": fail_jobs,
        "total_grams": total_grams, "success_grams": success_grams,
        "fail_grams": fail_grams, "waste_grams_total": waste_grams_total,
    })


@router.post("/prints")
def create_print_job(
    request: Request,
    name: str = Form(...),
    filament_id: int = Form(...),
    hours: float = Form(0),
    printer_name: str = Form(""),
    slicer_estimate: int = Form(0),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u: raise HTTPException(403)
    f = session.get(Filament, filament_id)
    if not f: raise HTTPException(400, "Пластик не найден")
    session.add(PrintJob(name=name.strip(), filament_id=filament_id, created_by=u.id, hours=hours,
                         printer_name=printer_name.strip(), slicer_estimate=slicer_estimate))
    session.commit()
    _audit("create", "print_job", None, f"{name.strip()}", u, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/prints/{job_id}/result")
def mark_print_result(job_id: int, request: Request,
                      status: str = Form(...),
                      weight_good: int = Form(0),
                      weight_waste: int = Form(0),
                      session: Session = Depends(get_db)):
    job = session.get(PrintJob, job_id)
    if not job: raise HTTPException(404)
    if job.status != "pending":
        raise HTTPException(400, "Результат уже отмечен")
    
    f = session.get(Filament, job.filament_id)
    if not f: raise HTTPException(400, "Пластик не найден")
    
    job.status = status
    job.weight_good = weight_good
    job.weight_waste = weight_waste
    
    if status == "success":
        total_consumed = weight_good
        job.grams = weight_good
        job.waste_grams = 0
        if f.quantity < total_consumed:
            raise HTTPException(400, f"Недостаточно пластика: {f.quantity} г.")
        f.quantity -= total_consumed
        session.add(FilamentMovement(
            filament_id=job.filament_id, type="out", quantity=total_consumed,
            reason=f"Печать: {job.name}"
        ))
    else:
        total_consumed = weight_good + weight_waste
        job.grams = total_consumed
        job.waste_grams = weight_waste
        if f.quantity < total_consumed:
            raise HTTPException(400, f"Недостаточно пластика: {f.quantity} г.")
        f.quantity -= total_consumed
        session.add(FilamentMovement(
            filament_id=job.filament_id, type="out", quantity=total_consumed,
            reason=f"Брак печати: {job.name}"
        ))
    
    session.commit()
    _audit("mark_print", "print_job", job_id,
           f"{job.name} → {'успех' if status == 'success' else 'брак'}" +
           (f", {total_consumed} г. расход" if status == "success" else f", {weight_good} г. деталь + {weight_waste} г. брак"),
           request.state.user, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/prints/{job_id}/edit")
def edit_print_job(job_id: int, request: Request,
                   name: str = Form(...),
                   filament_id: int = Form(...),
                   hours: float = Form(0),
                   printer_name: str = Form(""),
                   slicer_estimate: int = Form(0),
                   session: Session = Depends(get_db)):
    job = session.get(PrintJob, job_id)
    if not job: raise HTTPException(404)
    
    old_filament_id = job.filament_id
    new_filament = session.get(Filament, filament_id)
    if not new_filament: raise HTTPException(400, "Пластик не найден")
    
    if job.status != "pending":
        if old_filament_id != filament_id:
            old_consumed = job.grams
            old_f = session.get(Filament, old_filament_id)
            if old_f:
                old_f.quantity += old_consumed
                session.add(FilamentMovement(filament_id=old_filament_id, type="in", quantity=old_consumed,
                              reason=f"Корректировка: {job.name}"))
            new_consumed = job.grams
            if new_filament.quantity < new_consumed:
                raise HTTPException(400, f"Недостаточно пластика: {new_filament.quantity} г.")
            new_filament.quantity -= new_consumed
            session.add(FilamentMovement(filament_id=filament_id, type="out", quantity=new_consumed,
                          reason=f"Корректировка: {job.name}"))
    
    job.name = name.strip()
    job.filament_id = filament_id
    job.hours = hours
    job.printer_name = printer_name.strip()
    job.slicer_estimate = slicer_estimate
    session.commit()
    _audit("edit_print", "print_job", job_id, f"{job.name}", request.state.user, session)
    return RedirectResponse("/prints", status_code=303)


@router.post("/prints/{job_id}/delete")
def delete_print_job(job_id: int, request: Request, session: Session = Depends(get_db)):
    job = session.get(PrintJob, job_id)
    if not job: raise HTTPException(404)
    if job.status == "pending":
        pass
    else:
        f = session.get(Filament, job.filament_id)
        if f:
            f.quantity += job.grams
            session.add(FilamentMovement(filament_id=job.filament_id, type="in", quantity=job.grams,
                         reason=f"Аннулирована печать: {job.name}"))
    session.delete(job)
    session.commit()
    _audit("delete", "print_job", job_id, f"{job.name}", request.state.user, session)
    return RedirectResponse("/prints", status_code=303)
