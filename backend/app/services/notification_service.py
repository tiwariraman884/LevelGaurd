from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.escalation import Escalation
from app.models.notification import Notification, NotificationStatus
from app.models.product import Product


LEVEL_RECIPIENTS = {
    "district": "district_collector",
    "state": "state_admin",
    "national": "national_admin",
}


def create_escalation_notification(
    db: Session,
    escalation: Escalation,
) -> Notification:
    recipient_role = LEVEL_RECIPIENTS.get(escalation.level)

    if recipient_role is None:
        raise ValueError(
            f"Unsupported escalation notification level: {escalation.level}"
        )

    product = db.get(Product, escalation.product_id)

    product_label = (
        getattr(product, "brand", None)
        or getattr(product, "name", None)
        or f"Product #{escalation.product_id}"
    )

    subject = (
        f"LABELGUARD Escalation - {product_label} - "
        f"{escalation.level.upper()}"
    )

    message = (
        f"Compliance escalation requires {escalation.level}-level attention. "
        f"Product ID: {escalation.product_id}. "
        f"Trigger inspection: {escalation.trigger_inspection_id}. "
        f"Non-compliant inspection count: {escalation.failed_inspection_count}. "
        f"Reason: {escalation.reason}"
    )

    existing = db.scalar(
        select(Notification)
        .where(
            Notification.escalation_id == escalation.id,
            Notification.recipient_role == recipient_role,
            Notification.status.in_(
                [
                    NotificationStatus.PENDING,
                    NotificationStatus.NOT_CONFIGURED,
                    NotificationStatus.SENT,
                ]
            ),
        )
        .order_by(Notification.id.desc())
        .limit(1)
    )

    if existing is not None:
        return existing

    notification = Notification(
        escalation_id=escalation.id,
        recipient_role=recipient_role,
        recipient_name={
            "district_collector": "District Collector",
            "state_admin": "State Admin",
            "national_admin": "National Admin",
        }[recipient_role],
        recipient_email=None,
        channel="in_app",
        subject=subject,
        message=message,
        status=NotificationStatus.PENDING,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


def create_district_collector_notification(
    db: Session,
    escalation: Escalation,
) -> Notification:
    return create_escalation_notification(
        db=db,
        escalation=escalation,
    )
