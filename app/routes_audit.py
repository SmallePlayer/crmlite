from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog
from app.auth import require_admin, User

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
def get_logs(
    skip: int = 0,
    limit: int = 200,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.query(AuditLog).count()
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": l.id,
                "user_name": l.user_name,
                "action": l.action,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "details": l.details,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
    }
