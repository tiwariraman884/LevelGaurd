"""
Unit tests for Inspection GPS location metadata, validation, and scan timing.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.inspection import ComplianceStatus, Inspection, InspectionStatus
from app.models.role import Role
from app.models.user import User
from app.schemas.inspection import InspectionCreate, InspectionResponse
from app.services.inspection_service import (
    create_inspection,
    validate_location_metadata,
)


class TestLocationValidation:
    def test_valid_location_metadata(self):
        dt = datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)
        lat, lng, acc, cap_at, src = validate_location_metadata(
            latitude=28.6139,
            longitude=77.2090,
            location_accuracy_m=5.0,
            location_captured_at=dt,
            location_source="gps",
        )
        assert lat == 28.6139
        assert lng == 77.2090
        assert acc == 5.0
        assert cap_at == dt
        assert src == "gps"

    def test_none_location_metadata(self):
        lat, lng, acc, cap_at, src = validate_location_metadata()
        assert lat is None
        assert lng is None
        assert acc is None
        assert cap_at is None
        assert src is None

    def test_naive_datetime_converted_to_utc(self):
        naive_dt = datetime(2026, 9, 11, 12, 0, 0)
        _, _, _, cap_at, _ = validate_location_metadata(
            latitude=10.0,
            longitude=20.0,
            location_captured_at=naive_dt,
        )
        assert cap_at.tzinfo == timezone.utc

    def test_invalid_latitude_high(self):
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            validate_location_metadata(latitude=91.0, longitude=77.0)

    def test_invalid_latitude_low(self):
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            validate_location_metadata(latitude=-91.0, longitude=77.0)

    def test_invalid_longitude_high(self):
        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            validate_location_metadata(latitude=28.0, longitude=181.0)

    def test_invalid_longitude_low(self):
        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            validate_location_metadata(latitude=28.0, longitude=-181.0)

    def test_negative_accuracy(self):
        with pytest.raises(ValueError, match="Location accuracy must be greater than or equal to 0"):
            validate_location_metadata(latitude=28.0, longitude=77.0, location_accuracy_m=-1.0)

    def test_only_latitude_supplied(self):
        with pytest.raises(ValueError, match="Both latitude and longitude must be provided together"):
            validate_location_metadata(latitude=28.0, longitude=None)

    def test_only_longitude_supplied(self):
        with pytest.raises(ValueError, match="Both latitude and longitude must be provided together"):
            validate_location_metadata(latitude=None, longitude=77.0)

    def test_location_source_too_long(self):
        with pytest.raises(ValueError, match="Location source must not exceed 30 characters"):
            validate_location_metadata(latitude=28.0, longitude=77.0, location_source="a" * 31)


class TestInspectionSchemas:
    def test_inspection_create_with_gps(self):
        schema = InspectionCreate(
            product_id=1,
            latitude=28.6139,
            longitude=77.2090,
            location_accuracy_m=10.0,
            location_source="device_fused",
        )
        assert schema.latitude == 28.6139
        assert schema.longitude == 77.2090
        assert schema.location_accuracy_m == 10.0
        assert schema.location_source == "device_fused"

    def test_inspection_create_without_gps(self):
        schema = InspectionCreate(product_id=1)
        assert schema.latitude is None
        assert schema.longitude is None

    def test_inspection_create_only_latitude_rejected(self):
        with pytest.raises(ValidationError):
            InspectionCreate(latitude=28.6139)

    def test_inspection_create_only_longitude_rejected(self):
        with pytest.raises(ValidationError):
            InspectionCreate(longitude=77.2090)

    def test_inspection_create_out_of_bounds_coords(self):
        with pytest.raises(ValidationError):
            InspectionCreate(latitude=95.0, longitude=50.0)

    def test_inspection_create_negative_accuracy(self):
        with pytest.raises(ValidationError):
            InspectionCreate(latitude=10.0, longitude=10.0, location_accuracy_m=-5.0)

    def test_inspection_response_schema_fields(self):
        now = datetime.now(timezone.utc)
        resp = InspectionResponse(
            id=10,
            inspector_id=1,
            product_id=2,
            reference_number="LG-TEST01",
            status=InspectionStatus.COMPLETED,
            compliance_status=ComplianceStatus.COMPLIANT,
            created_at=now,
            completed_at=now,
            latitude=19.0760,
            longitude=72.8777,
            location_accuracy_m=3.5,
            location_captured_at=now,
            location_source="gps",
            scan_started_at=now,
            scan_completed_at=now,
        )
        assert resp.latitude == 19.0760
        assert resp.longitude == 72.8777
        assert resp.location_accuracy_m == 3.5
        assert resp.location_source == "gps"
        assert resp.scan_started_at == now
        assert resp.scan_completed_at == now
