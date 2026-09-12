from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.user import User
from app.repositories.declaration_repository import get_declarations_for_inspection
from app.repositories.violation_repository import get_violations_for_inspection
from app.schemas.bulk import BulkScanResponse
from app.schemas.inspection import (
    InspectionCreate,
    InspectionDetailResponse,
    InspectionResponse,
    OfficerDecisionRequest,
    OfficerDecisionResponse,
)
from app.schemas.mrp import MRPFindingResponse
from app.services.analysis_service import analyze_inspection
from app.services.compliance_service import evaluate_inspection
from app.services.escalation_service import evaluate_product_escalation
from app.services.image_service import create_inspection_images_bulk
from app.services.inspection_mrp_service import process_inspection_mrp
from app.services.inspection_service import (
    create_inspection,
    finalize_inspection_decision,
    get_inspection,
    list_inspections,
)


router = APIRouter(
    prefix="/inspections",
    tags=["Inspections"],
)


@router.post(
    "",
    response_model=InspectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin", "inspector"))],
)
def create_new_inspection(
    payload: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_inspection(
            db=db,
            inspector=current_user,
            product_id=payload.product_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            location_accuracy_m=payload.location_accuracy_m,
            location_captured_at=payload.location_captured_at,
            location_source=payload.location_source,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/bulk-scan",
    response_model=BulkScanResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin", "inspector"))],
)
def bulk_scan_inspection(
    files: list[UploadFile] = File(...),
    image_types: list[str] | None = Form(None),
    product_id: int | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    location_accuracy_m: float | None = Form(None),
    location_captured_at: datetime | None = Form(None),
    location_source: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Consolidated Bulk Scanning Endpoint:
    1. Creates a new inspection.
    2. Uploads and validates multiple product images.
    3. Executes orientation detection, adaptive OCR, and declaration extraction across all images.
    4. Merges declarations with cross-image conflict detection and evidence provenance.
    5. Evaluates compliance across all 12 Legal Metrology rules in a single pass.
    6. Returns a comprehensive inspection result.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files provided for bulk scan.",
        )

    # 1. Create inspection
    try:
        inspection = create_inspection(
            db=db,
            inspector=current_user,
            product_id=product_id,
            latitude=latitude,
            longitude=longitude,
            location_accuracy_m=location_accuracy_m,
            location_captured_at=location_captured_at,
            location_source=location_source,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 2. Upload and store images
    try:
        upload_result = create_inspection_images_bulk(
            db=db,
            inspection_id=inspection.id,
            upload_files=files,
            image_types=image_types,
        )
    except ValueError as exc:
        inspection.status = InspectionStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if upload_result["successful_count"] == 0:
        inspection.status = InspectionStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All uploaded images failed validation: {upload_result['failed_images']}",
        )

    # 3. Process analysis and compliance
    inspection.status = InspectionStatus.PROCESSING
    db.commit()

    try:
        analysis_result = analyze_inspection(
            db=db,
            inspection_id=inspection.id,
        )

        comp_result = evaluate_inspection(
            db=db,
            inspection_id=inspection.id,
        )

        now = datetime.now(timezone.utc)
        inspection.status = InspectionStatus.COMPLETED
        inspection.completed_at = now
        inspection.scan_completed_at = now
        db.commit()
        db.refresh(inspection)

    except Exception as exc:
        inspection.status = InspectionStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk scan analysis failed: {exc}",
        ) from exc

    # Evaluate product-level escalation after compliance status is finalized
    escalation_record = evaluate_product_escalation(
        db=db,
        inspection_id=inspection.id,
    )
    escalation_data = None
    if escalation_record is not None:
        escalation_data = {
            "id": escalation_record.id,
            "product_id": escalation_record.product_id,
            "trigger_inspection_id": escalation_record.trigger_inspection_id,
            "failed_inspection_count": escalation_record.failed_inspection_count,
            "level": escalation_record.level,
            "status": escalation_record.status,
            "reason": escalation_record.reason,
        }

    violations = get_violations_for_inspection(db, inspection.id)
    violations_data = [
        {
            "id": v.id,
            "field_name": v.field_name,
            "severity": v.severity,
            "status": v.status,
            "message": v.message,
            "detected_value": v.detected_value,
            "expected_value": v.expected_value,
            "confidence": v.confidence,
        }
        for v in violations
    ]

    return {
        "inspection_id": inspection.id,
        "reference_number": inspection.reference_number,
        "total_images": upload_result["total_uploaded"],
        "successfully_processed": analysis_result["successfully_processed"],
        "failed_images": upload_result["failed_images"] + analysis_result.get("failed_images", []),
        "overall_status": str(inspection.compliance_status.value if hasattr(inspection.compliance_status, "value") else inspection.compliance_status),
        "compliance_status": str(inspection.compliance_status.value if hasattr(inspection.compliance_status, "value") else inspection.compliance_status),
        "processing_duration_seconds": analysis_result.get("processing_duration_seconds", 0.0),
        "images": analysis_result.get("images", []),
        "declarations": analysis_result.get("fields", {}),
        "compliance_results": comp_result.get("results", []),
        "violations": violations_data,
        "escalation": escalation_data,
    }


@router.post(
    "/{inspection_id}/analyze",
    response_model=BulkScanResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles("admin", "inspector"))],
)
def run_inspection_analysis(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run full multi-image analysis and compliance evaluation for an existing inspection.
    """
    inspection = get_inspection(
        db=db,
        inspection_id=inspection_id,
    )

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    if (
        inspection.inspector_id != current_user.id
        and current_user.role.name != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this inspection",
        )

    if not inspection.images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No images uploaded for this inspection to analyze.",
        )

    inspection.status = InspectionStatus.PROCESSING
    db.commit()

    try:
        analysis_result = analyze_inspection(
            db=db,
            inspection_id=inspection.id,
        )

        comp_result = evaluate_inspection(
            db=db,
            inspection_id=inspection.id,
        )

        now = datetime.now(timezone.utc)
        inspection.status = InspectionStatus.COMPLETED
        inspection.completed_at = now
        inspection.scan_completed_at = now
        db.commit()
        db.refresh(inspection)

    except Exception as exc:
        inspection.status = InspectionStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inspection analysis failed: {exc}",
        ) from exc

    # Evaluate product-level escalation after compliance status is finalized
    escalation_record = evaluate_product_escalation(
        db=db,
        inspection_id=inspection.id,
    )
    escalation_data = None
    if escalation_record is not None:
        escalation_data = {
            "id": escalation_record.id,
            "product_id": escalation_record.product_id,
            "trigger_inspection_id": escalation_record.trigger_inspection_id,
            "failed_inspection_count": escalation_record.failed_inspection_count,
            "level": escalation_record.level,
            "status": escalation_record.status,
            "reason": escalation_record.reason,
        }

    violations = get_violations_for_inspection(db, inspection.id)
    violations_data = [
        {
            "id": v.id,
            "field_name": v.field_name,
            "severity": v.severity,
            "status": v.status,
            "message": v.message,
            "detected_value": v.detected_value,
            "expected_value": v.expected_value,
            "confidence": v.confidence,
        }
        for v in violations
    ]

    return {
        "inspection_id": inspection.id,
        "reference_number": inspection.reference_number,
        "total_images": len(inspection.images),
        "successfully_processed": analysis_result["successfully_processed"],
        "failed_images": analysis_result.get("failed_images", []),
        "overall_status": str(inspection.compliance_status.value if hasattr(inspection.compliance_status, "value") else inspection.compliance_status),
        "compliance_status": str(inspection.compliance_status.value if hasattr(inspection.compliance_status, "value") else inspection.compliance_status),
        "processing_duration_seconds": analysis_result.get("processing_duration_seconds", 0.0),
        "images": analysis_result.get("images", []),
        "declarations": analysis_result.get("fields", {}),
        "compliance_results": comp_result.get("results", []),
        "violations": violations_data,
        "escalation": escalation_data,
    }




@router.post(
    "/{inspection_id}/decision",
    response_model=OfficerDecisionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles("admin", "inspector"))],
)
def finalize_decision(
    inspection_id: int,
    payload: OfficerDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        inspection = finalize_inspection_decision(
            db=db,
            inspection_id=inspection_id,
            officer=current_user,
            decision=payload.decision,
            remarks=payload.remarks,
        )

        return {
            "inspection_id": inspection.id,
            "decision": inspection.final_decision,
            "decided_by": inspection.final_decision_by,
            "decided_at": inspection.final_decision_at,
            "remarks": inspection.officer_remarks,
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
    "",
    response_model=list[InspectionResponse],
    dependencies=[Depends(require_roles("admin", "inspector", "auditor"))],
)
def get_inspections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_inspections(
        db=db,
        inspector=current_user,
    )


@router.get(
    "/{inspection_id}",
    response_model=InspectionDetailResponse,
    dependencies=[Depends(require_roles("admin", "inspector", "auditor"))],
)
def get_single_inspection(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inspection = get_inspection(
        db=db,
        inspection_id=inspection_id,
    )

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    user_role = getattr(getattr(current_user, "role", None), "name", None)
    if (
        inspection.inspector_id != current_user.id
        and user_role not in ("admin", "auditor")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this inspection",
        )

    violations = get_violations_for_inspection(db, inspection.id)
    setattr(inspection, "violations", violations)

    return inspection


@router.post(
    "/{inspection_id}/process-mrp",
    response_model=MRPFindingResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles("admin", "inspector"))],
)
def process_mrp(
    inspection_id: int,
    pack_quantity: float | None = None,
    pack_unit: str | None = None,
    variant: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inspection = get_inspection(
        db=db,
        inspection_id=inspection_id,
    )

    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    if (
        inspection.inspector_id != current_user.id
        and current_user.role.name != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this inspection",
        )

    try:
        return process_inspection_mrp(
            db=db,
            inspection_id=inspection_id,
            pack_quantity=pack_quantity,
            pack_unit=pack_unit,
            variant=variant,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
