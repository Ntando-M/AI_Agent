from __future__ import annotations

"""
End-to-end checks for the V10 hardening.

These exist because the unit tests cannot prove the wiring: a
limit that is enforced in a helper but never called by the
endpoint passes every unit test and still accepts an unbounded
upload. Each test below drives the real ASGI app through
TestClient.
"""

import io
import json
import logging

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.logging_config import (
    JsonFormatter,
    get_logger,
)
from api.settings import Settings
from memory.sqlite_store import SQLiteConversationStore
from orchestrator.llm_gateway import LLMGateway
from orchestrator.orchestrator import Orchestrator


API_KEY = "test-key-value-000000000000"

AUTH = {"X-API-Key": API_KEY}


@pytest.fixture
def hardening_settings(tmp_path):
    """
    Settings with the limits turned down so the rejection
    paths are reachable without writing megabytes to disk.
    """

    return Settings(
        api_key=API_KEY,
        chat_database_url=(
            f"sqlite:///{tmp_path / 'chat.db'}"
        ),
        dataset_upload_directory=str(
            tmp_path / "uploads"
        ),
        documents_directory=str(
            tmp_path / "documents"
        ),
        reports_directory=str(tmp_path / "reports"),
        max_dataset_upload_bytes=512,
        max_document_upload_bytes=512,
        analysis_timeout_seconds=30.0,
    )


@pytest.fixture
def client(hardening_settings, tmp_path):
    """
    A client with a stub gateway.

    No network call is made: the stub returns a fixed
    structured response, so these tests exercise transport
    behaviour only.
    """

    from models.response_models import (
        AnalysisResponse,
    )

    stub_response = AnalysisResponse(
        answer="Stubbed answer.",
        analysis_type="general",
        datasets_used=[],
        calculations_performed=[],
        key_findings=[],
        sources=[],
        confidence=0.5,
    )

    class StubGateway:
        def raw(self, messages):
            return '{"steps": []}'

        def structured(self, messages):
            return stub_response.model_dump()

    orchestrator = Orchestrator(
        gateway=StubGateway(),
        dataset_path=None,
    )

    app = create_app(
        settings=hardening_settings,
        orchestrator=orchestrator,
    )

    return TestClient(app, raise_server_exceptions=False)


# ====================================================
# UPLOAD LIMITS THROUGH THE REAL ENDPOINTS
# ====================================================


def test_oversized_dataset_is_rejected_413(client):
    """
    The endpoint, not just the helper, must refuse. This is
    the test that would have caught the original unbounded
    shutil.copyfileobj.
    """

    payload = b"Date,Revenue\n" + (b"2026-01-05,1\n" * 500)

    assert len(payload) > 512

    response = client.post(
        "/datasets",
        headers=AUTH,
        files={
            "file": (
                "big.csv",
                io.BytesIO(payload),
                "text/csv",
            )
        },
    )

    assert response.status_code == 413
    assert "maximum upload size" in (
        response.json()["detail"]
    )


def test_oversized_document_is_rejected_413(client):
    payload = b"x" * 2000

    response = client.post(
        "/documents",
        headers=AUTH,
        files={
            "file": (
                "big.txt",
                io.BytesIO(payload),
                "text/plain",
            )
        },
    )

    assert response.status_code == 413


def test_dataset_within_limit_is_accepted(client):
    frame = pd.DataFrame(
        {
            "Date": ["2026-01-05"],
            "Revenue": [75000],
        }
    )

    payload = frame.to_csv(index=False).encode()

    assert len(payload) <= 512

    response = client.post(
        "/datasets",
        headers=AUTH,
        files={
            "file": (
                "small.csv",
                io.BytesIO(payload),
                "text/csv",
            )
        },
    )

    assert response.status_code == 201


def test_executable_dataset_extension_is_rejected(client):
    response = client.post(
        "/datasets",
        headers=AUTH,
        files={
            "file": (
                "payload.exe",
                io.BytesIO(b"MZ"),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_path_traversal_filename_is_neutralised(client):
    """
    A traversal filename must not be written outside the
    upload directory. The extension check runs on the
    sanitised basename, so this file is judged on '.csv' and
    stored under a bare name.
    """

    frame = pd.DataFrame(
        {"Date": ["2026-01-05"], "Revenue": [1]}
    )

    response = client.post(
        "/datasets",
        headers=AUTH,
        files={
            "file": (
                "../../escape.csv",
                io.BytesIO(
                    frame.to_csv(index=False).encode()
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert ".." not in payload["name"]
    assert "/" not in payload["name"]
    assert "\\" not in payload["name"]


def test_upload_without_auth_is_still_401(client):
    """
    The new limits must not become a way to probe the API
    unauthenticated.
    """

    response = client.post(
        "/datasets",
        files={
            "file": (
                "x.csv",
                io.BytesIO(b"a,b\n1,2\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 401


# ====================================================
# CORRELATION IDS AND REQUEST LOGGING
# ====================================================


def test_response_carries_a_request_id(client):
    response = client.get("/health")

    assert response.headers.get("X-Request-ID")


def test_client_supplied_request_id_is_echoed(client):
    """
    An upstream service that already started a trace must be
    able to have it continued here.
    """

    response = client.get(
        "/health",
        headers={"X-Request-ID": "trace-abc-123"},
    )

    assert (
        response.headers["X-Request-ID"]
        == "trace-abc-123"
    )


def test_request_id_is_sanitised_in_response(client):
    """
    A forged header must not come back with newlines in it.
    """

    response = client.get(
        "/health",
        headers={
            "X-Request-ID": "abc\ndef"
        },
    )

    echoed = response.headers["X-Request-ID"]

    assert "\n" not in echoed


def capture_events(client, call):
    """
    Run a request and return the structured events it emitted.

    The package logger sets propagate=False so a host
    application's root handler cannot duplicate every line.
    That also means pytest's caplog sees nothing, so a handler
    is attached to the package logger directly. Reading the
    real records is the point: asserting on formatted text
    would pass even if the fields were wrong.
    """

    from api.logging_config import get_logger

    events = []

    class Capture(logging.Handler):
        def emit(self, record):
            context = getattr(record, "context", None)

            if isinstance(context, dict):
                events.append(context)

    logger = get_logger()
    handler = Capture()
    logger.addHandler(handler)

    try:
        call()
    finally:
        logger.removeHandler(handler)

    return events


def test_request_completion_is_logged(client):
    events = capture_events(
        client,
        lambda: client.get(
            "/health",
            headers={"X-Request-ID": "logged-1"},
        ),
    )

    completed = [
        event
        for event in events
        if event["event"] == "request_completed"
    ]

    assert completed

    context = completed[0]

    assert context["method"] == "GET"
    assert context["path"] == "/health"
    assert context["status_code"] == 200
    assert isinstance(context["duration_ms"], int)


def test_log_line_carries_the_correlation_id(client):
    """
    The point of a correlation id is that every line for one
    request shares it, so it has to reach the record the
    formatter reads.

    The id is supplied as a header because the middleware
    binds one per request, overwriting anything set
    beforehand. Presetting the context variable here would
    test nothing.
    """

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger = get_logger("api.request")
    logger.addHandler(handler)

    try:
        client.get(
            "/health",
            headers={"X-Request-ID": "logged-1"},
        )
    finally:
        logger.removeHandler(handler)

    lines = [
        json.loads(line)
        for line in stream.getvalue().strip().splitlines()
        if line
    ]

    assert lines
    assert all(
        line["request_id"] == "logged-1"
        for line in lines
    )


def test_rejected_upload_is_logged(client):
    events = capture_events(
        client,
        lambda: client.post(
            "/datasets",
            headers=AUTH,
            files={
                "file": (
                    "payload.exe",
                    io.BytesIO(b"MZ"),
                    "application/octet-stream",
                )
            },
        ),
    )

    assert any(
        event["event"] == "upload_rejected"
        for event in events
    )


def test_api_key_never_appears_in_logs(client):
    """
    The key authenticates every request, so it must never be
    written to a log that ships anywhere.
    """

    from api.logging_config import get_logger

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger = get_logger()
    logger.addHandler(handler)

    try:
        client.post(
            "/chat",
            headers=AUTH,
            json={
                "session_id": "s1",
                "message": "What is total revenue?",
            },
        )
    finally:
        logger.removeHandler(handler)

    assert API_KEY not in stream.getvalue()


# ====================================================
# TIMEOUT BEHAVIOUR THROUGH THE ENDPOINT
# ====================================================


def test_timeout_returns_504(
    hardening_settings,
    tmp_path,
):
    """
    A hung orchestrator must produce 504, not a hung request
    and not a misleading 500.
    """

    import time

    class HangingGateway:
        def raw(self, messages):
            time.sleep(30)
            return "{}"

        def structured(self, messages):
            time.sleep(30)
            return {}

    settings = Settings(
        api_key=API_KEY,
        chat_database_url=(
            f"sqlite:///{tmp_path / 'chat.db'}"
        ),
        dataset_upload_directory=str(
            tmp_path / "uploads"
        ),
        documents_directory=str(tmp_path / "documents"),
        reports_directory=str(tmp_path / "reports"),
        # Short enough to fail inside the test's patience.
        analysis_timeout_seconds=0.5,
    )

    orchestrator = Orchestrator(
        gateway=HangingGateway(),
        dataset_path=None,
    )

    app = create_app(
        settings=settings,
        orchestrator=orchestrator,
    )

    client = TestClient(
        app, raise_server_exceptions=False
    )

    response = client.post(
        "/chat",
        headers=AUTH,
        json={
            "session_id": "s1",
            "message": "What is total revenue?",
        },
    )

    assert response.status_code == 504
    assert "did not complete" in (
        response.json()["detail"]
    )