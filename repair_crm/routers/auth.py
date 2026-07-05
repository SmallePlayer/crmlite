from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import TOKEN_EXPIRY, BASE_DIR
from database import get_db
from helpers import (
    _verify_password, _create_token, _audit, _validate_password,
    _hash_password, _user_context,
)
from models.user import User

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_db),
):
    user = session.execute(
        __import__("sqlalchemy").select(User).where(User.username == username.strip())
    ).scalar_one_or_none()
    if not user or not _verify_password(password, user.password_hash):
        _audit("login_failed", "user", None, f"Неудачный вход: {username.strip()}", None, session)
        return templates.TemplateResponse(request, "login.html", {
            "user": None, "error": "Неверный логин или пароль",
        }, status_code=401)
    if not user.is_active:
        return templates.TemplateResponse(request, "login.html", {
            "user": None, "error": "Учётная запись отключена",
        }, status_code=403)
    user.last_login = datetime.utcnow()
    session.commit()
    token = _create_token(user.id)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("token", token, max_age=TOKEN_EXPIRY, httponly=True)
    _audit("login", "user", user.id, user.full_name, user, session)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("token")
    return response


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, session: Session = Depends(get_db)):
    current = request.state.user
    if not current:
        raise HTTPException(403)
    u = session.get(User, current.id)
    return templates.TemplateResponse(request, "profile.html", {
        **_user_context(request, session),
        "profile": u,
    })


@router.post("/profile/edit")
def profile_edit(
    request: Request,
    full_name: str = Form(...),
    inn: str = Form(""),
    position: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_db),
):
    current = request.state.user
    if not current:
        raise HTTPException(403)
    u = session.get(User, current.id)
    u.full_name = full_name.strip()
    u.inn = inn.strip()
    u.position = position.strip()
    if password.strip():
        pw = _validate_password(password)
        u.password_hash = _hash_password(pw)
    session.commit()
    _audit("update_profile", "user", u.id, u.full_name, u, session)
    return RedirectResponse("/profile", status_code=303)
