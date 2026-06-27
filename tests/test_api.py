"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model_loaded" in data
    assert "db_connected" in data

def test_predict_model_not_loaded(monkeypatch):
    """Test prediction fails gracefully if model is missing."""
    import api.main
    monkeypatch.setattr(api.main, "_ltr_model", None)
    
    response = client.get("/api/v1/predict/2024/1")
    assert response.status_code == 503
    assert "Models not loaded" in response.json()["detail"]
