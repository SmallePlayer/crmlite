from fastapi import APIRouter, Depends, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, or_
from sqlalchemy.orm import Session, joinedload

from config import BASE_DIR
from database import get_db
from helpers import _audit, _user_context
from models.user import User
from models.chat import ChatMessage

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, peer: str = Query(""), session: Session = Depends(get_db)):
    u = request.state.user
    if not u:
        raise HTTPException(403)
    users = session.execute(
        select(User).where(User.is_active == True).order_by(User.full_name)
    ).scalars().all()
    peer_id = 0
    peer_name = "Общий чат"
    try:
        peer_id = int(peer.strip()) if peer.strip() else 0
    except ValueError:
        peer_id = 0
    q = select(ChatMessage).options(joinedload(ChatMessage.from_user), joinedload(ChatMessage.to_user))
    if peer_id == 0:
        q = q.where(ChatMessage.to_user_id.is_(None))
    else:
        q = q.where(
            or_(
                (ChatMessage.from_user_id == u.id) & (ChatMessage.to_user_id == peer_id),
                (ChatMessage.from_user_id == peer_id) & (ChatMessage.to_user_id == u.id),
            )
        )
        peer_name = (session.get(User, peer_id) or u).full_name
    q = q.order_by(desc(ChatMessage.created_at)).limit(100)
    messages = session.execute(q).unique().scalars().all()
    return templates.TemplateResponse(request, "chat.html", {
        **_user_context(request, session),
        "messages": list(reversed(messages)), "users": users,
        "current_user_id": u.id, "peer_id": peer_id, "peer_name": peer_name,
    })


@router.post("/chat/send")
def chat_send(request: Request, text: str = Form(...), to_user_id: int = Form(0),
              session: Session = Depends(get_db)):
    u = request.state.user
    if not u or not text.strip():
        raise HTTPException(403)
    session.add(ChatMessage(from_user_id=u.id, to_user_id=to_user_id if to_user_id > 0 else None, text=text.strip()))
    session.commit()
    _audit("chat", "chat", None, f"{u.full_name}: {text.strip()[:50]}", u, session)
    redirect_url = "/chat" if to_user_id == 0 else f"/chat?peer={to_user_id}"
    return RedirectResponse(redirect_url, status_code=303)
