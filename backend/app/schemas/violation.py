from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ViolationResponse(BaseModel):
    id: int
    inspection_id: int
    rule_version_id: int
    field_name: str
    severity: str
    status: str
    message: str
    detected_value: str | None = None
    expected_value: str | None = None
    confidence: float | None = None
    evidence: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
