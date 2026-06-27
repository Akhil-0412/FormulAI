"""Tyre Strategy router."""

from fastapi import APIRouter

router = APIRouter(prefix="/tyre", tags=["tyre"])

@router.get("/strategy")
def get_tyre_strategy():
    return {"status": "Not implemented"}
