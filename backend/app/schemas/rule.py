from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class RuleCheckResponse(BaseModel):
    id: int
    field_name: str
    operator: str
    expected_value: str | None = None
    expected_unit: str | None = None
    severity: str
    failure_message: str

    model_config = ConfigDict(from_attributes=True)


class RuleResponse(BaseModel):
    id: int
    rule_code: str
    rule_number: str
    version: int
    title: str
    requirement: str
    effective_from: date
    effective_to: date | None = None
    status: str
    approval_status: str
    created_at: datetime
    updated_at: datetime
    checks_count: int = 0
    checks: list[RuleCheckResponse] = []

    model_config = ConfigDict(from_attributes=True)
