import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
from fastapi import UploadFile
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inspection import Inspection
from app.models.inspection_image import InspectionImage


STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage" / "uploads"

ALLOWED_IMAGE_TYPES = {
    "front",
    "back",
    "side",
    "top",
    "bottom",
    "other",
}

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_BULK_IMAGES = 15


def validate_image_type(
    image_type: str | None,
    default: str = "other",
) -> str:
    if not image_type or not str(image_type).strip():
        return default

    normalized = str(image_type).strip().lower()
    if normalized not in ALLOWED_IMAGE_TYPES:
        return default

    return normalized


def validate_mime_type(content_type: str | None) -> str:
    if not content_type or content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            "Unsupported image format. Use JPEG, PNG, or WebP."
        )

    return content_type


def validate_image_content(content: bytes) -> tuple[int, int]:
    """
    Validate that raw bytes decode to a readable, uncorrupted image.
    Returns (width, height).
    """
    if not content:
        raise ValueError("Image file is empty.")

    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None or img.size == 0:
        raise ValueError("Image file is corrupted or cannot be decoded.")

    height, width = img.shape[:2]
    if height < 10 or width < 10:
        raise ValueError("Image dimensions too small (minimum 10x10 pixels).")

    return width, height


def calculate_file_hash(file_path: str) -> str:
    hasher = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


def read_and_hash_upload(
    upload_file: UploadFile,
) -> tuple[bytes, str]:

    content = upload_file.file.read()

    if not content:
        raise ValueError("Image file is empty.")

    if len(content) > MAX_FILE_SIZE:
        raise ValueError("Image size must not exceed 10 MB.")

    validate_image_content(content)

    file_hash = hashlib.sha256(content).hexdigest()

    upload_file.file.seek(0)

    return content, file_hash


def save_upload_file(
    upload_file: UploadFile,
    content: bytes,
) -> tuple[str, int]:

    STORAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    original_name = Path(
        upload_file.filename or "image"
    ).name

    extension = Path(
        original_name
    ).suffix.lower()

    if extension not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        raise ValueError(
            "Unsupported file extension. "
            "Use .jpg, .jpeg, .png, or .webp."
        )

    stored_name = f"{uuid4().hex}{extension}"

    destination = STORAGE_DIR / stored_name

    try:
        destination.write_bytes(content)
    except Exception:
        if destination.exists():
            destination.unlink()

        raise

    return str(destination), len(content)


def find_duplicate_image(
    db: Session,
    inspection_id: int,
    file_hash: str,
) -> InspectionImage | None:

    statement = (
        select(InspectionImage)
        .where(
            InspectionImage.inspection_id == inspection_id,
            InspectionImage.content_hash == file_hash,
        )
        .limit(1)
    )

    return db.scalar(statement)


def create_inspection_image(
    db: Session,
    inspection_id: int,
    image_type: str,
    upload_file: UploadFile,
) -> InspectionImage:

    inspection = db.get(
        Inspection,
        inspection_id,
    )

    if inspection is None:
        raise LookupError(
            "Inspection not found."
        )

    normalized_type = validate_image_type(
        image_type
    )

    mime_type = validate_mime_type(
        upload_file.content_type
    )

    content, file_hash = read_and_hash_upload(
        upload_file
    )

    duplicate = find_duplicate_image(
        db=db,
        inspection_id=inspection_id,
        file_hash=file_hash,
    )

    if duplicate is not None:
        raise ValueError(
            "Duplicate image already exists for "
            f"this inspection (image_id={duplicate.id})."
        )

    file_path, file_size = save_upload_file(
        upload_file,
        content,
    )

    image = InspectionImage(
        inspection_id=inspection_id,
        file_name=Path(
            upload_file.filename or "image"
        ).name,
        file_path=file_path,
        image_type=normalized_type,
        file_size=file_size,
        mime_type=mime_type,
        content_hash=file_hash,
    )

    try:
        db.add(image)
        db.commit()
        db.refresh(image)

    except Exception:
        db.rollback()

        stored_file = Path(file_path)

        if stored_file.exists():
            stored_file.unlink()

        raise

    return image


def create_inspection_images_bulk(
    db: Session,
    inspection_id: int,
    upload_files: list[UploadFile],
    image_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Upload and validate multiple images for an inspection.
    Handles per-image validation errors gracefully so valid images can be stored.
    """
    if not upload_files:
        raise ValueError("No image files provided.")

    if len(upload_files) > MAX_BULK_IMAGES:
        raise ValueError(
            f"Maximum {MAX_BULK_IMAGES} images allowed per bulk request. Received {len(upload_files)}."
        )

    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        raise LookupError("Inspection not found.")

    successful_images: list[InspectionImage] = []
    failed_images: list[dict[str, Any]] = []

    seen_hashes_in_batch: set[str] = set()

    for idx, upload_file in enumerate(upload_files):
        fname = Path(upload_file.filename or f"image_{idx + 1}").name
        raw_type = image_types[idx] if image_types and idx < len(image_types) else "other"
        img_type = validate_image_type(raw_type)

        try:
            mime_type = validate_mime_type(upload_file.content_type)
            content, file_hash = read_and_hash_upload(upload_file)

            if file_hash in seen_hashes_in_batch:
                failed_images.append({
                    "file_name": fname,
                    "image_type": img_type,
                    "error": "Duplicate image in the same bulk request.",
                })
                continue

            duplicate = find_duplicate_image(
                db=db,
                inspection_id=inspection_id,
                file_hash=file_hash,
            )
            if duplicate is not None:
                failed_images.append({
                    "file_name": fname,
                    "image_type": img_type,
                    "error": f"Duplicate image already exists for this inspection (image_id={duplicate.id}).",
                })
                continue

            file_path, file_size = save_upload_file(
                upload_file,
                content,
            )

            image = InspectionImage(
                inspection_id=inspection_id,
                file_name=fname,
                file_path=file_path,
                image_type=img_type,
                file_size=file_size,
                mime_type=mime_type,
                content_hash=file_hash,
            )

            db.add(image)
            db.flush()
            db.refresh(image)

            seen_hashes_in_batch.add(file_hash)
            successful_images.append(image)

        except Exception as exc:
            failed_images.append({
                "file_name": fname,
                "image_type": img_type,
                "error": str(exc),
            })

    if successful_images:
        db.commit()
    else:
        db.rollback()

    return {
        "inspection_id": inspection_id,
        "total_uploaded": len(upload_files),
        "successful_count": len(successful_images),
        "failed_count": len(failed_images),
        "successful_images": successful_images,
        "failed_images": failed_images,
    }


def list_inspection_images(
    db: Session,
    inspection_id: int,
) -> list[InspectionImage]:

    statement = (
        select(InspectionImage)
        .where(
            InspectionImage.inspection_id == inspection_id
        )
        .order_by(
            InspectionImage.created_at.asc()
        )
    )

    return list(
        db.scalars(statement).all()
    )
