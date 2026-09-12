from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "",
    response_model=list[NotificationResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                "admin",
                "inspector",
                "auditor",
                "district_collector",
                "state_admin",
                "national_admin",
            )
        )
    ],
)
def list_notifications(
    escalation_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Notification)
    user_role = getattr(getattr(current_user, "role", None), "name", None)

    if user_role not in ("admin", "auditor"):
        stmt = stmt.where(Notification.recipient_role == user_role)

    if escalation_id is not None:
        stmt = stmt.where(Notification.escalation_id == escalation_id)

    if status_filter:
        stmt = stmt.where(Notification.status == status_filter)

    stmt = stmt.order_by(desc(Notification.created_at))
    return db.scalars(stmt).all()
