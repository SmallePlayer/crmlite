from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Lead, User
from app.auth import get_current_user
from app.audit import log

# открытый роутер — без авторизации (для сайта)
public = APIRouter(prefix="/api/leads", tags=["leads"])
# защищённый роутер — для CRM
protected = APIRouter(prefix="/api/leads", tags=["leads"], dependencies=[Depends(get_current_user)])


class LeadIn(BaseModel):
    name: str
    phone: str
    service_type: str = ""
    message: Optional[str] = None


class LeadOut(BaseModel):
    id: int
    name: str
    phone: str
    service_type: str
    message: Optional[str]
    status: str
    created_at: str

    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    status: str


@public.post("", response_model=LeadOut)
def create_lead(data: LeadIn, db: Session = Depends(get_db)):
    lead = Lead(
        name=data.name,
        phone=data.phone,
        service_type=data.service_type,
        message=data.message,
        status="new",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    log(None, "create", "lead", lead.id, f"Новая заявка от {lead.name} ({lead.phone})", db=db)
    return _lead_out(lead)


@protected.get("", response_model=List[LeadOut])
def list_leads(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Lead)
    if status:
        q = q.filter(Lead.status == status)
    leads = q.order_by(Lead.created_at.desc()).all()
    return [_lead_out(l) for l in leads]


@protected.put("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, data: LeadUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).get(lead_id)
    if not lead:
        raise HTTPException(404, "Заявка не найдена")
    lead.status = data.status
    db.commit()
    db.refresh(lead)
    log(user, "update", "lead", lead.id, f"Статус заявки #{lead.id}: {lead.status}", db=db)
    return _lead_out(lead)


@protected.delete("/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).get(lead_id)
    if not lead:
        raise HTTPException(404, "Заявка не найдена")
    db.delete(lead)
    db.commit()
    log(user, "delete", "lead", lead_id, f"Удалена заявка #{lead_id}", db=db)
    return {"ok": True}


def _lead_out(l: Lead) -> LeadOut:
    return LeadOut(
        id=l.id,
        name=l.name,
        phone=l.phone,
        service_type=l.service_type,
        message=l.message,
        status=l.status,
        created_at=l.created_at.isoformat(),
    )
