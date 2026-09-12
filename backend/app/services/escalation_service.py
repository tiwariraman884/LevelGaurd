from datetime import datetime, timezone

"""
backend/app/services/escalation_service.py

Service layer for evaluating and managing product-level compliance escalations.
"""

from sqlalchemy.orm import Session

from app.models.escalation import Escalation
from app.models.inspection import ComplianceStatus, Inspection
from app.repositories.escalation_repository import (
    count_non_compliant_inspections_for_product,
    create_escalation,
    get_existing_open_escalation_for_product,
)
from app.services.inspection_service import get_inspection
from app.services.audit_service import create_audit_log
from app.services.notification_service import (
    create_district_collector_notification,
    create_escalation_notification,
)


ESCALATION_NON_COMPLIANT_THRESHOLD = 3
INITIAL_ESCALATION_LEVEL = "district"


def evaluate_product_escalation(
    db: Session,
    inspection_id: int,
) -> Escalation | None:
    """
    Evaluates whether the inspection triggers a product-level escalation.

    Business Rules:
    1. Only inspections with a registered catalog product_id can escalate.
    2. Only inspections with finalized compliance_status == NON_COMPLIANT count.
    3. Escalates when distinct non-compliant inspection count > 3 (i.e. 4th event).
    4. If an open escalation already exists for the product, prevents duplicate creation
       and returns the existing open escalation record.
    5. Initial escalation level is 'state'.
    """
    inspection: Inspection | None = get_inspection(db, inspection_id)
    if inspection is None:
        return None

    if inspection.product_id is None:
        return None

    # Only non-compliant inspections can trigger/increment escalation
    comp_status = (
        inspection.compliance_status.value
        if hasattr(inspection.compliance_status, "value")
        else str(inspection.compliance_status)
    )
    if comp_status != ComplianceStatus.NON_COMPLIANT.value and comp_status != "non_compliant":
        return None

    # Count distinct non-compliant inspection events for this product
    failed_count = count_non_compliant_inspections_for_product(
        db=db,
        product_id=inspection.product_id,
    )

    if failed_count <= ESCALATION_NON_COMPLIANT_THRESHOLD:
        return None

    # Check for existing open escalation
    existing_open = get_existing_open_escalation_for_product(
        db=db,
        product_id=inspection.product_id,
    )
    if existing_open is not None:
        return existing_open

    # Create new escalation linked to trigger inspection
    reason = (
        f"Product has reached {failed_count} distinct non-compliant inspection events, "
        f"exceeding the threshold of {ESCALATION_NON_COMPLIANT_THRESHOLD}."
    )

    escalation_data = {
        "product_id": inspection.product_id,
        "trigger_inspection_id": inspection.id,
        "failed_inspection_count": failed_count,
        "level": INITIAL_ESCALATION_LEVEL,
        "status": "open",
        "reason": reason,
    }

    escalation = create_escalation(db=db, data=escalation_data)

    create_district_collector_notification(
        db=db,
        escalation=escalation,
    )

    create_audit_log(
        db=db,
        actor=None,
        action="ESCALATION_CREATED",
        object_type="escalation",
        object_id=escalation.id,
        details={
            "product_id": escalation.product_id,
            "trigger_inspection_id": escalation.trigger_inspection_id,
            "failed_inspection_count": escalation.failed_inspection_count,
            "level": escalation.level,
            "status": escalation.status,
        },
    )

    return escalation

def process_escalation_action(
    db: Session,
    escalation_id: int,
    actor,
    action: str,
    notes: str | None = None,
) -> Escalation:
    """
    Process an authorized escalation action.

    district_collector:
        acknowledge, resolve, refer_state

    state_admin:
        acknowledge, resolve, refer_national

    national_admin:
        acknowledge, resolve
    """
    escalation = db.get(Escalation, escalation_id)

    if escalation is None:
        raise LookupError("Escalation not found")

    role_name = getattr(getattr(actor, "role", None), "name", None)
    normalized_action = action.strip().lower()
    normalized_notes = notes.strip() if notes else None

    permissions = {
        "district_collector": {"acknowledge", "resolve", "refer_state"},
        "state_admin": {"acknowledge", "resolve", "refer_national"},
        "national_admin": {"acknowledge", "resolve"},
        "admin": {"acknowledge", "resolve", "refer_state", "refer_national"},
    }

    if role_name not in permissions:
        raise PermissionError(
            "This role cannot perform escalation actions."
        )

    if normalized_action not in permissions[role_name]:
        raise PermissionError(
            f"Role '{role_name}' cannot perform action '{normalized_action}'."
        )

    current_level = escalation.level

    role_level = {
        "district_collector": "district",
        "state_admin": "state",
        "national_admin": "national",
    }

    if role_name in role_level and current_level != role_level[role_name]:
        raise PermissionError(
            f"Role '{role_name}' cannot act on {current_level}-level escalations."
        )

    if normalized_action == "acknowledge":
        if escalation.status not in ("open", "acknowledged"):
            raise ValueError(
                "Only open or acknowledged escalations can be acknowledged."
            )

        escalation.status = "acknowledged"
        escalation.acknowledged_by = actor.id
        escalation.acknowledged_at = datetime.now(timezone.utc)

    elif normalized_action == "resolve":
        if escalation.status == "resolved":
            raise ValueError("Escalation is already resolved.")

        if escalation.status != "acknowledged":
            raise ValueError(
                "Escalation must be acknowledged before it can be resolved."
            )

        if not normalized_notes:
            raise ValueError("Resolution notes are required.")

        escalation.status = "resolved"
        escalation.resolved_by = actor.id
        escalation.resolved_at = datetime.now(timezone.utc)
        escalation.resolution_notes = normalized_notes

    elif normalized_action == "refer_state":
        if escalation.status == "resolved":
            raise ValueError("Cannot refer a resolved escalation.")

        if current_level != "district":
            raise ValueError(
                "Only district-level escalations can be referred to state."
            )

        escalation.level = "state"
        escalation.status = "open"
        escalation.acknowledged_by = None
        escalation.acknowledged_at = None
        escalation.referred_by = actor.id
        escalation.referred_at = datetime.now(timezone.utc)
        escalation.resolution_notes = normalized_notes

    elif normalized_action == "refer_national":
        if escalation.status == "resolved":
            raise ValueError("Cannot refer a resolved escalation.")

        if current_level != "state":
            raise ValueError(
                "Only state-level escalations can be referred to national."
            )

        escalation.level = "national"
        escalation.status = "open"
        escalation.acknowledged_by = None
        escalation.acknowledged_at = None
        escalation.referred_by = actor.id
        escalation.referred_at = datetime.now(timezone.utc)
        escalation.resolution_notes = normalized_notes

    else:
        raise ValueError("Invalid escalation action.")

    db.commit()
    db.refresh(escalation)

    if normalized_action in ("refer_state", "refer_national"):
        create_escalation_notification(
            db=db,
            escalation=escalation,
        )

    create_audit_log(
        db=db,
        actor=actor,
        action=f"ESCALATION_{normalized_action.upper()}",
        object_type="escalation",
        object_id=escalation.id,
        details={
            "level": escalation.level,
            "status": escalation.status,
            "notes": normalized_notes,
        },
    )

    return escalation

