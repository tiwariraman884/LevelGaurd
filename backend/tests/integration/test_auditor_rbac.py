"""
backend/tests/integration/test_auditor_rbac.py

Comprehensive tests for Auditor Read-Only Role & RBAC (Scenarios A through T).
"""

from datetime import datetime, timezone
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.security import hash_password
from app.main import app
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.escalation_service import evaluate_product_escalation
from app.services.inspection_service import create_inspection


@pytest.fixture(scope="module")
def seeded_roles(db_session: Session) -> dict[str, Role]:
    roles = {}
    for name, desc in [
        ("admin", "System administrator"),
        ("inspector", "Legal Metrology inspection officer"),
        ("auditor", "Read-only inspection auditor"),
    ]:
        role = db_session.query(Role).filter_by(name=name).first()
        if not role:
            role = Role(name=name, description=desc)
            db_session.add(role)
            db_session.commit()
            db_session.refresh(role)
        roles[name] = role
    return roles


@pytest.fixture(scope="module")
def auditor_user(db_session: Session, seeded_roles: dict[str, Role]) -> User:
    auditor_role = seeded_roles["auditor"]
    user = db_session.query(User).filter_by(email="auditor_test@labelguard.local").first()
    if not user:
        user = User(
            email="auditor_test@labelguard.local",
            password_hash=hash_password("Auditor@Test2026"),
            full_name="Audit Officer",
            role_id=auditor_role.id,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def inspector_user(db_session: Session, seeded_roles: dict[str, Role]) -> User:
    inspector_role = seeded_roles["inspector"]
    user = db_session.query(User).filter_by(email="inspector_test@labelguard.local").first()
    if not user:
        user = User(
            email="inspector_test@labelguard.local",
            password_hash=hash_password("Inspector@Test2026"),
            full_name="Inspection Officer",
            role_id=inspector_role.id,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def auditor_client(auditor_user: User, db_session: Session):
    def override_get_current_user():
        return auditor_user

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def inspector_client(inspector_user: User, db_session: Session):
    def override_get_current_user():
        return inspector_user

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestAuditorRBAC:
    def test_A_seeded_auditor_role_exists(self, db_session: Session):
        role = db_session.query(Role).filter_by(name="auditor").first()
        assert role is not None
        assert role.name == "auditor"
        assert "auditor" in role.description.lower()

    def test_B_auditor_can_authenticate(
        self,
        db_session: Session,
        auditor_user: User,
    ):
        with TestClient(app) as raw_client:
            login_res = raw_client.post(
                "/api/v1/auth/login",
                json={"email": auditor_user.email, "password": "Auditor@Test2026"},
            )
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            assert token is not None

            me_res = raw_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert me_res.status_code == 200
            data = me_res.json()
            assert data["role"] == "auditor"
            assert data["email"] == auditor_user.email

    def test_C_auditor_can_list_inspections(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        # Create an inspection by inspector
        insp = create_inspection(db=db_session, inspector=inspector_user)

        res = auditor_client.get("/api/v1/inspections")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        inspection_ids = [item["id"] for item in data]
        assert insp.id in inspection_ids

    def test_D_auditor_can_get_single_inspection(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)

        res = auditor_client.get(f"/api/v1/inspections/{insp.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == insp.id
        assert data["reference_number"] == insp.reference_number

    def test_E_auditor_can_get_inspection_images(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)

        res = auditor_client.get(f"/api/v1/inspections/{insp.id}/images")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_F_auditor_can_list_and_get_products(
        self,
        db_session: Session,
        auditor_client: TestClient,
    ):
        product = Product(
            product_name="Auditor Test Product",
            brand_name="AuditBrand",
            category="Beverages",
            package_type="Bottle",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        # List products
        res_list = auditor_client.get("/api/v1/products")
        assert res_list.status_code == 200
        assert any(p["id"] == product.id for p in res_list.json())

        # Single product
        res_single = auditor_client.get(f"/api/v1/products/{product.id}")
        assert res_single.status_code == 200
        assert res_single.json()["id"] == product.id

    def test_G_auditor_can_get_mrp_references(
        self,
        db_session: Session,
        auditor_client: TestClient,
    ):
        product = Product(
            product_name="Auditor MRP Product",
            brand_name="AuditBrand",
            category="Snacks",
            package_type="Pouch",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        res = auditor_client.get(f"/api/v1/products/{product.id}/mrp-references")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_H_auditor_can_download_pdf(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)
        insp.compliance_status = ComplianceStatus.COMPLIANT
        insp.status = InspectionStatus.COMPLETED
        insp.completed_at = datetime.now(timezone.utc)
        db_session.commit()

        res = auditor_client.get(f"/api/v1/reports/{insp.id}/pdf")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF-")

    def test_I_auditor_can_download_docx(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)
        insp.compliance_status = ComplianceStatus.COMPLIANT
        insp.status = InspectionStatus.COMPLETED
        insp.completed_at = datetime.now(timezone.utc)
        db_session.commit()

        res = auditor_client.get(f"/api/v1/reports/{insp.id}/docx")
        assert res.status_code == 200
        assert "wordprocessingml.document" in res.headers["content-type"]

    def test_J_auditor_can_get_escalation(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        product = Product(
            product_name="Auditor Escalation Product",
            brand_name="AuditBrand",
            category="Food",
            package_type="Box",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        for _ in range(4):
            insp = create_inspection(db=db_session, inspector=inspector_user)
            insp.product_id = product.id
            insp.compliance_status = ComplianceStatus.NON_COMPLIANT
            insp.status = InspectionStatus.COMPLETED
            insp.completed_at = datetime.now(timezone.utc)
            db_session.commit()
            esc = evaluate_product_escalation(db_session, insp.id)

        assert esc is not None

        # Auditor can view escalation by ID
        res_esc = auditor_client.get(f"/api/v1/escalations/{esc.id}")
        assert res_esc.status_code == 200
        assert res_esc.json()["id"] == esc.id

        # Auditor can view escalations by product ID
        res_prod_esc = auditor_client.get(f"/api/v1/products/{product.id}/escalations")
        assert res_prod_esc.status_code == 200
        assert len(res_prod_esc.json()) >= 1

    def test_K_auditor_cannot_create_inspection_forbidden(
        self,
        auditor_client: TestClient,
    ):
        res = auditor_client.post("/api/v1/inspections", json={})
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_L_auditor_cannot_bulk_scan_forbidden(
        self,
        auditor_client: TestClient,
    ):
        file_data = io.BytesIO(b"fake image data")
        res = auditor_client.post(
            "/api/v1/inspections/bulk-scan",
            files=[("files", ("test.png", file_data, "image/png"))],
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_M_auditor_cannot_analyze_inspection_forbidden(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)
        res = auditor_client.post(f"/api/v1/inspections/{insp.id}/analyze")
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_N_auditor_cannot_upload_image_forbidden(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)
        file_data = io.BytesIO(b"fake image data")
        res = auditor_client.post(
            f"/api/v1/inspections/{insp.id}/images",
            data={"image_type": "front"},
            files={"file": ("front.png", file_data, "image/png")},
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_O_auditor_cannot_mutate_product_forbidden(
        self,
        auditor_client: TestClient,
    ):
        res = auditor_client.post(
            "/api/v1/products",
            json={
                "product_name": "Forbidden Product",
                "brand_name": "Brand",
                "category": "Food",
                "package_type": "Box",
            },
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_P_auditor_cannot_create_mrp_reference_forbidden(
        self,
        db_session: Session,
        auditor_client: TestClient,
    ):
        product = Product(
            product_name="Product MRP 403",
            brand_name="Brand",
            category="Food",
            package_type="Box",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        res = auditor_client.post(
            f"/api/v1/products/{product.id}/mrp-references",
            json={"mrp_declared": 99.0, "source": "catalog"},
        )
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_Q_auditor_cannot_process_mrp_or_mutate_inspection(
        self,
        db_session: Session,
        inspector_user: User,
        auditor_client: TestClient,
    ):
        insp = create_inspection(db=db_session, inspector=inspector_user)
        res = auditor_client.post(f"/api/v1/inspections/{insp.id}/process-mrp")
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_R_auditor_cannot_access_admin_test_endpoint(
        self,
        auditor_client: TestClient,
    ):
        res = auditor_client.get("/api/v1/auth/admin-test")
        assert res.status_code == 403
        assert res.json()["detail"] == "Insufficient permissions"

    def test_S_existing_admin_behavior_unchanged(
        self,
        client: TestClient,
    ):
        res = client.get("/api/v1/auth/admin-test")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_T_existing_inspector_behavior_unchanged(
        self,
        inspector_client: TestClient,
    ):
        # Inspector can create inspection
        res_create = inspector_client.post("/api/v1/inspections", json={})
        assert res_create.status_code == 201

        # Inspector cannot access admin-only endpoint
        res_admin = inspector_client.get("/api/v1/auth/admin-test")
        assert res_admin.status_code == 403
