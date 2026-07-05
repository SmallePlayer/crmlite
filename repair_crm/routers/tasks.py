from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context
from models.user import User
from models.task import Task

router = APIRouter()


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    filter: str = Query("all"),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u:
        raise HTTPException(403)

    users = session.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    ).scalars().all()

    q = select(Task).options(
        joinedload(Task.creator), joinedload(Task.assignee),
    )
    if filter == "my":
        q = q.where(Task.assigned_to == u.id)
    elif filter == "assigned":
        q = q.where(Task.created_by == u.id, Task.assigned_to != u.id)
    elif filter == "done":
        q = q.where(Task.status == "done")
    elif filter == "pending":
        q = q.where(Task.status == "pending")
    q = q.order_by(desc(Task.created_at))

    tasks = session.execute(q).unique().scalars().all()

    counts = {}
    for f_val, f_label, f_cond in [
        ("all", "Все", True),
        ("my", "Мои", Task.assigned_to == u.id),
        ("assigned", "Назначил", (Task.created_by == u.id) & (Task.assigned_to != u.id)),
        ("pending", "Активные", Task.status == "pending"),
        ("done", "Выполнены", Task.status == "done"),
    ]:
        cnt_q = select(func.count(Task.id))
        if f_cond is not True:
            cnt_q = cnt_q.where(f_cond)
        counts[f_val] = session.execute(cnt_q).scalar() or 0

    return templates.TemplateResponse(request, "tasks.html", {
        **_user_context(request, session),
        "tasks": tasks, "users": users, "filter": filter, "counts": counts,
    })


@router.post("/tasks")
def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    assigned_to: int = Form(...),
    session: Session = Depends(get_db),
):
    u = request.state.user
    if not u:
        raise HTTPException(403)
    target = session.get(User, assigned_to)
    if not target:
        raise HTTPException(400, "Пользователь не найден")
    task = Task(
        title=title.strip(),
        description=description.strip(),
        created_by=u.id,
        assigned_to=assigned_to,
    )
    session.add(task)
    session.commit()
    _audit("create", "task", task.id, f"«{task.title}» → {target.full_name}", u, session)
    return RedirectResponse("/tasks", status_code=303)


@router.post("/tasks/{task_id}/done")
def mark_task_done(task_id: int, request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u:
        raise HTTPException(403)
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404)
    task.status = "done"
    task.completed_at = datetime.utcnow()
    session.commit()
    _audit("done", "task", task.id, f"«{task.title}» выполнена", u, session)
    return RedirectResponse("/tasks", status_code=303)


@router.post("/tasks/{task_id}/delete")
def delete_task(task_id: int, request: Request, session: Session = Depends(get_db)):
    u = request.state.user
    if not u:
        raise HTTPException(403)
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(404)
    if task.created_by != u.id and u.role.name != "admin":
        raise HTTPException(403, "Удалить может только автор или администратор")
    session.delete(task)
    session.commit()
    _audit("delete", "task", task_id, f"«{task.title}»", u, session)
    return RedirectResponse("/tasks", status_code=303)
