import json

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def create_audit_log(
    db: Session,
    actor: User | None,
    action: str,
    object_type: str,
    object_id: int | None = None,
    details: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor.id if actor is not None else None,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log
