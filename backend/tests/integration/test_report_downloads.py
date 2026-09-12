"""
backend/tests/integration/test_report_downloads.py

Integration tests for the Report Download API endpoints:
- GET /api/v1/reports/{inspection_id}/pdf
- GET /api/v1/reports/{inspection_id}/docx

Covers requirements A through K:
A. PDF download authenticated admin
B. DOCX download authenticated admin
C. PDF Content-Type (application/pdf)
D. DOCX Content-Type (application/vnd.openxmlformats-officedocument.wordprocessingml.document)
E. Attachment filename formatting (<reference_number>_inspection_report.pdf / .docx)
F. Nonexistent inspection -> 404
G. Unauthorized inspector -> 403
H. Generated PDF file exists on disk
I. Generated DOCX file exists on disk
J. Router endpoints registered in FastAPI application
K. Existing tests remain passing
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.reports.docx_generator import REPORTS_DIR
from app.services.inspection_service import create_inspection
from tests.integration.test_reports import _create_test_declaration


@pytest.fixture
def other_inspector(db_session: Session) -> User:
    """Fixture providing a second inspector user for authorization testing."""
    user = db_session.query(User).filter(User.email == "other_inspector@labelguard.local").first()
    if not user:
        inspector_role = db_session.query(Role).filter(Role.name == "inspector").first()
        user = User(
            id=999,
            role_id=inspector_role.id,
            full_name="Other Inspector",
            email="other_inspector@labelguard.local",
            password_hash="hashed_pw_placeholder",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


class TestReportDownloadsAPI:
    # J. Router endpoints registered
    def test_J_router_endpoints_registered(self):
        openapi_paths = app.openapi()["paths"]
        assert "/api/v1/reports/{inspection_id}/pdf" in openapi_paths
        assert "/api/v1/reports/{inspection_id}/docx" in openapi_paths

    # A, C, E, H. PDF download authenticated admin, content-type, filename, file exists
    def test_A_C_E_H_download_pdf_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(
            db=db_session,
            inspector=admin_user,
            latitude=28.6139,
            longitude=77.2090,
            location_accuracy_m=5.0,
            location_source="gps",
        )
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="mrp",
            extracted_value="Rs. 50.00",
            normalized_value="50.00",
        )

        response = client.get(f"/api/v1/reports/{insp.id}/pdf")

        assert response.status_code == 200
        # C. Content-Type
        assert response.headers["content-type"] == "application/pdf"
        # E. Attachment filename
        expected_filename = f"{insp.reference_number}_inspection_report.pdf"
        assert expected_filename in response.headers.get("content-disposition", "")
        # Content validation
        assert response.content.startswith(b"%PDF-")
        assert len(response.content) > 2000

        # H. Generated PDF file exists on disk
        pdf_path = REPORTS_DIR / expected_filename
        assert pdf_path.exists()

    # B, D, E, I. DOCX download authenticated admin, content-type, filename, file exists
    def test_B_D_E_I_download_docx_success(
        self,
        client: TestClient,
        db_session: Session,
        admin_user: User,
    ):
        insp = create_inspection(
            db=db_session,
            inspector=admin_user,
            latitude=28.6139,
            longitude=77.2090,
            location_accuracy_m=5.0,
            location_source="gps",
        )
        _create_test_declaration(
            db=db_session,
            inspection_id=insp.id,
            field_name="net_quantity",
            extracted_value="200 g",
            normalized_value="200 g",
        )

        response = client.get(f"/api/v1/reports/{insp.id}/docx")

        assert response.status_code == 200
        # D. Content-Type
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        # E. Attachment filename
        expected_filename = f"{insp.reference_number}_inspection_report.docx"
        assert expected_filename in response.headers.get("content-disposition", "")
        # Content validation
        assert len(response.content) > 2000

        # I. Generated DOCX file exists on disk
        docx_path = REPORTS_DIR / expected_filename
        assert docx_path.exists()

    # F. Nonexistent inspection -> 404
    def test_F_nonexistent_inspection_returns_404(self, client: TestClient):
        response_pdf = client.get("/api/v1/reports/99999999/pdf")
        assert response_pdf.status_code == 404
        assert "not found" in response_pdf.json()["detail"].lower()

        response_docx = client.get("/api/v1/reports/99999999/docx")
        assert response_docx.status_code == 404
        assert "not found" in response_docx.json()["detail"].lower()

    # G. Unauthorized inspector -> 403
    def test_G_unauthorized_inspector_returns_403(
        self,
        db_session: Session,
        admin_user: User,
        other_inspector: User,
    ):
        # Create inspection owned by admin_user (id=1)
        insp = create_inspection(db=db_session, inspector=admin_user)

        # Create client acting as other_inspector (role='inspector', id=999)
        def override_other_user():
            return other_inspector

        app.dependency_overrides[get_current_user] = override_other_user

        with TestClient(app) as test_client:
            resp_pdf = test_client.get(f"/api/v1/reports/{insp.id}/pdf")
            assert resp_pdf.status_code == 403
            assert "access" in resp_pdf.json()["detail"].lower()

            resp_docx = test_client.get(f"/api/v1/reports/{insp.id}/docx")
            assert resp_docx.status_code == 403
            assert "access" in resp_docx.json()["detail"].lower()

        app.dependency_overrides.clear()
