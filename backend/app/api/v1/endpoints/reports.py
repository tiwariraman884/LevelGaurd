"""
backend/app/api/v1/endpoints/reports.py

API Endpoints for generating and downloading Legal Metrology inspection reports in PDF and editable DOCX formats.
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.reports.docx_generator import generate_inspection_docx
from app.reports.pdf_generator import generate_inspection_pdf
from app.services.inspection_service import get_inspection


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


@router.get(
    "/{inspection_id}/pdf",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles("admin", "inspector", "auditor"))],
)
def download_inspection_pdf(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and download the official Legal Metrology inspection report in PDF format.
    """
    inspection = get_inspection(db=db, inspection_id=inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    user_role = getattr(getattr(current_user, "role", None), "name", None)
    if (
        inspection.inspector_id != current_user.id
        and user_role not in ("admin", "auditor")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this inspection report",
        )

    try:
        pdf_path: Path = generate_inspection_pdf(db=db, inspection_id=inspection_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF report: {exc}",
        ) from exc

    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Generated PDF report file could not be found.",
        )

    filename = f"{inspection.reference_number}_inspection_report.pdf"

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
    )


@router.get(
    "/{inspection_id}/docx",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles("admin", "inspector", "auditor"))],
)
def download_inspection_docx(
    inspection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate and download the official editable Legal Metrology inspection report in Microsoft Word (.docx) format.
    """
    inspection = get_inspection(db=db, inspection_id=inspection_id)
    if inspection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    user_role = getattr(getattr(current_user, "role", None), "name", None)
    if (
        inspection.inspector_id != current_user.id
        and user_role not in ("admin", "auditor")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this inspection report",
        )

    try:
        docx_path: Path = generate_inspection_docx(db=db, inspection_id=inspection_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate DOCX report: {exc}",
        ) from exc

    if not docx_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Generated DOCX report file could not be found.",
        )

    filename = f"{inspection.reference_number}_inspection_report.docx"

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )
