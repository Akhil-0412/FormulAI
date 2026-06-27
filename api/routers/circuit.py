"""Circuit Meta router."""

from fastapi import APIRouter

router = APIRouter(prefix="/circuit", tags=["circuit"])

@router.get("/{circuit_id}")
def get_circuit_meta(circuit_id: str):
    return {"circuit_id": circuit_id, "status": "Not implemented"}
