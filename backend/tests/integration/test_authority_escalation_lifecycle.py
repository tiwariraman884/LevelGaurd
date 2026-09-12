"""
backend/tests/integration/test_authority_escalation_lifecycle.py

Targeted integration tests for Authority Escalation Lifecycle (Checkpoints 1 through 15).
"""

from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.security import hash_password
from app.main import app
from app.models.audit_log import AuditLog
from app.models.escalation import Escalation
from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.notification import Notification, NotificationStatus
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.inspection_service import create_inspection


def _get_or_create_role(db: Session, name: str, description: str) -> Role:
    role = db.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=description)
        db.add(role)
        db.commit()
        db.refresh(role)
    return role


def _get_or_create_user(db: Session, email: str, role_name: str, full_name: str) -> User:
    user = db.query(User).filter_by(email=email).first()
    if not user:
        role = _get_or_create_role(db, role_name, f"{role_name} role")
        user = User(
            email=email,
            password_hash=hash_password("Password@123"),
            full_name=full_name,
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture(scope="module")
def authority_users(db_session: Session) -> dict[str, User]:
    return {
        "admin": _get_or_create_user(db_session, "admin_auth_test@labelguard.local", "admin", "Admin User"),
        "district_collector": _get_or_create_user(db_session, "collector_auth_test@labelguard.local", "district_collector", "District Collector"),
        "state_admin": _get_or_create_user(db_session, "state_admin_auth_test@labelguard.local", "state_admin", "State Admin"),
        "national_admin": _get_or_create_user(db_session, "national_admin_auth_test@labelguard.local", "national_admin", "National Admin"),
        "inspector": _get_or_create_user(db_session, "inspector_auth_test@labelguard.local", "inspector", "Inspector Officer"),
        "auditor": _get_or_create_user(db_session, "auditor_auth_test@labelguard.local", "auditor", "Auditor Officer"),
    }


def _make_client_for_user(user: User, db_session: Session) -> TestClient:
    def override_get_current_user():
        return user

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _create_test_escalation(
    db: Session,
    inspector: User,
    level: str = "district",
    status: str = "open",
    product_suffix: str = "lifecycle",
) -> Escalation:
    product = Product(
        product_name=f"Escalation Test Product {product_suffix}_{datetime.now().timestamp()}",
        brand_name="TestBrand",
        category="Commodity",
        package_type="Pouch",
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    insp = create_inspection(db=db, inspector=inspector)
    insp.product_id = product.id
    insp.compliance_status = ComplianceStatus.NON_COMPLIANT
    insp.status = InspectionStatus.COMPLETED
    insp.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(insp)

    esc = Escalation(
        product_id=product.id,
        trigger_inspection_id=insp.id,
        failed_inspection_count=4,
        level=level,
        status=status,
        reason=f"Product reached 4 distinct non-compliant inspections for {level} escalation.",
    )
    db.add(esc)
    db.commit()
    db.refresh(esc)
    return esc


class TestCheckpoint1StateAdminAcknowledge:
    def test_state_admin_acknowledges_state_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        # Create a state-level open escalation
        esc = _create_test_escalation(db_session, inspector, level="state", status="open", product_suffix="state_ack")

        client = _make_client_for_user(state_admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "State admin acknowledges case."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["escalation_id"] == esc.id
        assert data["level"] == "state"
        assert data["status"] == "acknowledged"
        assert data["actor_id"] == state_admin.id
        assert data["action"] == "acknowledge"

        # Verify in DB
        db_session.refresh(esc)
        assert esc.status == "acknowledged"
        assert esc.acknowledged_by == state_admin.id
        assert esc.acknowledged_at is not None

        # Verify Audit Log
        audit = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id, action="ESCALATION_ACKNOWLEDGE")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_id == state_admin.id
        details = json.loads(audit.details) if audit.details else {}
        assert details.get("level") == "state"
        assert details.get("status") == "acknowledged"

    def test_admin_can_acknowledge_state_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(db_session, inspector, level="state", status="open", product_suffix="admin_state_ack")

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Admin operational acknowledgment."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "acknowledged"
        assert data["actor_id"] == admin.id

        db_session.refresh(esc)
        assert esc.acknowledged_by == admin.id

    def test_unauthorized_roles_cannot_acknowledge_state_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(db_session, inspector, level="state", status="open", product_suffix="unauth_state_ack")

        # District collector on state escalation -> 403
        client_dc = _make_client_for_user(authority_users["district_collector"], db_session)
        res_dc = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "District collector trying to ack state."},
        )
        app.dependency_overrides.clear()
        assert res_dc.status_code == 403

        # National admin on state escalation -> 403
        client_na = _make_client_for_user(authority_users["national_admin"], db_session)
        res_na = client_na.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "National admin trying to ack state."},
        )
        app.dependency_overrides.clear()
        assert res_na.status_code == 403

        # Inspector on state escalation -> 403
        client_insp = _make_client_for_user(authority_users["inspector"], db_session)
        res_insp = client_insp.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge"},
        )
        app.dependency_overrides.clear()
        assert res_insp.status_code == 403

        # Auditor on state escalation -> 403
        client_aud = _make_client_for_user(authority_users["auditor"], db_session)
        res_aud = client_aud.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge"},
        )
        app.dependency_overrides.clear()
        assert res_aud.status_code == 403


class TestCheckpoint2StateAdminResolve:
    """Checkpoint 2 — State Admin resolves a state-level escalation."""

    def test_state_admin_resolves_acknowledged_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        # Create a state-level acknowledged escalation
        esc = _create_test_escalation(
            db_session, inspector, level="state", status="acknowledged",
            product_suffix="state_resolve",
        )
        esc.acknowledged_by = state_admin.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(state_admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Issue resolved after corrective action by manufacturer."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["escalation_id"] == esc.id
        assert data["level"] == "state"
        assert data["status"] == "resolved"
        assert data["actor_id"] == state_admin.id
        assert data["action"] == "resolve"
        assert data["notes"] is not None

        # Verify DB state
        db_session.refresh(esc)
        assert esc.status == "resolved"
        assert esc.resolved_by == state_admin.id
        assert esc.resolved_at is not None
        assert esc.resolution_notes == "Issue resolved after corrective action by manufacturer."

    def test_admin_resolves_state_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="acknowledged",
            product_suffix="admin_state_resolve",
        )
        esc.acknowledged_by = admin.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Admin resolved state-level case."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "resolved"
        assert data["actor_id"] == admin.id

        db_session.refresh(esc)
        assert esc.resolved_by == admin.id
        assert esc.resolution_notes == "Admin resolved state-level case."

    def test_resolve_without_notes_returns_400(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="acknowledged",
            product_suffix="state_resolve_no_notes",
        )

        client = _make_client_for_user(state_admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve"},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "notes" in res.json()["detail"].lower() or "required" in res.json()["detail"].lower()

    def test_resolve_already_resolved_returns_400(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="resolved",
            product_suffix="state_double_resolve",
        )
        esc.resolved_by = state_admin.id
        esc.resolved_at = datetime.now(timezone.utc)
        esc.resolution_notes = "Already resolved."
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(state_admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Trying to re-resolve."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "already resolved" in res.json()["detail"].lower()

    def test_unauthorized_roles_cannot_resolve_state_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(
            db_session, inspector, level="state", status="acknowledged",
            product_suffix="unauth_state_resolve",
        )

        # District collector on state escalation -> 403
        client_dc = _make_client_for_user(authority_users["district_collector"], db_session)
        res_dc = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "DC trying to resolve state."},
        )
        app.dependency_overrides.clear()
        assert res_dc.status_code == 403

        # National admin on state escalation -> 403
        client_na = _make_client_for_user(authority_users["national_admin"], db_session)
        res_na = client_na.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "National admin trying to resolve state."},
        )
        app.dependency_overrides.clear()
        assert res_na.status_code == 403

        # Inspector -> 403
        client_insp = _make_client_for_user(authority_users["inspector"], db_session)
        res_insp = client_insp.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Inspector trying to resolve."},
        )
        app.dependency_overrides.clear()
        assert res_insp.status_code == 403

        # Auditor -> 403
        client_aud = _make_client_for_user(authority_users["auditor"], db_session)
        res_aud = client_aud.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Auditor trying to resolve."},
        )
        app.dependency_overrides.clear()
        assert res_aud.status_code == 403

    def test_resolve_generates_audit_log(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="open",
            product_suffix="state_resolve_audit",
        )

        # First acknowledge
        client = _make_client_for_user(state_admin, db_session)
        res_ack = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Acking for resolve audit test."},
        )
        assert res_ack.status_code == 200

        # Then resolve
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Full resolution with audit verification."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200

        # Verify audit log entry for ESCALATION_RESOLVE
        audit = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id, action="ESCALATION_RESOLVE")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_id == state_admin.id
        details = json.loads(audit.details) if audit.details else {}
        assert details.get("level") == "state"
        assert details.get("status") == "resolved"
        assert details.get("notes") == "Full resolution with audit verification."


class TestCheckpoint3DistrictReferToState:
    """Checkpoint 3 — District Collector refers an escalation from district to state."""

    def test_district_collector_refers_to_state(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="acknowledged",
            product_suffix="dc_refer_state",
        )
        esc.acknowledged_by = dc.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Referred to state authority for further action."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["escalation_id"] == esc.id
        assert data["level"] == "state"
        assert data["status"] == "open"
        assert data["actor_id"] == dc.id
        assert data["action"] == "refer_state"

        # Verify DB
        db_session.refresh(esc)
        assert esc.level == "state"
        assert esc.status == "open"
        # acknowledged_by/at should be reset
        assert esc.acknowledged_by is None
        assert esc.acknowledged_at is None

    def test_admin_can_refer_to_state(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="acknowledged",
            product_suffix="admin_refer_state",
        )

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Admin referring to state."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "state"
        assert data["status"] == "open"

    def test_cannot_refer_state_from_state_level(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        # State-level escalation — refer_state not valid
        esc = _create_test_escalation(
            db_session, inspector, level="state", status="open",
            product_suffix="state_refer_state_invalid",
        )

        # Use admin (who has refer_state permission) to test level guard
        admin = authority_users["admin"]
        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Trying invalid referral."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "district" in res.json()["detail"].lower()

    def test_unauthorized_roles_cannot_refer_state(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="unauth_refer_state",
        )

        # state_admin cannot refer_state (it's not in their permitted actions per level)
        client_sa = _make_client_for_user(authority_users["state_admin"], db_session)
        res_sa = client_sa.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "State admin trying to refer from district."},
        )
        app.dependency_overrides.clear()
        assert res_sa.status_code == 403

        # Inspector -> 403
        client_insp = _make_client_for_user(authority_users["inspector"], db_session)
        res_insp = client_insp.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state"},
        )
        app.dependency_overrides.clear()
        assert res_insp.status_code == 403

    def test_refer_state_generates_audit_log(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="dc_refer_state_audit",
        )

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Referring with audit trail."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200

        audit = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id, action="ESCALATION_REFER_STATE")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_id == dc.id
        details = json.loads(audit.details) if audit.details else {}
        assert details.get("level") == "state"
        assert details.get("status") == "open"

    def test_refer_state_creates_notification(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="dc_refer_state_notif",
        )

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Notifying state authority."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200

        # Verify notification was created for the state-level escalation
        notif = (
            db_session.query(Notification)
            .filter_by(escalation_id=esc.id)
            .order_by(Notification.id.desc())
            .first()
        )
        assert notif is not None


class TestCheckpoint4DistrictCollectorAcknowledge:
    """Checkpoint 4 — District Collector acknowledges a district-level escalation."""

    def test_district_collector_acknowledges_district_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="dc_ack",
        )

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "District collector acknowledges."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "district"
        assert data["status"] == "acknowledged"
        assert data["actor_id"] == dc.id

        db_session.refresh(esc)
        assert esc.acknowledged_by == dc.id
        assert esc.acknowledged_at is not None

    def test_unauthorized_roles_cannot_acknowledge_district(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="unauth_dc_ack",
        )

        # state_admin on district -> 403
        client_sa = _make_client_for_user(authority_users["state_admin"], db_session)
        res_sa = client_sa.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge"},
        )
        app.dependency_overrides.clear()
        assert res_sa.status_code == 403

        # national_admin on district -> 403
        client_na = _make_client_for_user(authority_users["national_admin"], db_session)
        res_na = client_na.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge"},
        )
        app.dependency_overrides.clear()
        assert res_na.status_code == 403


class TestCheckpoint5DistrictCollectorResolve:
    """Checkpoint 5 — District Collector resolves a district-level escalation."""

    def test_district_collector_resolves_district_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="acknowledged",
            product_suffix="dc_resolve",
        )
        esc.acknowledged_by = dc.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "District collector resolved the issue locally."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "district"
        assert data["status"] == "resolved"
        assert data["actor_id"] == dc.id

        db_session.refresh(esc)
        assert esc.resolved_by == dc.id
        assert esc.resolved_at is not None
        assert esc.resolution_notes == "District collector resolved the issue locally."

    def test_resolve_district_without_notes_returns_400(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="acknowledged",
            product_suffix="dc_resolve_no_notes",
        )

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve"},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400

    def test_resolve_district_generates_audit(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="acknowledged",
            product_suffix="dc_resolve_audit",
        )
        esc.acknowledged_by = dc.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Resolved with audit trail."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200

        audit = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id, action="ESCALATION_RESOLVE")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_id == dc.id
        details = json.loads(audit.details) if audit.details else {}
        assert details.get("level") == "district"
        assert details.get("status") == "resolved"


class TestCheckpoint6StateAdminReferNational:
    """Checkpoint 6 — State Admin refers an escalation from state to national."""

    def test_state_admin_refers_to_national(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="acknowledged",
            product_suffix="sa_refer_national",
        )
        esc.acknowledged_by = state_admin.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(state_admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "State admin refers to national authority."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["escalation_id"] == esc.id
        assert data["level"] == "national"
        assert data["status"] == "open"
        assert data["actor_id"] == state_admin.id
        assert data["action"] == "refer_national"

        db_session.refresh(esc)
        assert esc.level == "national"
        assert esc.status == "open"
        assert esc.acknowledged_by is None
        assert esc.acknowledged_at is None

    def test_admin_can_refer_to_national(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="acknowledged",
            product_suffix="admin_refer_national",
        )

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "Admin escalating to national."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "national"
        assert data["status"] == "open"

    def test_cannot_refer_national_from_district_level(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="district_refer_national_invalid",
        )

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "Skip district -> national."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "state" in res.json()["detail"].lower()

    def test_unauthorized_roles_cannot_refer_national(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(
            db_session, inspector, level="state", status="open",
            product_suffix="unauth_refer_national",
        )

        # District collector cannot refer_national
        client_dc = _make_client_for_user(authority_users["district_collector"], db_session)
        res_dc = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "DC trying."},
        )
        app.dependency_overrides.clear()
        assert res_dc.status_code == 403

        # Inspector -> 403
        client_insp = _make_client_for_user(authority_users["inspector"], db_session)
        res_insp = client_insp.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national"},
        )
        app.dependency_overrides.clear()
        assert res_insp.status_code == 403

    def test_refer_national_generates_audit_and_notification(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        state_admin = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="open",
            product_suffix="sa_refer_national_audit",
        )

        client = _make_client_for_user(state_admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "Referring with audit."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200

        # Audit
        audit = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id, action="ESCALATION_REFER_NATIONAL")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_id == state_admin.id
        details = json.loads(audit.details) if audit.details else {}
        assert details.get("level") == "national"
        assert details.get("status") == "open"

        # Notification
        notif = (
            db_session.query(Notification)
            .filter_by(escalation_id=esc.id)
            .order_by(Notification.id.desc())
            .first()
        )
        assert notif is not None


class TestCheckpoint7NationalAdminAcknowledge:
    """Checkpoint 7 — National Admin acknowledges a national-level escalation."""

    def test_national_admin_acknowledges_national_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        na = authority_users["national_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="national", status="open",
            product_suffix="na_ack",
        )

        client = _make_client_for_user(na, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "National admin acknowledges."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "national"
        assert data["status"] == "acknowledged"
        assert data["actor_id"] == na.id

        db_session.refresh(esc)
        assert esc.acknowledged_by == na.id
        assert esc.acknowledged_at is not None

    def test_unauthorized_roles_cannot_acknowledge_national(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(
            db_session, inspector, level="national", status="open",
            product_suffix="unauth_na_ack",
        )

        # district_collector on national -> 403
        client_dc = _make_client_for_user(authority_users["district_collector"], db_session)
        res_dc = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge"},
        )
        app.dependency_overrides.clear()
        assert res_dc.status_code == 403

        # state_admin on national -> 403
        client_sa = _make_client_for_user(authority_users["state_admin"], db_session)
        res_sa = client_sa.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge"},
        )
        app.dependency_overrides.clear()
        assert res_sa.status_code == 403

    def test_admin_can_acknowledge_national_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="national", status="open",
            product_suffix="admin_na_ack",
        )

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Admin ack national."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "acknowledged"


class TestCheckpoint8NationalAdminResolve:
    """Checkpoint 8 — National Admin resolves a national-level escalation."""

    def test_national_admin_resolves_national_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        na = authority_users["national_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="national", status="acknowledged",
            product_suffix="na_resolve",
        )
        esc.acknowledged_by = na.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(esc)

        client = _make_client_for_user(na, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "National admin final resolution."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200
        data = res.json()
        assert data["level"] == "national"
        assert data["status"] == "resolved"
        assert data["actor_id"] == na.id

        db_session.refresh(esc)
        assert esc.resolved_by == na.id
        assert esc.resolved_at is not None
        assert esc.resolution_notes == "National admin final resolution."

    def test_resolve_national_without_notes_returns_400(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        na = authority_users["national_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="national", status="acknowledged",
            product_suffix="na_resolve_no_notes",
        )

        client = _make_client_for_user(na, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve"},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400

    def test_unauthorized_roles_cannot_resolve_national(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        inspector = authority_users["inspector"]
        esc = _create_test_escalation(
            db_session, inspector, level="national", status="acknowledged",
            product_suffix="unauth_na_resolve",
        )

        # district_collector on national -> 403
        client_dc = _make_client_for_user(authority_users["district_collector"], db_session)
        res_dc = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "DC trying national resolve."},
        )
        app.dependency_overrides.clear()
        assert res_dc.status_code == 403

        # state_admin on national -> 403
        client_sa = _make_client_for_user(authority_users["state_admin"], db_session)
        res_sa = client_sa.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "SA trying national resolve."},
        )
        app.dependency_overrides.clear()
        assert res_sa.status_code == 403

    def test_resolve_national_generates_audit(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        na = authority_users["national_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="national", status="acknowledged",
            product_suffix="na_resolve_audit",
        )
        esc.acknowledged_by = na.id
        esc.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()

        client = _make_client_for_user(na, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Final national resolution with audit."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 200

        audit = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id, action="ESCALATION_RESOLVE")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert audit.actor_id == na.id
        details = json.loads(audit.details) if audit.details else {}
        assert details.get("level") == "national"
        assert details.get("status") == "resolved"
        assert details.get("notes") == "Final national resolution with audit."


class TestCheckpoint9EndToEndLifecycle:
    """Checkpoint 9 — Full escalation lifecycle: district → state → national → resolve."""

    def test_full_lifecycle_district_to_national_resolve(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        sa = authority_users["state_admin"]
        na = authority_users["national_admin"]
        inspector = authority_users["inspector"]

        # Step 1: Create district-level open escalation
        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="e2e_full_lifecycle",
        )
        assert esc.level == "district"
        assert esc.status == "open"

        # Step 2: District Collector acknowledges
        client_dc = _make_client_for_user(dc, db_session)
        res = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "DC acknowledges."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "acknowledged"
        assert res.json()["level"] == "district"

        # Step 3: District Collector refers to state
        client_dc = _make_client_for_user(dc, db_session)
        res = client_dc.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Referring to state authority."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["level"] == "state"
        assert res.json()["status"] == "open"

        # Step 4: State Admin acknowledges
        client_sa = _make_client_for_user(sa, db_session)
        res = client_sa.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "State admin acknowledges."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "acknowledged"
        assert res.json()["level"] == "state"

        # Step 5: State Admin refers to national
        client_sa = _make_client_for_user(sa, db_session)
        res = client_sa.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "Referring to national authority."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["level"] == "national"
        assert res.json()["status"] == "open"

        # Step 6: National Admin acknowledges
        client_na = _make_client_for_user(na, db_session)
        res = client_na.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "National admin acknowledges."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "acknowledged"
        assert res.json()["level"] == "national"

        # Step 7: National Admin resolves
        client_na = _make_client_for_user(na, db_session)
        res = client_na.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Final resolution at national level."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "resolved"
        assert res.json()["level"] == "national"

        # Verify final DB state
        db_session.refresh(esc)
        assert esc.level == "national"
        assert esc.status == "resolved"
        assert esc.resolved_by == na.id
        assert esc.resolved_at is not None
        assert esc.resolution_notes == "Final resolution at national level."

        # Verify audit trail has all lifecycle events
        audits = (
            db_session.query(AuditLog)
            .filter_by(object_type="escalation", object_id=esc.id)
            .order_by(AuditLog.id.asc())
            .all()
        )
        audit_actions = [a.action for a in audits]
        assert "ESCALATION_ACKNOWLEDGE" in audit_actions
        assert "ESCALATION_REFER_STATE" in audit_actions
        assert "ESCALATION_REFER_NATIONAL" in audit_actions
        assert "ESCALATION_RESOLVE" in audit_actions


class TestCheckpoint10EdgeCases:
    """Checkpoint 10 — Edge cases and cross-level guard rails."""

    def test_nonexistent_escalation_returns_404(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        client = _make_client_for_user(admin, db_session)
        res = client.post(
            "/api/v1/escalations/99999/action",
            json={"action": "acknowledge", "notes": "Ghost."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 404

    def test_invalid_action_returns_422(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="invalid_action",
        )

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "nuke_it", "notes": "Not a real action."},
        )
        app.dependency_overrides.clear()
        # Pydantic schema validation rejects unknown actions
        assert res.status_code == 422

    def test_cannot_acknowledge_resolved_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="resolved",
            product_suffix="ack_after_resolve",
        )
        esc.resolved_by = dc.id
        esc.resolved_at = datetime.now(timezone.utc)
        esc.resolution_notes = "Already resolved."
        db_session.commit()

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Trying to ack resolved."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 400

    def test_admin_bypasses_level_check_for_all_actions(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Admin can act on any level (no role_level constraint)."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        # National level — admin can acknowledge
        esc = _create_test_escalation(
            db_session, inspector, level="national", status="open",
            product_suffix="admin_any_level",
        )

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Admin on national."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "acknowledged"

        # Then resolve
        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Admin resolves national."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "resolved"


class TestCheckpoint11StrictStateMachine:
    """Checkpoint 11 — Strict escalation state machine enforcement."""

    def test_resolve_requires_acknowledged_status(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Cannot resolve an open (non-acknowledged) escalation."""
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="resolve_needs_ack",
        )

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Trying to resolve without ack."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "acknowledged" in res.json()["detail"].lower()

    def test_resolve_requires_acknowledged_at_state_level(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """State-level: cannot resolve an open escalation."""
        sa = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="open",
            product_suffix="state_resolve_needs_ack",
        )

        client = _make_client_for_user(sa, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Trying state resolve without ack."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "acknowledged" in res.json()["detail"].lower()

    def test_resolve_requires_acknowledged_at_national_level(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """National-level: cannot resolve an open escalation."""
        na = authority_users["national_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="national", status="open",
            product_suffix="national_resolve_needs_ack",
        )

        client = _make_client_for_user(na, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Trying national resolve without ack."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "acknowledged" in res.json()["detail"].lower()

    def test_cannot_refer_state_on_resolved_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Cannot refer a resolved district-level escalation to state."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="resolved",
            product_suffix="refer_state_resolved",
        )
        esc.resolved_by = admin.id
        esc.resolved_at = datetime.now(timezone.utc)
        esc.resolution_notes = "Already resolved."
        db_session.commit()

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Trying to refer resolved."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "resolved" in res.json()["detail"].lower()

    def test_cannot_refer_national_on_resolved_escalation(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Cannot refer a resolved state-level escalation to national."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="resolved",
            product_suffix="refer_national_resolved",
        )
        esc.resolved_by = admin.id
        esc.resolved_at = datetime.now(timezone.utc)
        esc.resolution_notes = "Already resolved."
        db_session.commit()

        client = _make_client_for_user(admin, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_national", "notes": "Trying to refer resolved to national."},
        )
        app.dependency_overrides.clear()

        assert res.status_code == 400
        assert "resolved" in res.json()["detail"].lower()

    def test_e2e_strict_lifecycle_ack_then_resolve(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """E2E: open → ack → resolve is the only valid resolve path."""
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="strict_ack_resolve",
        )

        client = _make_client_for_user(dc, db_session)

        # Attempt resolve from open → FAIL
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Skip ack."},
        )
        assert res.status_code == 400

        # Acknowledge → OK
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Proper ack."},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "acknowledged"

        # Resolve → OK
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "resolve", "notes": "Now resolve properly."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["status"] == "resolved"

    def test_e2e_strict_lifecycle_ack_then_refer(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """E2E: open → ack → refer_state is valid from acknowledged status."""
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="strict_ack_refer",
        )

        client = _make_client_for_user(dc, db_session)

        # Acknowledge → OK
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "acknowledge", "notes": "Ack first."},
        )
        assert res.status_code == 200

        # Refer to state → OK
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Now refer to state."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["level"] == "state"
        assert res.json()["status"] == "open"

    def test_refer_state_from_open_without_ack_is_allowed(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Referral from open is allowed (unlike resolve, referral doesn't require ack)."""
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="refer_open_ok",
        )

        client = _make_client_for_user(dc, db_session)
        res = client.post(
            f"/api/v1/escalations/{esc.id}/action",
            json={"action": "refer_state", "notes": "Urgent escalation without ack."},
        )
        app.dependency_overrides.clear()
        assert res.status_code == 200
        assert res.json()["level"] == "state"


class TestCheckpoint12ReferralTimestamps:
    """Checkpoint 12 — Dedicated referral timestamps and actor tracking."""

    def test_refer_state_records_referred_by_and_timestamp(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """District Collector referring to State records referred_by and referred_at."""
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="ref_time_dc",
        )
        assert esc.referred_by is None
        assert esc.referred_at is None

        client = _make_client_for_user(dc, db_session)
        try:
            res = client.post(
                f"/api/v1/escalations/{esc.id}/action",
                json={"action": "refer_state", "notes": "Referring to State level."},
            )
            assert res.status_code == 200

            # Query DB directly to verify persistence
            db_session.refresh(esc)
            assert esc.referred_by == dc.id
            assert esc.referred_at is not None

            # Verify via GET endpoint
            res_get = client.get(f"/api/v1/escalations/{esc.id}")
            assert res_get.status_code == 200
            data = res_get.json()
            assert data["referred_by"] == dc.id
            assert data["referred_at"] is not None
        finally:
            app.dependency_overrides.clear()

    def test_refer_national_records_referred_by_and_timestamp(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """State Admin referring to National updates referred_by and referred_at."""
        sa = authority_users["state_admin"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="state", status="open",
            product_suffix="ref_time_sa",
        )

        client = _make_client_for_user(sa, db_session)
        try:
            res = client.post(
                f"/api/v1/escalations/{esc.id}/action",
                json={"action": "refer_national", "notes": "Referring to National authority."},
            )
            assert res.status_code == 200

            db_session.refresh(esc)
            assert esc.referred_by == sa.id
            assert esc.referred_at is not None

            # Verify via GET endpoint
            res_get = client.get(f"/api/v1/escalations/{esc.id}")
            assert res_get.status_code == 200
            data = res_get.json()
            assert data["referred_by"] == sa.id
            assert data["referred_at"] is not None
        finally:
            app.dependency_overrides.clear()

    def test_escalation_list_includes_referral_fields(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """GET /api/v1/escalations returns referred_by and referred_at in the items."""
        admin = authority_users["admin"]
        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(
            db_session, inspector, level="district", status="open",
            product_suffix="ref_list_check",
        )

        client_dc = _make_client_for_user(dc, db_session)
        try:
            res_action = client_dc.post(
                f"/api/v1/escalations/{esc.id}/action",
                json={"action": "refer_state", "notes": "Listing test referral."},
            )
            assert res_action.status_code == 200
        finally:
            app.dependency_overrides.clear()

        client_admin = _make_client_for_user(admin, db_session)
        try:
            res_list = client_admin.get("/api/v1/escalations/")
            assert res_list.status_code == 200
            items = res_list.json()
            matching = [item for item in items if item["id"] == esc.id]
            assert len(matching) == 1
            assert matching[0]["referred_by"] == dc.id
            assert matching[0]["referred_at"] is not None
        finally:
            app.dependency_overrides.clear()


class TestCheckpoint13FullEndToEndAuthorityLifecycle:
    """Checkpoint 13 — Complete End-to-End Authority Lifecycle with full audit and notification verification."""

    def test_full_chain_from_inspection_to_national_resolve(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Full lifecycle: 4 non-compliant inspections -> district escalation -> DC ack -> DC refer_state -> State Admin ack -> State Admin refer_national -> National Admin ack -> National Admin resolve."""
        from app.models.audit_log import AuditLog
        from app.models.notification import Notification
        from app.services.escalation_service import evaluate_product_escalation

        admin = authority_users["admin"]
        inspector = authority_users["inspector"]
        dc = authority_users["district_collector"]
        sa = authority_users["state_admin"]
        na = authority_users["national_admin"]

        product = Product(
            product_name="Lifecycle E2E Full Chain Product",
            brand_name="E2E Brand",
            category="Beverages",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        # Create 4 non-compliant inspections
        last_insp = None
        for i in range(4):
            insp = Inspection(
                inspector_id=inspector.id,
                product_id=product.id,
                status=InspectionStatus.COMPLETED,
                compliance_status=ComplianceStatus.NON_COMPLIANT,
                reference_number=f"E2E-CHAIN-INSP-{i}-{product.id}",
            )
            db_session.add(insp)
            db_session.commit()
            db_session.refresh(insp)
            last_insp = insp

        # Evaluate escalation
        escalation = evaluate_product_escalation(db=db_session, inspection_id=last_insp.id)
        assert escalation is not None
        assert escalation.level == "district"
        assert escalation.status == "open"
        assert escalation.failed_inspection_count == 4

        # 1. Verify District Notification
        notif_dc = db_session.scalar(
            select(Notification).where(
                Notification.escalation_id == escalation.id,
                Notification.recipient_role == "district_collector",
            )
        )
        assert notif_dc is not None
        assert notif_dc.status == "pending"

        # 2. Verify ESCALATION_CREATED audit log
        audit_create = db_session.scalar(
            select(AuditLog).where(
                AuditLog.object_type == "escalation",
                AuditLog.object_id == escalation.id,
                AuditLog.action == "ESCALATION_CREATED",
            )
        )
        assert audit_create is not None

        # 3. District Collector Acknowledges
        client_dc = _make_client_for_user(dc, db_session)
        try:
            res_ack = client_dc.post(
                f"/api/v1/escalations/{escalation.id}/action",
                json={"action": "acknowledge", "notes": "DC acknowledged receipt."},
            )
            assert res_ack.status_code == 200
            assert res_ack.json()["status"] == "acknowledged"
            assert res_ack.json()["actor_id"] == dc.id

            db_session.refresh(escalation)
            assert escalation.status == "acknowledged"
            assert escalation.acknowledged_by == dc.id
            assert escalation.acknowledged_at is not None

            # 4. District Collector Refers to State
            res_ref = client_dc.post(
                f"/api/v1/escalations/{escalation.id}/action",
                json={"action": "refer_state", "notes": "Referring to State due to multi-district violation."},
            )
            assert res_ref.status_code == 200
            assert res_ref.json()["level"] == "state"
            assert res_ref.json()["status"] == "open"
        finally:
            app.dependency_overrides.clear()

        db_session.refresh(escalation)
        assert escalation.level == "state"
        assert escalation.status == "open"
        assert escalation.referred_by == dc.id
        assert escalation.referred_at is not None

        # Verify State Admin Notification
        notif_sa = db_session.scalar(
            select(Notification).where(
                Notification.escalation_id == escalation.id,
                Notification.recipient_role == "state_admin",
            )
        )
        assert notif_sa is not None
        assert notif_sa.status == "pending"

        # 5. State Admin Acknowledges
        client_sa = _make_client_for_user(sa, db_session)
        try:
            res_sa_ack = client_sa.post(
                f"/api/v1/escalations/{escalation.id}/action",
                json={"action": "acknowledge", "notes": "State Admin taking over."},
            )
            assert res_sa_ack.status_code == 200
            assert res_sa_ack.json()["status"] == "acknowledged"
            assert res_sa_ack.json()["actor_id"] == sa.id

            db_session.refresh(escalation)
            assert escalation.status == "acknowledged"
            assert escalation.acknowledged_by == sa.id

            # 6. State Admin Refers to National
            res_sa_ref = client_sa.post(
                f"/api/v1/escalations/{escalation.id}/action",
                json={"action": "refer_national", "notes": "Interstate scope detected; referring to National."},
            )
            assert res_sa_ref.status_code == 200
            assert res_sa_ref.json()["level"] == "national"
            assert res_sa_ref.json()["status"] == "open"
        finally:
            app.dependency_overrides.clear()

        db_session.refresh(escalation)
        assert escalation.level == "national"
        assert escalation.status == "open"
        assert escalation.referred_by == sa.id
        assert escalation.referred_at is not None

        # Verify National Admin Notification
        notif_na = db_session.scalar(
            select(Notification).where(
                Notification.escalation_id == escalation.id,
                Notification.recipient_role == "national_admin",
            )
        )
        assert notif_na is not None
        assert notif_na.status == "pending"

        # 7. National Admin Acknowledges & Resolves
        client_na = _make_client_for_user(na, db_session)
        try:
            res_na_ack = client_na.post(
                f"/api/v1/escalations/{escalation.id}/action",
                json={"action": "acknowledge", "notes": "National Admin review started."},
            )
            assert res_na_ack.status_code == 200
            assert res_na_ack.json()["status"] == "acknowledged"

            res_na_res = client_na.post(
                f"/api/v1/escalations/{escalation.id}/action",
                json={"action": "resolve", "notes": "Nationwide product recall and advisory issued. Resolved."},
            )
            assert res_na_res.status_code == 200
            assert res_na_res.json()["status"] == "resolved"
            assert res_na_res.json()["actor_id"] == na.id
        finally:
            app.dependency_overrides.clear()

        db_session.refresh(escalation)
        assert escalation.status == "resolved"
        assert escalation.resolved_by == na.id
        assert escalation.resolved_at is not None
        assert "Nationwide product recall" in (escalation.resolution_notes or "")

        # Verify all audit logs exist for this escalation
        audit_logs = list(
            db_session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.object_type == "escalation",
                    AuditLog.object_id == escalation.id,
                )
                .order_by(AuditLog.id.asc())
            ).all()
        )
        actions = [log.action for log in audit_logs]
        assert "ESCALATION_CREATED" in actions
        assert "ESCALATION_ACKNOWLEDGE" in actions
        assert "ESCALATION_REFER_STATE" in actions
        assert "ESCALATION_REFER_NATIONAL" in actions
        assert "ESCALATION_RESOLVE" in actions


class TestCheckpoint14AdminEndToEndValidation:
    """Checkpoint 14 — Admin end-to-end permissions and state-machine validation."""

    def test_admin_valid_district_actions(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Admin can ACK, resolve, and refer_state on district escalation."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        # Admin ACK & Resolve
        esc1 = _create_test_escalation(db_session, inspector, level="district", status="open", product_suffix="adm_d1")
        client = _make_client_for_user(admin, db_session)
        try:
            res_ack = client.post(f"/api/v1/escalations/{esc1.id}/action", json={"action": "acknowledge", "notes": "Admin ack district."})
            assert res_ack.status_code == 200
            res_res = client.post(f"/api/v1/escalations/{esc1.id}/action", json={"action": "resolve", "notes": "Admin resolve district."})
            assert res_res.status_code == 200
            assert res_res.json()["status"] == "resolved"

            # Admin refer_state
            esc2 = _create_test_escalation(db_session, inspector, level="district", status="open", product_suffix="adm_d2")
            res_ref = client.post(f"/api/v1/escalations/{esc2.id}/action", json={"action": "refer_state", "notes": "Admin refer to state."})
            assert res_ref.status_code == 200
            assert res_ref.json()["level"] == "state"
        finally:
            app.dependency_overrides.clear()

    def test_admin_valid_state_and_national_actions(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Admin can ACK, resolve, and refer_national on state escalation, and ACK/resolve on national escalation."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        client = _make_client_for_user(admin, db_session)
        try:
            # State level: ACK & Refer National
            esc_state = _create_test_escalation(db_session, inspector, level="state", status="open", product_suffix="adm_s1")
            res_ref_nat = client.post(f"/api/v1/escalations/{esc_state.id}/action", json={"action": "refer_national", "notes": "Admin refer national."})
            assert res_ref_nat.status_code == 200
            assert res_ref_nat.json()["level"] == "national"

            # National level: ACK & Resolve
            esc_nat = _create_test_escalation(db_session, inspector, level="national", status="open", product_suffix="adm_n1")
            res_ack_nat = client.post(f"/api/v1/escalations/{esc_nat.id}/action", json={"action": "acknowledge", "notes": "Admin ack national."})
            assert res_ack_nat.status_code == 200
            res_res_nat = client.post(f"/api/v1/escalations/{esc_nat.id}/action", json={"action": "resolve", "notes": "Admin resolve national."})
            assert res_res_nat.status_code == 200
            assert res_res_nat.json()["status"] == "resolved"
        finally:
            app.dependency_overrides.clear()

    def test_admin_invalid_operations_fail(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Admin cannot violate level transitions, act on resolved escalations, or resolve without notes."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        client = _make_client_for_user(admin, db_session)
        try:
            # 1. Admin refer_national from district -> 400
            esc_dist = _create_test_escalation(db_session, inspector, level="district", status="open", product_suffix="adm_inv_1")
            res1 = client.post(f"/api/v1/escalations/{esc_dist.id}/action", json={"action": "refer_national", "notes": "Skip state."})
            assert res1.status_code == 400

            # 2. Admin refer_state from state -> 400
            esc_state = _create_test_escalation(db_session, inspector, level="state", status="open", product_suffix="adm_inv_2")
            res2 = client.post(f"/api/v1/escalations/{esc_state.id}/action", json={"action": "refer_state", "notes": "Invalid backward."})
            assert res2.status_code == 400

            # 3. Admin refer_state from national -> 400
            esc_nat = _create_test_escalation(db_session, inspector, level="national", status="open", product_suffix="adm_inv_3")
            res3 = client.post(f"/api/v1/escalations/{esc_nat.id}/action", json={"action": "refer_state", "notes": "Invalid."})
            assert res3.status_code == 400

            # 4. Admin refer_national from national -> 400
            res4 = client.post(f"/api/v1/escalations/{esc_nat.id}/action", json={"action": "refer_national", "notes": "Invalid."})
            assert res4.status_code == 400

            # 5. Admin act on resolved escalation -> 400
            esc_res = _create_test_escalation(db_session, inspector, level="district", status="resolved", product_suffix="adm_inv_5")
            res5 = client.post(f"/api/v1/escalations/{esc_res.id}/action", json={"action": "acknowledge", "notes": "Reopen attempt."})
            assert res5.status_code == 400

            # 6. Admin resolve without notes -> 400
            esc_ack = _create_test_escalation(db_session, inspector, level="district", status="acknowledged", product_suffix="adm_inv_6")
            res6 = client.post(f"/api/v1/escalations/{esc_ack.id}/action", json={"action": "resolve", "notes": ""})
            assert res6.status_code == 400
        finally:
            app.dependency_overrides.clear()


class TestCheckpoint15NotificationReliability:
    """Checkpoint 15 — Notification reliability, fields integrity, and deduplication."""

    def test_notification_fields_and_deduplication(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Notification has all required fields, status is pending (never fake sent), and duplicate calls do not create duplicate rows."""
        from app.models.notification import Notification, NotificationStatus
        from app.services.notification_service import create_escalation_notification

        inspector = authority_users["inspector"]
        esc = _create_test_escalation(db_session, inspector, level="district", status="open", product_suffix="notif_test")

        # First call creates notification
        n1 = create_escalation_notification(db=db_session, escalation=esc)
        assert n1.escalation_id == esc.id
        assert n1.recipient_role == "district_collector"
        assert n1.recipient_name == "District Collector"
        assert n1.channel == "in_app"
        assert n1.status == NotificationStatus.PENDING
        assert "LABELGUARD Escalation" in n1.subject
        assert n1.message is not None
        assert n1.created_at is not None

        # Second call returns existing (deduplication)
        n2 = create_escalation_notification(db=db_session, escalation=esc)
        assert n1.id == n2.id

        # Total notifications for this escalation remains 1
        count = db_session.scalar(
            select(func.count(Notification.id)).where(Notification.escalation_id == esc.id)
        )
        assert count == 1


class TestCheckpoint16AuditCompleteness:
    """Checkpoint 16 — Audit logging completeness and actor attribution."""

    def test_audit_logs_capture_actor_and_details_correctly(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Audit records capture actor_id from auth token and record proper action and details."""
        import json
        from app.models.audit_log import AuditLog

        dc = authority_users["district_collector"]
        inspector = authority_users["inspector"]

        esc = _create_test_escalation(db_session, inspector, level="district", status="open", product_suffix="audit_comp")

        client = _make_client_for_user(dc, db_session)
        try:
            res = client.post(
                f"/api/v1/escalations/{esc.id}/action",
                json={"action": "acknowledge", "notes": "Audit verification note."},
            )
            assert res.status_code == 200
        finally:
            app.dependency_overrides.clear()

        # Check audit log in DB
        log = db_session.scalar(
            select(AuditLog)
            .where(
                AuditLog.object_type == "escalation",
                AuditLog.object_id == esc.id,
                AuditLog.action == "ESCALATION_ACKNOWLEDGE",
            )
            .order_by(AuditLog.id.desc())
        )
        assert log is not None
        assert log.actor_id == dc.id
        assert log.created_at is not None
        details = json.loads(log.details) if log.details else {}
        assert details.get("status") == "acknowledged"
        assert details.get("notes") == "Audit verification note."


class TestCheckpoint17EscalationListingDashboardAPI:
    """Checkpoint 17 — Escalation listing/dashboard API with filtering, pagination, and RBAC."""

    def test_listing_filters_and_pagination(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """GET /api/v1/escalations/ correctly filters by level, status, product_id, and applies pagination."""
        admin = authority_users["admin"]
        inspector = authority_users["inspector"]

        esc_d = _create_test_escalation(db_session, inspector, level="district", status="open", product_suffix="list_d")
        esc_s = _create_test_escalation(db_session, inspector, level="state", status="acknowledged", product_suffix="list_s")
        esc_n = _create_test_escalation(db_session, inspector, level="national", status="resolved", product_suffix="list_n")

        client = _make_client_for_user(admin, db_session)
        try:
            # 1. Filter by level=district
            res_d = client.get("/api/v1/escalations/?level=district")
            assert res_d.status_code == 200
            ids_d = [item["id"] for item in res_d.json()]
            assert esc_d.id in ids_d
            assert esc_s.id not in ids_d

            # 2. Filter by status=acknowledged
            res_ack = client.get("/api/v1/escalations/?status=acknowledged")
            assert res_ack.status_code == 200
            ids_ack = [item["id"] for item in res_ack.json()]
            assert esc_s.id in ids_ack
            assert esc_d.id not in ids_ack

            # 3. Filter by product_id
            res_prod = client.get(f"/api/v1/escalations/?product_id={esc_n.product_id}")
            assert res_prod.status_code == 200
            ids_prod = [item["id"] for item in res_prod.json()]
            assert esc_n.id in ids_prod
            assert esc_d.id not in ids_prod

            # 4. Pagination
            res_page = client.get("/api/v1/escalations/?skip=0&limit=2")
            assert res_page.status_code == 200
            assert len(res_page.json()) <= 2
        finally:
            app.dependency_overrides.clear()

    def test_listing_rbac_for_auditor_and_unauthorized(
        self,
        db_session: Session,
        authority_users: dict[str, User],
    ):
        """Auditor can view escalation list (read-only); inspector is forbidden from arbitrary listing without authorized role."""
        auditor = authority_users["auditor"]
        inspector = authority_users["inspector"]

        # Auditor can list
        client_aud = _make_client_for_user(auditor, db_session)
        try:
            res_aud = client_aud.get("/api/v1/escalations/")
            assert res_aud.status_code == 200
            assert isinstance(res_aud.json(), list)
        finally:
            app.dependency_overrides.clear()

        # Inspector cannot list all escalations
        client_insp = _make_client_for_user(inspector, db_session)
        try:
            res_insp = client_insp.get("/api/v1/escalations/")
            assert res_insp.status_code == 403
        finally:
            app.dependency_overrides.clear()


