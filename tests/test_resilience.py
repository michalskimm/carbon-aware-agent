import httpx
import pytest

from carbon_agent.resilience import call_with_resilience


@pytest.mark.asyncio
async def test_succeeds_first_try():
    async def ok():
        return "done"

    assert await call_with_resilience(ok) == "done"


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("boom")
        return "recovered"

    assert await call_with_resilience(flaky) == "recovered"
    assert attempts["n"] == 3  # retried, didn't give up


@pytest.mark.asyncio
async def test_does_not_retry_non_retryable():
    attempts = {"n": 0}

    async def bad():
        attempts["n"] += 1
        raise ValueError("not transient")

    with pytest.raises(ValueError):
        await call_with_resilience(bad)
    assert attempts["n"] == 1  # failed fast, did not retry


@pytest.mark.asyncio
async def test_retries_connecterror_wrapped_in_exceptiongroup():
    attempts = {"n": 0}

    async def flaky_group():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise ExceptionGroup("mcp", [httpx.ConnectError("boom")])
        return "recovered"

    assert await call_with_resilience(flaky_group) == "recovered"
    assert attempts["n"] == 2  # the predicate saw inside the group and retried
