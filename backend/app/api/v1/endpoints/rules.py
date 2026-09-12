from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.rule_version import RuleVersion
from app.models.user import User
from app.schemas.rule import RuleResponse


router = APIRouter(
    prefix="/rules",
    tags=["Rules"],
)


@router.get(
    "",
    response_model=list[RuleResponse],
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
def get_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(RuleVersion)
        .options(selectinload(RuleVersion.checks))
        .order_by(RuleVersion.rule_code)
    )
    rules = db.scalars(stmt).all()
    results = []
    for r in rules:
        r_dict = {
            "id": r.id,
            "rule_code": r.rule_code,
            "rule_number": r.rule_number,
            "version": r.version,
            "title": r.title,
            "requirement": r.requirement,
            "effective_from": r.effective_from,
            "effective_to": r.effective_to,
            "status": r.status,
            "approval_status": r.approval_status,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "checks_count": len(r.checks) if r.checks else 0,
            "checks": [
                {
                    "id": c.id,
                    "field_name": c.field_name,
                    "operator": c.operator,
                    "expected_value": c.expected_value,
                    "expected_unit": c.expected_unit,
                    "severity": c.severity,
                    "failure_message": c.failure_message,
                }
                for c in (r.checks or [])
            ],
        }
        results.append(r_dict)
    return results


@router.get(
    "/{rule_id}",
    response_model=RuleResponse,
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
def get_single_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(RuleVersion)
        .where(RuleVersion.id == rule_id)
        .options(selectinload(RuleVersion.checks))
    )
    r = db.scalar(stmt)
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    return {
        "id": r.id,
        "rule_code": r.rule_code,
        "rule_number": r.rule_number,
        "version": r.version,
        "title": r.title,
        "requirement": r.requirement,
        "effective_from": r.effective_from,
        "effective_to": r.effective_to,
        "status": r.status,
        "approval_status": r.approval_status,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "checks_count": len(r.checks) if r.checks else 0,
        "checks": [
            {
                "id": c.id,
                "field_name": c.field_name,
                "operator": c.operator,
                "expected_value": c.expected_value,
                "expected_unit": c.expected_unit,
                "severity": c.severity,
                "failure_message": c.failure_message,
            }
            for c in (r.checks or [])
        ],
    }
