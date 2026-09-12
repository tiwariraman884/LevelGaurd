from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.inspection import ComplianceStatus, InspectionStatus


class InspectionCreate(BaseModel):
    product_id: int | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    location_accuracy_m: float | None = Field(default=None, ge=0.0)
    location_captured_at: datetime | None = None
    location_source: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def validate_coordinates(self) -> "InspectionCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both latitude and longitude must be provided together.")
        if self.location_captured_at is not None and self.location_captured_at.tzinfo is None:
            self.location_captured_at = self.location_captured_at.replace(tzinfo=timezone.utc)
        return self


class InspectionResponse(BaseModel):
    id: int
    inspector_id: int
    product_id: int | None
    reference_number: str
    status: InspectionStatus
    compliance_status: ComplianceStatus
    created_at: datetime
    completed_at: datetime | None
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_m: float | None = None
    location_captured_at: datetime | None = None
    location_source: str | None = None
    scan_started_at: datetime | None = None
    scan_completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class OfficerDecisionRequest(BaseModel):
    decision: str = Field(
        ...,
        pattern="^(APPROVED|REJECTED|REVIEW_REQUIRED)$",
    )
    remarks: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_remarks(self) -> "OfficerDecisionRequest":
        if self.decision in ("REJECTED", "REVIEW_REQUIRED"):
            if not self.remarks or not self.remarks.strip():
                raise ValueError(
                    "Remarks are required for REJECTED or REVIEW_REQUIRED decisions."
                )
        return self


class OfficerDecisionResponse(BaseModel):
    inspection_id: int
    decision: str
    decided_by: int
    decided_at: datetime
    remarks: str | None = None


from app.schemas.declaration import DeclarationResponse
from app.schemas.escalation import EscalationResponse
from app.schemas.image import ImageResponse
from app.schemas.mrp import MRPFindingResponse
from app.schemas.product import ProductResponse
from app.schemas.violation import ViolationResponse


class InspectionDetailResponse(InspectionResponse):
    final_decision: str | None = None
    final_decision_by: int | None = None
    final_decision_at: datetime | None = None
    officer_remarks: str | None = None
    product: ProductResponse | None = None
    images: list[ImageResponse] = []
    declarations: list[DeclarationResponse] = []
    violations: list[ViolationResponse] = []
    mrp_findings: list[MRPFindingResponse] = []
    escalation: EscalationResponse | None = None


