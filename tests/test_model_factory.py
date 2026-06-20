import pytest

from carbon_agent.agent import _build_model


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not_a_real_provider")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        _build_model()
