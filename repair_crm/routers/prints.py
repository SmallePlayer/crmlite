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
        "jobs": jobs, "filaments": filaments,
        "page": page, "pages": pages, "total": total,
        "total_jobs": total_jobs, "success_jobs": success_jobs, "fail_jobs": fail_jobs,
        "total_grams": total_grams, "success_grams": success_grams,
        "fail_grams": fail_grams, "waste_grams_total": waste_grams_total,
    })


@router.post("/prints")
def create_print_job(
    request: Request,
    name: str = Form(""),
    filament_id: int = Form(...),
    grams: int = Form(...),
    status: str = Form("success"),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u: raise HTTPException(403)
    if grams <= 0: raise HTTPException(400, "Укажите вес")
    f = session.get(Filament, filament_id)
    if not f: raise HTTPException(400, "Пластик не найден")
    if f.quantity < grams: raise HTTPException(400, f"Недостаточно пластика: {f.quantity} г.")
    f.quantity -= grams
    job_name = name.strip() or ("Брак" if status == "fail" else "Печать")
    session.add(FilamentMovement(filament_id=filament_id, type="out", quantity=grams,
                 reason=f"{'Брак' if status == 'fail' else 'Печать'}: {job_name}"))
    session.add(PrintJob(name=job_name, filament_id=filament_id, created_by=u.id,
                         grams=grams, status=status,
                         weight_good=grams if status == "success" else 0,
                         weight_waste=grams if status == "fail" else 0))
    session.commit()
    _audit("create", "print_job", None,
           f"{job_name} {grams}г → {'успех' if status == 'success' else 'брак'}", u, session)
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
