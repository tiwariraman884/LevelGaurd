"""
backend/app/reports/report_data.py

Centralized Canonical Report Data Builder for LABELGUARD Inspections.
Constructs a single, fully serializable payload consumed by PDF, DOCX, and API exporters.
"""

from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inspection import Inspection
from app.models.regulation import Regulation
from app.models.rule_version import RuleVersion
from app.repositories.declaration_repository import get_declarations_for_inspection
from app.repositories.inspection_repository import get_inspection
from app.repositories.rule_repository import get_active_rule_versions
from app.repositories.violation_repository import get_violations_for_inspection
from app.services.compliance_service import evaluate_inspection


GENERATOR_VERSION = "labelguard-report-v1"
BASE_DIR = Path(__file__).resolve().parents[2]


def _format_datetime_iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(dt, date):
        return dt.isoformat()
    return str(dt)


def _resolve_filesystem_path(stored_path: str | None) -> str | None:
    if not stored_path:
        return None
    path = Path(stored_path)
    if path.is_absolute() and path.exists():
        return str(path)

    # Try resolving relative to backend directory
    candidate = BASE_DIR / stored_path
    if candidate.exists():
        return str(candidate)

    # Try resolving relative to storage directory
    candidate_storage = BASE_DIR / "storage" / stored_path
    if candidate_storage.exists():
        return str(candidate_storage)

    return str(path.resolve()) if path.is_absolute() else str((BASE_DIR / stored_path).resolve())


def _parse_evidence_json(evidence_raw: str | None) -> Any:
    if not evidence_raw:
        return None
    try:
        return json.loads(evidence_raw)
    except (ValueError, TypeError):
        return evidence_raw


def build_inspection_report_data(
    db: Session,
    inspection_id: int,
    report_format: str | None = None,
) -> dict[str, Any]:
    """
    Constructs a comprehensive, canonical, and serializable dictionary representing
    the complete inspection report evidence, inspector details, product data,
    GPS location, images, declarations, violations, rule evaluations, and regulatory traceability.
    """
    inspection: Inspection | None = get_inspection(db, inspection_id)
    if inspection is None:
        raise ValueError(f"Inspection with ID {inspection_id} does not exist.")

    # 1. Inspection identity
    status_str = (
        inspection.status.value
        if hasattr(inspection.status, "value")
        else str(inspection.status)
    )
    compliance_status_str = (
        inspection.compliance_status.value
        if hasattr(inspection.compliance_status, "value")
        else str(inspection.compliance_status)
    )

    inspection_identity = {
        "inspection_id": inspection.id,
        "reference_number": inspection.reference_number,
        "status": status_str,
        "compliance_status": compliance_status_str,
        "created_at": _format_datetime_iso(inspection.created_at),
        "completed_at": _format_datetime_iso(inspection.completed_at),
        "scan_started_at": _format_datetime_iso(inspection.scan_started_at),
        "scan_completed_at": _format_datetime_iso(inspection.scan_completed_at),
    }

    # 2. Inspector
    inspector_data = {
        "inspector_id": inspection.inspector.id if inspection.inspector else inspection.inspector_id,
        "full_name": inspection.inspector.full_name if inspection.inspector else "Unknown",
        "email": inspection.inspector.email if inspection.inspector else "Unknown",
        "role": (
            inspection.inspector.role.name
            if inspection.inspector and inspection.inspector.role
            else "inspector"
        ),
    }

    # 3. Product
    product_data: dict[str, Any] | None = None
    if inspection.product is not None:
        p = inspection.product
        product_data = {
            "product_id": p.id,
            "product_name": p.product_name,
            "brand_name": p.brand_name,
            "category": p.category,
            "package_type": p.package_type,
            "manufacturer_name": p.manufacturer_name,
            "manufacturer_address": p.manufacturer_address,
            "created_at": _format_datetime_iso(p.created_at),
            "updated_at": _format_datetime_iso(p.updated_at),
        }

    # 4. Location evidence
    has_gps = inspection.latitude is not None and inspection.longitude is not None
    location_data = {
        "latitude": inspection.latitude,
        "longitude": inspection.longitude,
        "location_accuracy_m": inspection.location_accuracy_m,
        "location_captured_at": _format_datetime_iso(inspection.location_captured_at),
        "location_source": inspection.location_source,
        "is_available": has_gps,
        "formatted_location": (
            f"{inspection.latitude:.6f}, {inspection.longitude:.6f}"
            if has_gps
            else "Not available"
        ),
    }

    # 5. Images
    images_data: list[dict[str, Any]] = []
    for img in sorted(inspection.images, key=lambda x: x.id):
        images_data.append(
            {
                "id": img.id,
                "file_name": img.file_name,
                "file_path": img.file_path,
                "image_type": img.image_type,
                "file_size": img.file_size,
                "mime_type": img.mime_type,
                "content_hash": img.content_hash,
                "created_at": _format_datetime_iso(img.created_at),
                "absolute_path": _resolve_filesystem_path(img.file_path),
            }
        )

    # 6. Declarations
    declarations = get_declarations_for_inspection(db, inspection.id)
    declarations_data: list[dict[str, Any]] = []
    for d in declarations:
        display_val = d.normalized_value if d.normalized_value is not None else d.extracted_value
        declarations_data.append(
            {
                "id": d.id,
                "field_name": d.field_name,
                "extracted_value": d.extracted_value,
                "normalized_value": d.normalized_value,
                "display_value": display_val,
                "is_present": d.is_present,
                "confidence": d.confidence,
                "created_at": _format_datetime_iso(d.created_at),
            }
        )

    # 7. Compliance Evaluation & Rule Results (Dynamic)
    compliance_evaluation = evaluate_inspection(db, inspection.id)
    eval_status = compliance_evaluation.get("status", compliance_status_str)
    eval_results = compliance_evaluation.get("results", [])
    eval_map = {r["rule_code"]: r for r in eval_results}

    # Fetch active rule versions and regulation
    inspection_date = inspection.created_at.date() if inspection.created_at else date.today()
    reg_statement = (
        select(RuleVersion.regulation_id)
        .where(
            RuleVersion.status == "active",
            RuleVersion.approval_status == "approved",
        )
        .order_by(RuleVersion.regulation_id.asc())
        .limit(1)
    )
    reg_id = db.scalar(reg_statement)

    rules_data: list[dict[str, Any]] = []
    regulation_data: dict[str, Any] | None = None

    if reg_id is not None:
        reg_obj = db.get(Regulation, reg_id)
        if reg_obj is not None:
            regulation_data = {
                "regulation_id": reg_obj.id,
                "code": reg_obj.code,
                "name": reg_obj.name,
                "jurisdiction": reg_obj.jurisdiction,
                "authority": reg_obj.authority,
                "description": reg_obj.description,
            }

        active_rules = get_active_rule_versions(db, reg_id, inspection_date)
        for rule in active_rules:
            eval_entry = eval_map.get(rule.rule_code, {})
            rule_result_status = eval_entry.get("status", "not_evaluated")
            eval_checks = {c["field_name"]: c["status"] for c in eval_entry.get("checks", [])}

            checks_data: list[dict[str, Any]] = []
            for check in rule.checks:
                check_status = eval_checks.get(
                    check.field_name,
                    "not_applicable" if rule_result_status == "not_applicable" else "not_evaluated"
                )
                checks_data.append(
                    {
                        "field_name": check.field_name,
                        "operator": check.operator,
                        "expected_value": check.expected_value,
                        "expected_unit": check.expected_unit,
                        "severity": check.severity,
                        "failure_message": check.failure_message,
                        "status": check_status,
                    }
                )

            sources_data: list[dict[str, Any]] = []
            for src in rule.sources:
                sources_data.append(
                    {
                        "source_type": src.source_type,
                        "source_reference": src.source_reference,
                        "source_title": src.source_title,
                        "source_url": src.source_url,
                        "document_hash": src.document_hash,
                        "published_at": _format_datetime_iso(src.published_at),
                        "effective_from": _format_datetime_iso(src.effective_from),
                    }
                )

            rules_data.append(
                {
                    "rule_code": rule.rule_code,
                    "rule_number": rule.rule_number,
                    "version": rule.version,
                    "title": rule.title,
                    "requirement": rule.requirement,
                    "effective_from": _format_datetime_iso(rule.effective_from),
                    "effective_to": _format_datetime_iso(rule.effective_to),
                    "status": rule.status,
                    "approval_status": rule.approval_status,
                    "result_status": rule_result_status,
                    "checks": checks_data,
                    "sources": sources_data,
                }
            )

    # 8. Violations
    violations = get_violations_for_inspection(db, inspection.id)
    violations_data: list[dict[str, Any]] = []
    for v in violations:
        violations_data.append(
            {
                "id": v.id,
                "rule_version_id": v.rule_version_id,
                "field_name": v.field_name,
                "severity": v.severity,
                "status": v.status,
                "message": v.message,
                "detected_value": v.detected_value,
                "expected_value": v.expected_value,
                "confidence": v.confidence,
                "evidence": _parse_evidence_json(v.evidence),
                "created_at": _format_datetime_iso(v.created_at),
                "updated_at": _format_datetime_iso(v.updated_at),
            }
        )

    # 9. Evidence Summary
    passed_rules_count = sum(1 for r in rules_data if r["result_status"] == "pass")
    failed_rules_count = sum(1 for r in rules_data if r["result_status"] == "fail")
    reviewed_rules_count = sum(1 for r in rules_data if r["result_status"] == "review")
    not_applicable_rules_count = sum(1 for r in rules_data if r["result_status"] == "not_applicable")
    open_violations_count = sum(1 for v in violations_data if v["status"] == "open")
    review_violations_count = sum(1 for v in violations_data if v["status"] == "review")

    evidence_summary = {
        "total_images": len(images_data),
        "declarations_count": len(declarations_data),
        "violations_count": len(violations_data),
        "open_violations_count": open_violations_count,
        "review_items_count": review_violations_count,
        "total_rules": len(rules_data),
        "passed_rules": passed_rules_count,
        "failed_rules": failed_rules_count,
        "reviewed_rules": reviewed_rules_count,
        "not_applicable_rules": not_applicable_rules_count,
        "overall_compliance_status": eval_status,
    }

    # 10. Report metadata
    report_metadata = {
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "report_format": report_format or "canonical-dict",
        "generator_version": GENERATOR_VERSION,
    }

    # Assembled Canonical Payload
    return {
        "metadata": report_metadata,
        "inspection": inspection_identity,
        "inspector": inspector_data,
        "product": product_data,
        "location": location_data,
        "evidence_summary": evidence_summary,
        "regulation": regulation_data,
        "images": images_data,
        "declarations": declarations_data,
        "rules": rules_data,
        "violations": violations_data,
    }
