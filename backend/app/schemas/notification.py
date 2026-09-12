from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: int
    escalation_id: int | None = None
    recipient_role: str
    recipient_name: str | None = None
    recipient_email: str | None = None
    channel: str
    subject: str
    message: str
    status: str
    error_message: str | None = None
    created_at: datetime
    sent_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
