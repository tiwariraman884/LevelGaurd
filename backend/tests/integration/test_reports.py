"""
Integration and unit tests for the Centralized Report Data Builder (report_data.py).

Covers all required scenarios:
- valid inspection
- missing inspection
- inspection without product
- inspection without GPS
- inspection with GPS
- multiple images
- declarations and normalized display values
- violations handling
- compliant inspection with zero violations
- review / non-compliant inspection
- regulatory traceability & rule structure
- serialization contains only plain serializable data
"""

from datetime import datetime, timezone
import json
import pytest
from sqlalchemy.orm import Session

from app.models.declaration import Declaration
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.inspection_image import InspectionImage
from app.models.product import Product
from app.models.user import User
from app.reports.report_data import build_inspection_report_data
from app.services.inspection_service import create_inspection


def _create_test_declaration(
    db: Session,
    inspection_id: int,
    field_name: str,
    extracted_value: str | None,
    normalized_value: str | None = None,
    is_present: bool = True,
    confidence: float = 90.0,
) -> Declaration:
    decl = Declaration(
        inspection_id=inspection_id,
        field_name=field_name,
        extracted_value=extracted_value,
        normalized_value=normalized_value or extracted_value,
        is_present=is_present,
        confidence=confidence,
    )
    db.add(decl)
    db.commit()
    db.refresh(decl)
    return decl


class TestReportDataBuilder:
    def test_missing_inspection_raises_value_error(self, db_session: Session):
        with pytest.raises(ValueError, match="does not exist"):
            build_inspection_report_data(db_session, 9999999)

    def test_valid_inspection_without_product_and_without_gps(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)
        report = build_inspection_report_data(db_session, insp.id)

        # Inspection identity
        assert report["inspection"]["inspection_id"] == insp.id
        assert report["inspection"]["reference_number"] == insp.reference_number
        assert report["inspection"]["status"] == insp.status.value
        assert report["inspection"]["scan_started_at"] is not None

        # Inspector
        assert report["inspector"]["inspector_id"] == admin_user.id
        assert report["inspector"]["full_name"] == admin_user.full_name
        assert report["inspector"]["email"] == admin_user.email
        assert report["inspector"]["role"] == "admin"

        # Product is None
        assert report["product"] is None

        # Location is unavailable cleanly
        assert report["location"]["is_available"] is False
        assert report["location"]["latitude"] is None
        assert report["location"]["longitude"] is None
        assert report["location"]["formatted_location"] == "Not available"

        # Metadata
        assert report["metadata"]["generator_version"] == "labelguard-report-v1"
        assert report["metadata"]["report_format"] == "canonical-dict"
        assert report["metadata"]["report_generated_at"] is not None

    def test_inspection_with_product_and_gps(
        self,
        db_session: Session,
        admin_user: User,
    ):
        product = db_session.get(Product, 1)
        assert product is not None

        cap_time = datetime(2026, 9, 11, 10, 30, 0, tzinfo=timezone.utc)
        insp = create_inspection(
            db=db_session,
            inspector=admin_user,
            product_id=product.id,
            latitude=28.6139,
            longitude=77.2090,
            location_accuracy_m=3.5,
            location_captured_at=cap_time,
            location_source="device_gps",
        )

        report = build_inspection_report_data(db_session, insp.id)

        # Product details populated
        assert report["product"] is not None
        assert report["product"]["product_id"] == product.id
        assert report["product"]["brand_name"] == product.brand_name
        assert report["product"]["product_name"] == product.product_name
        assert report["product"]["category"] == product.category
        assert report["product"]["package_type"] == product.package_type
        assert report["product"]["manufacturer_name"] == product.manufacturer_name

        # Location details populated
        assert report["location"]["is_available"] is True
        assert report["location"]["latitude"] == 28.6139
        assert report["location"]["longitude"] == 77.2090
        assert report["location"]["location_accuracy_m"] == 3.5
        assert report["location"]["location_source"] == "device_gps"
        assert "28.613900, 77.209000" in report["location"]["formatted_location"]

    def test_multiple_images(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)

        img1 = InspectionImage(
            inspection_id=insp.id,
            file_name="front_panel.png",
            file_path="uploads/front_panel.png",
            image_type="front",
            file_size=102400,
            mime_type="image/png",
            content_hash="hash_front_12345",
        )
        img2 = InspectionImage(
            inspection_id=insp.id,
            file_name="back_panel.png",
            file_path="uploads/back_panel.png",
            image_type="back",
            file_size=204800,
            mime_type="image/png",
            content_hash="hash_back_67890",
        )
        db_session.add_all([img1, img2])
        db_session.commit()

        report = build_inspection_report_data(db_session, insp.id)

        assert len(report["images"]) == 2
        assert report["evidence_summary"]["total_images"] == 2
        file_names = [img["file_name"] for img in report["images"]]
        assert "front_panel.png" in file_names
        assert "back_panel.png" in file_names
        for img in report["images"]:
            assert "absolute_path" in img
            assert "content_hash" in img
            assert "created_at" in img

    def test_declarations_and_display_values(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)

        # Normalized value present
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="net_quantity",
            extracted_value="Net Wt: 200 gms",
            normalized_value="200 g",
            confidence=88.5,
        )
        # Normalized value is None -> display_value falls back to extracted_value
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="batch_number",
            extracted_value="B12345",
            normalized_value=None,
            confidence=92.0,
        )

        report = build_inspection_report_data(db_session, insp.id)

        assert len(report["declarations"]) == 2
        decl_map = {d["field_name"]: d for d in report["declarations"]}
        assert decl_map["net_quantity"]["display_value"] == "200 g"
        assert decl_map["batch_number"]["display_value"] == "B12345"

    def test_compliant_inspection_zero_violations(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)

        # Supply fully compliant declarations for all active Legal Metrology rules
        declarations_to_add = [
            ("mrp", "Rs. 50.00 (incl. of all taxes)", "50.00"),
            ("manufacturer", "Haldiram Snacks Pvt Ltd, Noida, UP", "Haldiram Snacks Pvt Ltd, Noida, UP"),
            ("product_name", "Namkeen / Snack Food", "Namkeen / Snack Food"),
            ("net_quantity", "200 g", "200 g"),
            ("unit_symbol", "g", "g"),
            ("unit_sale_price", "Rs. 0.25 / g", "0.25 / g"),
            ("manufacturing_date", "08/2026", "2026-08"),
            ("best_before", "08/2027", "2027-08"),
            ("date_sensitive_commodity", "true", "true"),
            ("batch_number", "B63240194", "B63240194"),
            ("country_of_origin", "India", "India"),
            ("consumer_care", "customercare@haldiram.com, 1800-111-222", "customercare@haldiram.com, 1800-111-222"),
            ("declaration_legibility", "pass", "pass"),
        ]

        for field_name, ext_val, norm_val in declarations_to_add:
            _create_test_declaration(
                db=db_session,
                inspection_id=insp.id,
                field_name=field_name,
                extracted_value=ext_val,
                normalized_value=norm_val,
                confidence=95.0,
            )

        report = build_inspection_report_data(db_session, insp.id)

        assert report["evidence_summary"]["overall_compliance_status"] == "compliant"
        assert report["evidence_summary"]["violations_count"] == 0
        assert report["evidence_summary"]["open_violations_count"] == 0
        assert report["evidence_summary"]["passed_rules"] > 0
        assert report["evidence_summary"]["failed_rules"] == 0
        assert len(report["violations"]) == 0

    def test_non_compliant_inspection_with_violations(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)

        # Inspection with no declarations -> required rules fail
        report = build_inspection_report_data(db_session, insp.id)

        assert report["evidence_summary"]["overall_compliance_status"] in ("non_compliant", "review")
        assert report["evidence_summary"]["violations_count"] > 0
        assert len(report["violations"]) > 0
        v0 = report["violations"][0]
        assert "id" in v0
        assert "field_name" in v0
        assert "severity" in v0
        assert "status" in v0
        assert "message" in v0

    def test_regulatory_traceability_and_rules_structure(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)
        report = build_inspection_report_data(db_session, insp.id)

        # Regulation
        assert report["regulation"] is not None
        assert report["regulation"]["code"] == "LM-PC-2011"
        assert "Legal Metrology" in report["regulation"]["name"]

        # Rules
        assert len(report["rules"]) > 0
        r0 = report["rules"][0]
        assert "rule_code" in r0
        assert "rule_number" in r0
        assert "version" in r0
        assert "title" in r0
        assert "requirement" in r0
        assert "result_status" in r0
        assert isinstance(r0["checks"], list)
        assert isinstance(r0["sources"], list)

    def test_full_payload_is_json_serializable(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(
            db=db_session,
            inspector=admin_user,
            latitude=19.0760,
            longitude=72.8777,
            location_accuracy_m=5.0,
            location_source="gps",
        )
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="mrp",
            extracted_value="Rs. 100",
            normalized_value="100.00",
        )

        report = build_inspection_report_data(db_session, insp.id)

        # Serialization check
        json_str = json.dumps(report)
        deserialized = json.loads(json_str)

        assert deserialized["inspection"]["inspection_id"] == insp.id
        assert deserialized["location"]["latitude"] == 19.0760
        assert deserialized["metadata"]["generator_version"] == "labelguard-report-v1"
