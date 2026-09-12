from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inspection import Inspection, InspectionStatus
from app.models.user import User
from app.services.audit_service import create_audit_log


def generate_reference_number() -> str:
    return f"LG-{uuid4().hex[:10].upper()}"


def validate_location_metadata(
    latitude: float | None = None,
    longitude: float | None = None,
    location_accuracy_m: float | None = None,
    location_captured_at: datetime | None = None,
    location_source: str | None = None,
) -> tuple[float | None, float | None, float | None, datetime | None, str | None]:
    if (latitude is None) != (longitude is None):
        raise ValueError("Both latitude and longitude must be provided together.")
    if latitude is not None and not (-90.0 <= latitude <= 90.0):
        raise ValueError("Latitude must be between -90 and 90 degrees.")
    if longitude is not None and not (-180.0 <= longitude <= 180.0):
        raise ValueError("Longitude must be between -180 and 180 degrees.")
    if location_accuracy_m is not None and location_accuracy_m < 0:
        raise ValueError("Location accuracy must be greater than or equal to 0.")
    if location_source is not None and len(location_source) > 30:
        raise ValueError("Location source must not exceed 30 characters.")
    if location_captured_at is not None and location_captured_at.tzinfo is None:
        location_captured_at = location_captured_at.replace(tzinfo=timezone.utc)
    return latitude, longitude, location_accuracy_m, location_captured_at, location_source


def create_inspection(
    db: Session,
    inspector: User,
    product_id: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    location_accuracy_m: float | None = None,
    location_captured_at: datetime | None = None,
    location_source: str | None = None,
) -> Inspection:
    (
        val_lat,
        val_lng,
        val_acc,
        val_captured_at,
        val_source,
    ) = validate_location_metadata(
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=location_accuracy_m,
        location_captured_at=location_captured_at,
        location_source=location_source,
    )

    inspection = Inspection(
        inspector_id=inspector.id,
        product_id=product_id,
        reference_number=generate_reference_number(),
        status=InspectionStatus.CREATED,
        latitude=val_lat,
        longitude=val_lng,
        location_accuracy_m=val_acc,
        location_captured_at=val_captured_at,
        location_source=val_source,
        scan_started_at=datetime.now(timezone.utc),
    )

    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    return inspection


def get_inspection(
    db: Session,
    inspection_id: int,
) -> Inspection | None:
    return db.get(Inspection, inspection_id)


def list_inspections(
    db: Session,
    inspector: User,
) -> list[Inspection]:
    role_name = getattr(getattr(inspector, "role", None), "name", None)
    if role_name in ("admin", "auditor"):
        statement = select(Inspection).order_by(Inspection.created_at.desc())
    else:
        statement = (
            select(Inspection)
            .where(Inspection.inspector_id == inspector.id)
            .order_by(Inspection.created_at.desc())
        )

    return list(db.scalars(statement).all())

def finalize_inspection_decision(
    db: Session,
    inspection_id: int,
    officer: User,
    decision: str,
    remarks: str | None = None,
) -> Inspection:
    """
    Persist the authorized officer's final decision separately from the
    AI/rule-engine compliance screening result.

    Decision mapping:
    APPROVED        -> COMPLIANT
    REJECTED        -> NON_COMPLIANT
    REVIEW_REQUIRED -> REVIEW
    """
    inspection = db.get(Inspection, inspection_id)

    if inspection is None:
        raise LookupError("Inspection not found")

    role_name = getattr(getattr(officer, "role", None), "name", None)
    if role_name not in ("admin", "inspector"):
        raise PermissionError(
            "Only admin or inspector can finalize an inspection decision."
        )

    if role_name == "inspector" and inspection.inspector_id != officer.id:
        raise PermissionError(
            "You do not have access to finalize this inspection."
        )

    normalized_remarks = remarks.strip() if remarks else None

    if decision == "APPROVED":
        compliance_status = "compliant"
    elif decision == "REJECTED":
        compliance_status = "non_compliant"
    elif decision == "REVIEW_REQUIRED":
        compliance_status = "review"
    else:
        raise ValueError("Invalid officer decision.")

    inspection.final_decision = decision
    inspection.final_decision_by = officer.id
    inspection.final_decision_at = datetime.now(timezone.utc)
    inspection.officer_remarks = normalized_remarks

    # Keep the existing compliance field synchronized with the authorized
    # final outcome after officer review.
    inspection.compliance_status = compliance_status

    db.commit()
    db.refresh(inspection)

    create_audit_log(
        db=db,
        actor=officer,
        action="OFFICER_FINAL_DECISION",
        object_type="inspection",
        object_id=inspection.id,
        details={
            "decision": decision,
            "compliance_status": inspection.compliance_status.value
            if hasattr(inspection.compliance_status, "value")
            else str(inspection.compliance_status),
            "remarks": normalized_remarks,
        },
    )

    return inspection

