"""Guardrail tests: the /chat input length cap rejects oversized prompts."""

from fastapi.testclient import TestClient

from carbon_agent.gateway import app


def test_oversized_message_rejected():
    client = TestClient(app)                    # bare client — no lifespan, no agent built
    resp = client.post("/chat", json={"message": "x" * 2001})
    assert resp.status_code == 422              # Pydantic max_length=2000 rejects before the LLM


def test_empty_message_rejected():
    client = TestClient(app)
    resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422              # min_length=1 rejects the empty case
