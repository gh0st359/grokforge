from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_compute_sum_and_product() -> None:
    r = client.post("/compute", json={"x": 3.0, "y": 4.0})
    assert r.status_code == 200
    body = r.json()
    assert body["sum"] == 7.0
    assert body["product"] == 12.0


def test_compute_negative() -> None:
    r = client.post("/compute", json={"x": -2.0, "y": 5.0})
    assert r.status_code == 200
    assert r.json()["sum"] == 3.0
