"""Explainability router."""

from fastapi import APIRouter

router = APIRouter(prefix="/explain", tags=["explainability"])

@router.get("/{driver_id}")
def get_explanation(driver_id: str):
    return {"driver_id": driver_id, "status": "Not implemented"}
