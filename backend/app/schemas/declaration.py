from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeclarationResponse(BaseModel):
    id: int
    inspection_id: int
    field_name: str
    extracted_value: str | None = None
    normalized_value: str | None = None
    is_present: bool = False
    confidence: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
