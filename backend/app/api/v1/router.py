from fastapi import APIRouter

from app.api.v1.endpoints import (
    analysis,
    auth,
    barcodes,
    compliance,
    escalations,
    health,
    images,
    inspections,
    manufacturer_references,
    notifications,
    products,
    reports,
    rules,
)


api_router = APIRouter()


api_router.include_router(
    health.router,
    tags=["Health"],
)

api_router.include_router(
    auth.router,
)

api_router.include_router(
    inspections.router,
)

api_router.include_router(
    images.router,
)

api_router.include_router(
    products.router,
)

api_router.include_router(
    barcodes.router,
)

api_router.include_router(
    manufacturer_references.router,
)

api_router.include_router(
    reports.router,
)

api_router.include_router(
    escalations.router,
)

api_router.include_router(
    notifications.router,
)

api_router.include_router(
    rules.router,
)

api_router.include_router(
    analysis.router,
)

api_router.include_router(
    compliance.router,
)

