"""
backend/app/api/v1/endpoints/escalations.py

API Endpoints for viewing product-level compliance escalations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.repositories.escalation_repository import (
    get_escalation,
    get_escalations_for_product,
    list_escalations_filtered,
)
from app.schemas.escalation import (
    EscalationActionRequest,
    EscalationActionResponse,
    EscalationResponse,
)
from app.services.inspection_service import get_inspection
from app.services.product_service import get_product
from app.services.escalation_service import process_escalation_action


router = APIRouter(
    prefix="/escalations",
    tags=["Escalations"],
)


@router.get(
    "/",
    response_model=list[EscalationResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                "admin",
                "auditor",
                "district_collector",
                "state_admin",
                "national_admin",
            )
        )
    ],
)
def list_escalations(
    level: str | None = Query(default=None, pattern="^(district|state|national)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|acknowledged|resolved)$"),
    product_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List and filter product compliance escalation records with pagination.
    """
    return list_escalations_filtered(
        db=db,
        level=level,
        status=status_filter,
        product_id=product_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{escalation_id}",
    response_model=EscalationResponse,
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
def get_single_escalation(
    escalation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific product compliance escalation record by its ID.
    """
    escalation = get_escalation(db=db, escalation_id=escalation_id)
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found",
        )

    trigger_inspection = get_inspection(db=db, inspection_id=escalation.trigger_inspection_id)
    user_role = getattr(getattr(current_user, "role", None), "name", None)
    if (
        user_role not in ("admin", "auditor", "district_collector", "state_admin", "national_admin")
        and trigger_inspection is not None
        and trigger_inspection.inspector_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this escalation",
        )

    return escalation


@router.post(
    "/{escalation_id}/action",
    response_model=EscalationActionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_roles(
                "admin",
                "district_collector",
                "state_admin",
                "national_admin",
            )
        )
    ],
)
def process_escalation(
    escalation_id: int,
    payload: EscalationActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        escalation = process_escalation_action(
            db=db,
            escalation_id=escalation_id,
            actor=current_user,
            action=payload.action,
            notes=payload.notes,
        )

        return {
            "escalation_id": escalation.id,
            "action": payload.action,
            "level": escalation.level,
            "status": escalation.status,
            "actor_id": current_user.id,
            "acted_at": (
                escalation.resolved_at
                if payload.action == "resolve"
                else escalation.acknowledged_at
                if payload.action == "acknowledge"
                else escalation.referred_at
                if payload.action in ("refer_state", "refer_national") and escalation.referred_at is not None
                else escalation.updated_at
            ),
            "notes": (
                escalation.resolution_notes
                if payload.notes
                else None
            ),
        }

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/product/{product_id}",
    response_model=list[EscalationResponse],
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
def get_escalations_by_product_id(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all escalation records for a specific product.
    """
    product = get_product(db=db, product_id=product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return get_escalations_for_product(db=db, product_id=product_id)

