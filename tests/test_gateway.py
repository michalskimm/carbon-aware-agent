from fastapi.testclient import TestClient

from carbon_agent.gateway import app


def test_health_and_root():
    client = TestClient(app)  # bare client — does NOT run lifespan (verified)
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/").json()
    assert r["service"] == "carbon-aware-agent"
    assert r["docs"] == "/docs"
