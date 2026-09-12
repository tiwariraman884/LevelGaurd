from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.declaration import Declaration
    from app.models.escalation import Escalation
    from app.models.inspection_image import InspectionImage
    from app.models.mrp_finding import MRPFinding
    from app.models.product import Product
    from app.models.user import User


class InspectionStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ComplianceStatus(str, Enum):
    PENDING = "pending"
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    REVIEW = "review"


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True)

    inspector_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reference_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[InspectionStatus] = mapped_column(
        SQLEnum(InspectionStatus, name="inspection_status"),
        default=InspectionStatus.CREATED,
        nullable=False,
    )

    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        SQLEnum(ComplianceStatus, name="compliance_status"),
        default=ComplianceStatus.PENDING,
        nullable=False,
    )

    final_decision: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    final_decision_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    final_decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    officer_remarks: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    location_accuracy_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    location_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    location_source: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    scan_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scan_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    inspector: Mapped["User"] = relationship(
        "User",
        back_populates="inspections",
        foreign_keys=[inspector_id],
    )

    product: Mapped["Product | None"] = relationship(
        back_populates="inspections"
    )

    images: Mapped[list["InspectionImage"]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
    )

    declarations: Mapped[list["Declaration"]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
    )

    mrp_findings: Mapped[list["MRPFinding"]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
    )

    escalation: Mapped["Escalation | None"] = relationship(
        back_populates="trigger_inspection",
        uselist=False,
        cascade="all, delete-orphan",
    )
