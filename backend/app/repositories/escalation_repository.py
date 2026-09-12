"""
backend/app/repositories/escalation_repository.py

Repository functions for Escalation records and non-compliant inspection tracking.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.escalation import Escalation
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus


def list_escalations_filtered(
    db: Session,
    level: str | None = None,
    status: str | None = None,
    product_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[Escalation]:
    """
    Lists escalations with optional level, status, and product filters and pagination.
    """
    statement = select(Escalation)
    if level is not None:
        statement = statement.where(Escalation.level == level)
    if status is not None:
        statement = statement.where(Escalation.status == status)
    if product_id is not None:
        statement = statement.where(Escalation.product_id == product_id)
    statement = statement.order_by(Escalation.created_at.desc()).offset(skip).limit(limit)
    return list(db.scalars(statement).all())



def count_non_compliant_inspections_for_product(
    db: Session,
    product_id: int,
) -> int:
    """
    Counts distinct completed non-compliant inspection events for a specific catalog product.
    Does NOT count compliant, review, or failed-processing inspections.
    """
    statement = (
        select(func.count(func.distinct(Inspection.id)))
        .where(
            Inspection.product_id == product_id,
            Inspection.compliance_status == ComplianceStatus.NON_COMPLIANT,
            Inspection.status != InspectionStatus.FAILED,
        )
    )
    return db.scalar(statement) or 0


def get_existing_open_escalation_for_product(
    db: Session,
    product_id: int,
) -> Escalation | None:
    """
    Returns an existing open escalation for a product if one is already active.
    """
    statement = (
        select(Escalation)
        .where(
            Escalation.product_id == product_id,
            Escalation.status == "open",
        )
        .order_by(Escalation.created_at.desc())
        .limit(1)
    )
    return db.scalars(statement).first()


def create_escalation(
    db: Session,
    data: dict,
) -> Escalation:
    """
    Creates and persists a new Escalation record.
    """
    escalation = Escalation(**data)
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    return escalation


def get_escalations_for_product(
    db: Session,
    product_id: int,
) -> list[Escalation]:
    """
    Retrieves all escalation records for a specific product.
    """
    statement = (
        select(Escalation)
        .where(Escalation.product_id == product_id)
        .order_by(Escalation.created_at.desc())
    )
    return list(db.scalars(statement).all())


def get_escalation(
    db: Session,
    escalation_id: int,
) -> Escalation | None:
    """
    Retrieves a single escalation record by its primary key.
    """
    return db.get(Escalation, escalation_id)

def acknowledge_escalation(
    db: Session,
    escalation: Escalation,
    actor_id: int,
) -> Escalation:
    escalation.status = "acknowledged"
    escalation.acknowledged_by = actor_id
    escalation.acknowledged_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(escalation)
    return escalation


def resolve_escalation(
    db: Session,
    escalation: Escalation,
    actor_id: int,
    resolution_notes: str | None = None,
) -> Escalation:
    escalation.status = "resolved"
    escalation.resolved_by = actor_id
    escalation.resolved_at = datetime.now(timezone.utc)
    escalation.resolution_notes = resolution_notes.strip() if resolution_notes else None

    db.commit()
    db.refresh(escalation)
    return escalation


def refer_escalation(
    db: Session,
    escalation: Escalation,
    actor_id: int,
    next_level: str,
    resolution_notes: str | None = None,
) -> Escalation:
    escalation.level = next_level
    escalation.status = "open"
    escalation.resolution_notes = resolution_notes.strip() if resolution_notes else None

    # The current authority's acknowledgement is retained as history;
    # the next authority receives a fresh open state.
    if next_level in ("state", "national"):
        escalation.acknowledged_by = None
        escalation.acknowledged_at = None

    db.commit()
    db.refresh(escalation)
    return escalation

