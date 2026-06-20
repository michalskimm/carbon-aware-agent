import asyncio
from collections.abc import Awaitable, Callable

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

# Transient transport failures worth retrying — the *inner* exception types.
_RETRYABLE_INNER = (httpx.ConnectError, httpx.TimeoutException, TimeoutError)


def _is_retryable(exc: BaseException) -> bool:
    """True if exc is a transient transport failure, including when wrapped in an
    ExceptionGroup (the MCP/anyio stack wraps connection errors in a group)."""
    if isinstance(exc, _RETRYABLE_INNER):
        return True
    if isinstance(exc, BaseExceptionGroup):
        # Retry only if every contained error is itself retryable - don't retry
        # a group that also holds a non-transient failure (e.g. auth).
        return all(_is_retryable(e) for e in exc.exceptions)
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),  # 1s, 2s, 4s... capped at 10s
    retry=retry_if_exception(_is_retryable),  # predicate, not type — sees inside groups
    reraise=True,  # raise the real error, not RetryError
)
async def call_with_resilience(coro_factory: Callable[[], Awaitable]) -> object:
    """Run an async call with a timeout, retried on transient failure.
    coro_factory is a zero-arg callable returning a fresh coroutine each attempt
    (a coroutine can only be awaited once, so we rebuild it per retry).
    """
    return await asyncio.wait_for(coro_factory(), timeout=15.0)
