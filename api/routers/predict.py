"""Predictions router."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/predict", tags=["predictions"])

@router.get("/")
def get_predictions():
    return {"status": "Not implemented"}

@router.post("/simulate")
def simulate_race():
    return {"status": "Not implemented"}
