"""Live Race Tracker router."""

from fastapi import APIRouter

router = APIRouter(prefix="/live", tags=["live"])

@router.get("/status")
def get_live_status():
    return {"status": "Not implemented"}
