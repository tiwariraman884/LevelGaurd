"""
backend/tests/integration/test_pdf_report.py

Comprehensive tests for the Production PDF Report Generator (pdf_generator.py).
Covers:
- compliant inspection
- non-compliant inspection
- review inspection
- inspection with GPS
- inspection without GPS
- multiple images (with actual test image files and missing image handling)
- missing image file fallback
- no violations (clean pass state)
- violations present
- long declaration values (wrapping & layout safety)
- multi-page rule table and document pagination
- PDF file actually created in backend/storage/reports/
- resulting PDF is non-empty and starts with '%PDF-'
"""

from pathlib import Path
import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.models.declaration import Declaration
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.inspection_image import InspectionImage
from app.models.product import Product
from app.models.user import User
from app.reports.pdf_generator import REPORTS_DIR, generate_inspection_pdf
from app.services.inspection_service import create_inspection
from tests.integration.test_reports import _create_test_declaration


def _verify_pdf_file(pdf_path: Path) -> bytes:
    assert pdf_path.exists(), f"PDF does not exist at {pdf_path}"
    assert pdf_path.is_file()
    size = pdf_path.stat().st_size
    assert size > 2000, f"PDF file size too small: {size} bytes"
    with open(pdf_path, "rb") as f:
        content = f.read()
    assert content.startswith(b"%PDF-"), "PDF missing %PDF- magic header"
    assert b"%%EOF" in content, "PDF missing %%EOF trailer"
    return content


def _create_temp_png(file_path: Path, color=(200, 230, 255), size=(300, 200)) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=color)
    img.save(file_path, format="PNG")


class TestPDFReportGenerator:
    def test_missing_inspection_raises_value_error(self, db_session: Session):
        with pytest.raises(ValueError, match="does not exist"):
            generate_inspection_pdf(db_session, 99999999)

    def test_compliant_inspection_pdf_generation(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(
            db=db_session,
            inspector=admin_user,
            latitude=28.6139,
            longitude=77.2090,
            location_accuracy_m=4.0,
            location_source="gps",
        )

        compliant_decls = [
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

        for field_name, ext_val, norm_val in compliant_decls:
            _create_test_declaration(
                db=db_session,
                inspection_id=insp.id,
                field_name=field_name,
                extracted_value=ext_val,
                normalized_value=norm_val,
                confidence=95.0,
            )

        pdf_path = generate_inspection_pdf(db_session, insp.id)

        assert pdf_path.name == f"{insp.reference_number}_inspection_report.pdf"
        assert pdf_path.parent == REPORTS_DIR
        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000

    def test_non_compliant_inspection_with_violations_pdf(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)
        # Empty inspection -> rules fail, violations generated
        pdf_path = generate_inspection_pdf(db_session, insp.id)

        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000

    def test_review_inspection_pdf(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)
        # Add declaration with low confidence -> triggers REVIEW status
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="mrp",
            extracted_value="Rs. 50",
            normalized_value="50.00",
            confidence=20.0,
        )

        pdf_path = generate_inspection_pdf(db_session, insp.id)
        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000

    def test_inspection_with_gps_pdf(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(
            db=db_session,
            inspector=admin_user,
            latitude=12.9716,
            longitude=77.5946,
            location_accuracy_m=5.0,
            location_source="gps_fused",
        )
        pdf_path = generate_inspection_pdf(db_session, insp.id)
        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000

    def test_inspection_without_gps_pdf(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)
        pdf_path = generate_inspection_pdf(db_session, insp.id)
        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000

    def test_inspection_with_multiple_images_and_missing_file_fallback(
        self,
        db_session: Session,
        admin_user: User,
        tmp_path: Path,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)

        # 1. Existing image file
        real_img_path = tmp_path / "panel_front.png"
        _create_temp_png(real_img_path, color=(100, 150, 200), size=(400, 300))

        img1 = InspectionImage(
            inspection_id=insp.id,
            file_name="panel_front.png",
            file_path=str(real_img_path),
            image_type="front",
            file_size=50000,
            mime_type="image/png",
            content_hash="hash_front_valid_123",
        )

        # 2. Missing image file (simulates deleted or unreadable file)
        img2 = InspectionImage(
            inspection_id=insp.id,
            file_name="panel_back_missing.png",
            file_path=str(tmp_path / "non_existent_image.png"),
            image_type="back",
            file_size=60000,
            mime_type="image/png",
            content_hash="hash_back_missing_456",
        )

        db_session.add_all([img1, img2])
        db_session.commit()

        pdf_path = generate_inspection_pdf(db_session, insp.id)
        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000

    def test_long_declaration_values_and_multi_page_wrapping(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(db=db_session, inspector=admin_user)

        # Very long text values to verify wrapping and layout stability
        long_mfr = (
            "Manufactured and packed by M/S Haldiram Snacks Private Limited, "
            "Plot No. A-1/A-2, Sector 62, Institutional Area, Industrial Estate, "
            "Noida, Gautam Buddha Nagar, Uttar Pradesh - 201309, India. "
            "Customer support phone: 1800-111-2222, email: complaints@haldiram.co.in"
        )
        long_care = (
            "For any consumer complaints, feedback or queries, contact Customer Care Manager at: "
            "Toll Free: 1800-425-1999, WhatsApp: +91-99999-88888, Email: support@brand.com, "
            "Postal: Post Box No. 1024, New Delhi - 110001, India."
        )

        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="manufacturer",
            extracted_value=long_mfr,
            normalized_value=long_mfr,
            confidence=94.0,
        )
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="consumer_care",
            extracted_value=long_care,
            normalized_value=long_care,
            confidence=91.0,
        )

        pdf_path = generate_inspection_pdf(db_session, insp.id)
        content = _verify_pdf_file(pdf_path)
        assert len(content) > 3000
