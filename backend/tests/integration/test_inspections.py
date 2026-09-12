"""
Integration tests for Inspection GPS location metadata, validation, scan lifecycle timing, and endpoints.

Covers requirements A through L:
A. normal inspection with GPS
B. normal inspection without GPS
C. bulk scan with GPS
D. bulk scan without GPS
E. invalid latitude
F. invalid longitude
G. negative accuracy
H. only latitude supplied
I. scan_started_at is automatically generated
J. scan_completed_at is generated after successful analysis
K. re-analysis does not reset scan_started_at
L. response schema exposes the new fields
"""

import io
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.models.inspection import Inspection, InspectionStatus
from app.models.user import User
from app.services.inspection_service import create_inspection


def _create_dummy_image_bytes(text: str = "TEST") -> bytes:
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestInspectionGPSAndScanTiming:
    # A. normal inspection with GPS
    def test_A_normal_inspection_with_gps(self, client: TestClient):
        payload = {
            "latitude": 28.6139,
            "longitude": 77.2090,
            "location_accuracy_m": 4.5,
            "location_captured_at": "2026-09-11T12:00:00Z",
            "location_source": "gps",
        }
        response = client.post("/api/v1/inspections", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["latitude"] == 28.6139
        assert data["longitude"] == 77.2090
        assert data["location_accuracy_m"] == 4.5
        assert data["location_source"] == "gps"
        assert data["location_captured_at"] is not None
        assert data["scan_started_at"] is not None
        assert data["scan_completed_at"] is None

    # B. normal inspection without GPS
    def test_B_normal_inspection_without_gps(self, client: TestClient):
        response = client.post("/api/v1/inspections", json={})
        assert response.status_code == 201
        data = response.json()
        assert data["latitude"] is None
        assert data["longitude"] is None
        assert data["location_accuracy_m"] is None
        assert data["location_source"] is None
        assert data["location_captured_at"] is None
        assert data["scan_started_at"] is not None

    # C. bulk scan with GPS
    def test_C_bulk_scan_with_gps(self, client: TestClient, db_session: Session):
        img_bytes = _create_dummy_image_bytes()
        files = [
            ("files", ("test1.png", img_bytes, "image/png")),
        ]
        data = {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "location_accuracy_m": 8.0,
            "location_source": "fused_network",
            "location_captured_at": "2026-09-11T12:15:00Z",
        }
        response = client.post("/api/v1/inspections/bulk-scan", files=files, data=data)
        assert response.status_code == 201
        res = response.json()
        inspection_id = res["inspection_id"]
        
        # Verify inspection in DB
        db_session.expire_all()
        inspection = db_session.get(Inspection, inspection_id)
        assert inspection is not None
        assert inspection.latitude == 12.9716
        assert inspection.longitude == 77.5946
        assert inspection.location_accuracy_m == 8.0
        assert inspection.location_source == "fused_network"
        assert inspection.scan_started_at is not None
        assert inspection.scan_completed_at is not None

    # D. bulk scan without GPS
    def test_D_bulk_scan_without_gps(self, client: TestClient, db_session: Session):
        img_bytes = _create_dummy_image_bytes()
        files = [
            ("files", ("test2.png", img_bytes, "image/png")),
        ]
        response = client.post("/api/v1/inspections/bulk-scan", files=files)
        assert response.status_code == 201
        res = response.json()
        inspection_id = res["inspection_id"]
        
        db_session.expire_all()
        inspection = db_session.get(Inspection, inspection_id)
        assert inspection is not None
        assert inspection.latitude is None
        assert inspection.longitude is None
        assert inspection.scan_started_at is not None
        assert inspection.scan_completed_at is not None

    # E. invalid latitude
    def test_E_invalid_latitude(self, client: TestClient):
        payload = {
            "latitude": 95.0,
            "longitude": 77.2090,
        }
        response = client.post("/api/v1/inspections", json=payload)
        assert response.status_code in (400, 422)

    # F. invalid longitude
    def test_F_invalid_longitude(self, client: TestClient):
        payload = {
            "latitude": 28.6139,
            "longitude": 185.0,
        }
        response = client.post("/api/v1/inspections", json=payload)
        assert response.status_code in (400, 422)

    # G. negative accuracy
    def test_G_negative_accuracy(self, client: TestClient):
        payload = {
            "latitude": 28.6139,
            "longitude": 77.2090,
            "location_accuracy_m": -2.0,
        }
        response = client.post("/api/v1/inspections", json=payload)
        assert response.status_code in (400, 422)

    # H. only latitude supplied
    def test_H_only_latitude_supplied(self, client: TestClient):
        payload = {
            "latitude": 28.6139,
        }
        response = client.post("/api/v1/inspections", json=payload)
        assert response.status_code in (400, 422)

    # I. scan_started_at is automatically generated
    def test_I_scan_started_at_automatically_generated(self, client: TestClient, admin_user: User, db_session: Session):
        insp = create_inspection(db=db_session, inspector=admin_user)
        assert insp.scan_started_at is not None
        assert insp.scan_started_at.tzinfo is not None

    # J. scan_completed_at is generated after successful analysis
    def test_J_scan_completed_at_generated_after_analysis(self, client: TestClient, db_session: Session):
        img_bytes = _create_dummy_image_bytes()
        files = [
            ("files", ("test_j.png", img_bytes, "image/png")),
        ]
        response = client.post("/api/v1/inspections/bulk-scan", files=files)
        assert response.status_code == 201
        inspection_id = response.json()["inspection_id"]
        
        db_session.expire_all()
        inspection = db_session.get(Inspection, inspection_id)
        assert inspection.scan_completed_at is not None
        assert inspection.completed_at is not None
        assert inspection.scan_completed_at.tzinfo is not None

    # K. re-analysis does not reset scan_started_at
    def test_K_reanalysis_does_not_reset_scan_started_at(self, client: TestClient, db_session: Session):
        img_bytes = _create_dummy_image_bytes()
        files = [
            ("files", ("test_k.png", img_bytes, "image/png")),
        ]
        response = client.post("/api/v1/inspections/bulk-scan", files=files)
        assert response.status_code == 201
        inspection_id = response.json()["inspection_id"]
        
        db_session.expire_all()
        inspection = db_session.get(Inspection, inspection_id)
        initial_started_at = inspection.scan_started_at
        
        # Trigger re-analyze
        re_resp = client.post(f"/api/v1/inspections/{inspection_id}/analyze")
        assert re_resp.status_code == 200
        
        db_session.expire_all()
        inspection_after = db_session.get(Inspection, inspection_id)
        assert inspection_after.scan_started_at == initial_started_at
        assert inspection_after.scan_completed_at is not None

    # L. response schema exposes the new fields
    def test_L_response_schema_exposes_new_fields(self, client: TestClient):
        payload = {
            "latitude": 13.0827,
            "longitude": 80.2707,
            "location_accuracy_m": 3.0,
            "location_source": "cellular",
        }
        create_resp = client.post("/api/v1/inspections", json=payload)
        assert create_resp.status_code == 201
        created_data = create_resp.json()
        inspection_id = created_data["id"]
        
        get_resp = client.get(f"/api/v1/inspections/{inspection_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        
        assert "latitude" in data
        assert "longitude" in data
        assert "location_accuracy_m" in data
        assert "location_captured_at" in data
        assert "location_source" in data
        assert "scan_started_at" in data
        assert "scan_completed_at" in data
        
        assert data["latitude"] == 13.0827
        assert data["longitude"] == 80.2707
        assert data["location_accuracy_m"] == 3.0
        assert data["location_source"] == "cellular"
        assert data["scan_started_at"] is not None
