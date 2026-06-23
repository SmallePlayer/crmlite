from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models import AuditLog, User
from app.database import SessionLocal


def log(
    user: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[str] = None,
    db: Optional[Session] = None,
):
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
    try:
        log_entry = AuditLog(
            user_id=user.id if user else None,
            user_name=user.full_name or user.username if user else "",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.add(log_entry)
        db.commit()
    finally:
        if own_session:
            db.close()
