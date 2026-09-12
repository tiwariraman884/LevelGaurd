from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EscalationResponse(BaseModel):
    id: int
    product_id: int
    trigger_inspection_id: int
    failed_inspection_count: int
    level: str
    status: str
    reason: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    resolved_by: int | None = None
    resolution_notes: str | None = None
    referred_by: int | None = None
    referred_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EscalationActionRequest(BaseModel):
    action: str = Field(..., pattern="^(acknowledge|resolve|refer_state|refer_national)$")
    notes: str | None = Field(default=None, max_length=2000)


class EscalationActionResponse(BaseModel):
    escalation_id: int
    action: str
    level: str
    status: str
    actor_id: int
    acted_at: datetime
    notes: str | None = None
