from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.image import ImageResponse


class FailedImageDetail(BaseModel):
    file_name: str
    error: str
    image_type: str | None = None


class BulkImageUploadResponse(BaseModel):
    inspection_id: int
    total_uploaded: int
    successful_count: int
    failed_count: int
    successful_images: list[ImageResponse]
    failed_images: list[FailedImageDetail] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BulkScanResponse(BaseModel):
    inspection_id: int
    reference_number: str
    total_images: int
    successfully_processed: int
    failed_images: list[dict[str, Any]] = Field(default_factory=list)
    overall_status: str
    compliance_status: str
    processing_duration_seconds: float
    images: list[dict[str, Any]] = Field(default_factory=list)
    declarations: dict[str, Any] = Field(default_factory=dict)
    compliance_results: list[dict[str, Any]] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)
    escalation: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)
