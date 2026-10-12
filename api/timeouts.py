"""A wall-clock bound on work that can block indefinitely.

The analysis engine makes network calls to a cloud LLM, calls a
local Ollama server, loads a dataset and runs matplotlib. Every
one of those can hang: a provider that accepts a connection and
never responds, a renderer waiting on a font, a database file
locked by another process.

Without a bound, one such call occupies the request worker until
the client gives up. The caller sees a hung request, the
operator sees nothing at all, and there is no log line
explaining where the time went.

A thread-based timeout is used rather than an async one because
the underlying calls are synchronous and some of them are CPU
bound in C extensions that cannot be interrupted. The
consequence is stated plainly rather than hidden: a thread that
has already started cannot be cancelled, so the bound stops the
*caller* waiting but the abandoned thread runs to completion.
That is acceptable here because the work is short and
idempotent, and it is not acceptable for arbitrary code
execution.

The alternative — pushing a timeout into each provider SDK — is
    better but incomplete, since it would not cover the database
    and rendering paths. This module is the backstop; provider-level
    timeouts would layer on top of it.
"""

from __future__ import annotations

import time
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
)
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_TIMEOUT_SECONDS = 120.0


class OperationTimeout(Exception):
    """
    The operation did not finish inside its bound.

    A distinct type so the endpoint can return 504 rather than
    reporting a provider failure, which would send an operator
    looking at Groq when the real cause was a slow disk.
    """


@dataclass(frozen=True)
class TimeoutReport:
    """
    What a bounded call cost, for logging.

    Timed-out calls are logged with the same shape as
    successful ones, so a latency alert does not have to handle
    a differently-shaped record on the failure path.
    """

    label: str
    duration_ms: int
    timed_out: bool


def run_with_timeout(
    function: Callable[..., Any],
    *args: Any,
    timeout_seconds: float = (
        DEFAULT_TIMEOUT_SECONDS
    ),
    label: str = "operation",
    **kwargs: Any,
) -> tuple[Any, TimeoutReport]:
    """
    Run a callable with a wall-clock bound.

    Returns the result and a report describing what happened.
    Raises OperationTimeout if the bound is exceeded.

    A single-worker executor is used per call. It is shut down
    without waiting on the abandoned thread, because waiting is
    exactly what the timeout exists to avoid.
    """

    started = time.monotonic()

    executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix=(
            f"timeout-{label}"
        ),
    )

    future = executor.submit(
        function,
        *args,
        **kwargs,
    )

    try:
        result = future.result(
            timeout=timeout_seconds
        )
    except FuturesTimeoutError as exc:
        future.cancel()
        executor.shutdown(
            wait=False,
            cancel_futures=True,
        )

        raise OperationTimeout(
            f"'{label}' did not complete within "
            f"{timeout_seconds:g} seconds."
        ) from exc
    except Exception:
        executor.shutdown(
            wait=True,
            cancel_futures=True,
        )
        raise
    else:
        executor.shutdown(wait=True)

    duration_ms = int(
        (time.monotonic() - started) * 1000
    )

    return result, TimeoutReport(
        label=label,
        duration_ms=duration_ms,
        timed_out=False,
    )


def clear_request_state() -> None:
    """
    Reset per-request state after a request completes.

    Exposed so a caller running outside the ASGI middleware —
    a background job, or a test — can still clean up. The
    middleware calls this in a finally block; the function is
    public because "did you remember to reset it" is not a
    failure mode worth having.
    """

    from api.logging_config import (
        request_id_context,
    )

    request_id_context.set("-")


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "OperationTimeout",
    "TimeoutReport",
    "clear_request_state",
    "run_with_timeout",
]