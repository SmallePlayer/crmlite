from datetime import datetime
from collections import defaultdict
import time

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from templates_env import templates
from sqlalchemy.orm import Session

from config import TOKEN_EXPIRY, BASE_DIR
from database import get_db
from helpers import (
    _verify_password, _create_token, _audit, _validate_password,
    _hash_password, _user_context,
)
from models.user import User

router = APIRouter()

_login_attempts = defaultdict(list)
RATE_LIMIT_WINDOW = 300
RATE_LIMIT_MAX = 5


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
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _login_attempts[client_ip] = [t for t in _login_attempts[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_login_attempts[client_ip]) >= RATE_LIMIT_MAX:
        return templates.TemplateResponse(request, "login.html", {
            "user": None, "error": "Слишком много попыток. Подождите 5 минут",
        }, status_code=429)
    user = session.execute(
        __import__("sqlalchemy").select(User).where(User.username == username.strip())
    ).scalar_one_or_none()
    if not user or not _verify_password(password, user.password_hash):
        _login_attempts[client_ip].append(now)
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
    is_secure = request.url.scheme == "https"
    response.set_cookie("token", token, max_age=TOKEN_EXPIRY, httponly=True, samesite="lax", secure=is_secure)
    _login_attempts[client_ip] = []
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
