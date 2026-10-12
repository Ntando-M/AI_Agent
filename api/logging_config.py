"""Structured logging for the service.

V10 asks for observability. The gap this fills is not "print
something when it breaks" but traceability: a single request can
call a cloud LLM, run nine deterministic tools and write a chart,
and when a user reports a wrong answer there is currently no way
to reconstruct which of those steps actually ran.

Two decisions shape this module.

* Logs are JSON lines, not prose. A line has to be greppable and
  machine-readable; a formatted sentence is neither once it
  crosses a process boundary.

* The LLM answer is never logged. A logged request carries the
  user's question and the tools that ran, which is enough to
  debug. The answer may contain figures derived from a customer
  dataset, and a log file is a much easier place to leak one
  than the database it came from.

Correlation ids come from the client when supplied, so a trace
survives across services. Where the client sends none, one is
generated. Either way the id appears on every line for that
request, which is what makes the lines joinable.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from logging import LoggerAdapter


# The correlation id for the request currently being handled.
# A ContextVar rather than a module global because the API may
# serve requests concurrently; a plain global would let one
# request's id leak into another's log lines.
request_id_context: ContextVar[str] = ContextVar(
    "request_id",
    default="-",
)


# Fields that must never reach the log, whatever a caller
# passes. Callers build log payloads from request data, so a
# caller mistake should not become a written secret.
REDACTED_KEYS = frozenset(
    {
        "api_key",
        "x-api-key",
        "authorization",
        "password",
        "secret",
        "token",
        "answer",
        "page_content",
        "file_content",
    }
)

REDACTED = "[redacted]"

LOGGER_NAME = "ai_data_analyst"


class _TaggedStreamHandler(logging.StreamHandler):
    """
    A handler that can be recognised as ours.

    Idempotent configuration needs a way to tell our handler
    from one a host application added. A subclass makes that
    check an isinstance test rather than a setattr on a
    built-in, which static analysis rightly objects to.
    """

    _ai_data_analyst = True


class JsonFormatter(logging.Formatter):
    """
    Render each record as one JSON object on one line.

    A record that cannot be serialised must still produce a
    usable line, so unknown objects fall back to their string
    form instead of raising inside the logging call and losing
    the record entirely.
    """

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(
                record,
                "request_id",
                request_id_context.get(),
            ),
        }

        context = getattr(record, "context", None)

        if isinstance(context, dict):
            for key, value in context.items():
                payload[key] = _sanitise(key, value)

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            default=str,
            ensure_ascii=False,
        )


def _sanitise(
    key: str,
    value: Any,
) -> Any:
    """
    Drop a field entirely when its name is sensitive.

    Replacing the value with a marker would still record that a
    field was present, which for a key whose only purpose is
    absence is itself information. Dropping is simpler to
    reason about when reading a log by hand.
    """

    if key.lower() in REDACTED_KEYS:
        return REDACTED

    if isinstance(value, dict):
        return {
            inner_key: _sanitise(inner_key, inner_value)
            for inner_key, inner_value in value.items()
        }

    return value


def new_request_id() -> str:
    """
    Mint a correlation id for a request that did not supply one.
    """

    return uuid.uuid4().hex[:12]


def set_request_id(request_id: str | None) -> str:
    """
    Bind the correlation id for the current context.

    A client-supplied id is truncated to a bounded length
    because it arrives untrusted and is written verbatim to
    every log line; an unbounded client string is a log
    injection vector.
    """

    if request_id:
        cleaned = "".join(
            character
            for character in str(request_id)
            if character.isalnum() or character in "-_"
        )[:64]
        resolved = cleaned or new_request_id()
    else:
        resolved = new_request_id()

    request_id_context.set(resolved)

    return resolved


def get_logger(
    name: str | None = None,
) -> logging.Logger:
    """
    Return a namespaced logger.

    One logger name per component keeps filtering possible:
    set AI_DATA_ANALYST_LOG_LEVEL=DEBUG to raise verbosity
    without touching root logging configuration.
    """

    if name:
        return logging.getLogger(
            f"{LOGGER_NAME}.{name}"
        )

    return logging.getLogger(LOGGER_NAME)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """
    Emit one structured event.

    `event` is the stable machine-readable name to filter on.
    The keyword fields are the variable parts. Keeping the two
    separate is what allows an alert on "llm_call_failed"
    without regexing a sentence.
    """

    logger.log(
        level,
        event,
        extra={
            "context": {
                "event": event,
                **fields,
            }
        },
    )


def configure_logging(
    level: str | None = None,
    stream: Any = None,
) -> logging.Logger:
    """
    Attach a JSON handler to the package logger.

    Idempotent: calling twice does not double every line, which
    matters because the API and a test app may both configure.
    """

    import os

    resolved = (
        level
        or os.getenv("LOG_LEVEL", "INFO")
    ).strip().upper()

    logger = logging.getLogger(LOGGER_NAME)

    logger.setLevel(resolved)

    # The API is a library inside the process. Without this,
    # a root handler added by a host app would duplicate every
    # line alongside ours.
    logger.propagate = False

    already_configured = any(
        getattr(handler, "_ai_data_analyst", False)
        for handler in logger.handlers
    )

    if not already_configured:
        handler = _TaggedStreamHandler(
            stream or sys.stderr
        )
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger


def get_logger_with_context(
    name: str | None = None,
    **fields: Any,
) -> logging.LoggerAdapter:
    """
    Return a logger that stamps the current request id on
    every record, so call sites do not each have to remember
    to pass it.
    """

    logger = get_logger(name)

    return LoggerAdapter(
        logger,
        {"request_id": request_id_context.get()},
    )