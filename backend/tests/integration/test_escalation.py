"""
backend/tests/integration/test_escalation.py

Comprehensive tests for Product-Level Escalation Workflow (evaluation, persistence, endpoints, RBAC).
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.escalation import Escalation
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.escalation_service import (
    ESCALATION_NON_COMPLIANT_THRESHOLD,
    evaluate_product_escalation,
)
from app.services.inspection_service import create_inspection


def _create_test_product(db: Session, name_suffix: str) -> Product:
    product = Product(
        product_name=f"Test Escalation Product {name_suffix}",
        brand_name="TestBrand",
        category="Food & Beverage",
        package_type="Pouch",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _create_inspection_with_status(
    db: Session,
    inspector: User,
    product: Product | None,
    compliance_status: ComplianceStatus,
    status: InspectionStatus = InspectionStatus.COMPLETED,
) -> Inspection:
    insp = create_inspection(db=db, inspector=inspector)
    insp.product_id = product.id if product else None
    insp.compliance_status = compliance_status
    insp.status = status
    insp.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(insp)
    return insp


class TestEscalationWorkflow:
    def test_first_three_non_compliant_do_not_escalate(
        self,
        db_session: Session,
        admin_user: User,
    ):
        product = _create_test_product(db_session, "under_threshold")

        # 1st non-compliant
        insp1 = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
        )
        esc1 = evaluate_product_escalation(db_session, insp1.id)
        assert esc1 is None

        # 2nd non-compliant
        insp2 = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
        )
        esc2 = evaluate_product_escalation(db_session, insp2.id)
        assert esc2 is None

        # 3rd non-compliant
        insp3 = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
        )
        esc3 = evaluate_product_escalation(db_session, insp3.id)
        assert esc3 is None

        # Ensure no escalation records exist in DB for this product
        escalations = db_session.query(Escalation).filter_by(product_id=product.id).all()
        assert len(escalations) == 0

    def test_fourth_non_compliant_triggers_state_escalation(
        self,
        db_session: Session,
        admin_user: User,
    ):
        product = _create_test_product(db_session, "triggers_escalation")

        for _ in range(3):
            insp = _create_inspection_with_status(
                db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
            )
            evaluate_product_escalation(db_session, insp.id)

        # 4th non-compliant inspection
        insp4 = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
        )
        esc = evaluate_product_escalation(db_session, insp4.id)

        assert esc is not None
        assert esc.product_id == product.id
        assert esc.trigger_inspection_id == insp4.id
        assert esc.failed_inspection_count == 4
        assert esc.level == "district"
        assert esc.status == "open"
        assert f"exceeding the threshold of {ESCALATION_NON_COMPLIANT_THRESHOLD}" in esc.reason
        assert esc.created_at is not None
        assert esc.resolved_at is None

    def test_fifth_non_compliant_does_not_create_duplicate_open_escalation(
        self,
        db_session: Session,
        admin_user: User,
    ):
        product = _create_test_product(db_session, "no_duplicate_open")

        for _ in range(4):
            insp = _create_inspection_with_status(
                db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
            )
            evaluate_product_escalation(db_session, insp.id)

        escalations_before = db_session.query(Escalation).filter_by(product_id=product.id).all()
        assert len(escalations_before) == 1
        first_esc_id = escalations_before[0].id

        # 5th non-compliant inspection
        insp5 = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
        )
        esc5 = evaluate_product_escalation(db_session, insp5.id)

        assert esc5 is not None
        assert esc5.id == first_esc_id

        # Still only 1 escalation in DB
        escalations_after = db_session.query(Escalation).filter_by(product_id=product.id).all()
        assert len(escalations_after) == 1

    def test_compliant_review_and_failed_inspections_do_not_count(
        self,
        db_session: Session,
        admin_user: User,
    ):
        product = _create_test_product(db_session, "only_non_compliant_counts")

        # 3 non-compliant
        for _ in range(3):
            insp = _create_inspection_with_status(
                db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
            )
            evaluate_product_escalation(db_session, insp.id)

        # Compliant
        insp_comp = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.COMPLIANT
        )
        assert evaluate_product_escalation(db_session, insp_comp.id) is None

        # Review
        insp_rev = _create_inspection_with_status(
            db_session, admin_user, product, ComplianceStatus.REVIEW
        )
        assert evaluate_product_escalation(db_session, insp_rev.id) is None

        # Failed inspection status
        insp_failed = _create_inspection_with_status(
            db_session,
            admin_user,
            product,
            ComplianceStatus.NON_COMPLIANT,
            status=InspectionStatus.FAILED,
        )
        assert evaluate_product_escalation(db_session, insp_failed.id) is None

        # Still 0 escalations
        assert db_session.query(Escalation).filter_by(product_id=product.id).count() == 0

    def test_products_tracked_independently(
        self,
        db_session: Session,
        admin_user: User,
    ):
        product_a = _create_test_product(db_session, "prod_a")
        product_b = _create_test_product(db_session, "prod_b")

        # Product A gets 3 non-compliant
        for _ in range(3):
            insp = _create_inspection_with_status(
                db_session, admin_user, product_a, ComplianceStatus.NON_COMPLIANT
            )
            evaluate_product_escalation(db_session, insp.id)

        # Product B gets 4 non-compliant
        for _ in range(4):
            insp = _create_inspection_with_status(
                db_session, admin_user, product_b, ComplianceStatus.NON_COMPLIANT
            )
            evaluate_product_escalation(db_session, insp.id)

        assert db_session.query(Escalation).filter_by(product_id=product_a.id).count() == 0
        assert db_session.query(Escalation).filter_by(product_id=product_b.id).count() == 1

    def test_inspection_without_product_does_not_escalate(
        self,
        db_session: Session,
        admin_user: User,
    ):
        insp = _create_inspection_with_status(
            db_session, admin_user, None, ComplianceStatus.NON_COMPLIANT
        )
        assert evaluate_product_escalation(db_session, insp.id) is None


class TestEscalationEndpoints:
    def test_get_escalation_by_id_and_by_product_api(
        self,
        db_session: Session,
        admin_user: User,
        client: TestClient,
    ):
        product = _create_test_product(db_session, "api_test")

        for _ in range(4):
            insp = _create_inspection_with_status(
                db_session, admin_user, product, ComplianceStatus.NON_COMPLIANT
            )
            esc = evaluate_product_escalation(db_session, insp.id)

        assert esc is not None

        # Test GET /api/v1/escalations/{escalation_id}
        res = client.get(f"/api/v1/escalations/{esc.id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == esc.id
        assert data["product_id"] == product.id
        assert data["failed_inspection_count"] == 4
        assert data["level"] == "district"
        assert data["status"] == "open"

        # Test GET /api/v1/products/{product_id}/escalations
        res_prod = client.get(f"/api/v1/products/{product.id}/escalations")
        assert res_prod.status_code == 200
        prod_data = res_prod.json()
        assert len(prod_data) >= 1
        assert prod_data[0]["id"] == esc.id

        # Test GET non-existent escalation -> 404
        res_404 = client.get("/api/v1/escalations/99999999")
        assert res_404.status_code == 404

        # Test GET non-existent product escalations -> 404
        res_prod_404 = client.get("/api/v1/products/99999999/escalations")
        assert res_prod_404.status_code == 404

    def test_escalation_rbac_forbidden_for_unauthorized_inspector(
        self,
        db_session: Session,
        admin_user: User,
    ):
        # Create inspector 1 and inspector 2
        inspector_role = db_session.query(Role).filter_by(name="inspector").first()
        if not inspector_role:
            inspector_role = Role(name="inspector", description="Inspector")
            db_session.add(inspector_role)
            db_session.commit()

        user1 = User(
            email=f"inspector1_{datetime.now().timestamp()}@labelguard.test",
            password_hash="hashed_password",
            full_name="Inspector One",
            role_id=inspector_role.id,
            is_active=True,
        )
        user2 = User(
            email=f"inspector2_{datetime.now().timestamp()}@labelguard.test",
            password_hash="hashed_password",
            full_name="Inspector Two",
            role_id=inspector_role.id,
            is_active=True,
        )
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        product = _create_test_product(db_session, "rbac_test")

        # user1 creates inspections and triggers escalation
        for _ in range(4):
            insp = _create_inspection_with_status(
                db_session, user1, product, ComplianceStatus.NON_COMPLIANT
            )
            esc = evaluate_product_escalation(db_session, insp.id)

        assert esc is not None

        # user1 (the trigger inspector) can access
        def override_user1():
            return user1

        def override_db():
            yield db_session

        app.dependency_overrides[get_current_user] = override_user1
        app.dependency_overrides[get_db] = override_db

        with TestClient(app) as test_client:
            res_user1 = test_client.get(f"/api/v1/escalations/{esc.id}")
            assert res_user1.status_code == 200

        # user2 (different inspector) should be forbidden
        def override_user2():
            return user2

        app.dependency_overrides[get_current_user] = override_user2
        with TestClient(app) as test_client:
            res_user2 = test_client.get(f"/api/v1/escalations/{esc.id}")
            assert res_user2.status_code == 403

        app.dependency_overrides.clear()
