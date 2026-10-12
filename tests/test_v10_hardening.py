from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import pytest

from api.logging_config import (
    JsonFormatter,
    configure_logging,
    get_logger,
    log_event,
    new_request_id,
    request_id_context,
    set_request_id,
)
from api.timeouts import (
    OperationTimeout,
    run_with_timeout,
)
from api.uploads import (
    DATASET_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    UploadPolicy,
    UploadRejected,
    sanitise_filename,
)


# ====================================================
# UPLOAD SIZE AND TYPE LIMITS
# ====================================================


def test_dataset_policy_rejects_executable():
    policy = UploadPolicy.for_datasets()

    with pytest.raises(
        UploadRejected,
        match="Unsupported dataset type",
    ):
        policy.validate_extension("malware.exe")


def test_document_policy_rejects_executable():
    """
    The endpoint this guards writes into a directory the RAG
    loader later reads, so an arbitrary extension is the hole
    being closed.
    """

    policy = UploadPolicy.for_documents()

    with pytest.raises(UploadRejected):
        policy.validate_extension("payload.sh")


def test_policy_accepts_every_declared_extension():
    policy = UploadPolicy.for_documents()

    for extension in DOCUMENT_EXTENSIONS:
        assert policy.validate_extension(
            f"file{extension}"
        ) == extension


def test_extension_check_is_case_insensitive():
    """
    A client sending Report.PDF should not be rejected for
    capitalisation. The extension is normalised before the
    membership test.
    """

    policy = UploadPolicy.for_documents()

    assert policy.validate_extension(
        "Report.PDF"
    ) == ".pdf"


def test_missing_extension_is_rejected():
    policy = UploadPolicy.for_datasets()

    with pytest.raises(
        UploadRejected,
        match="no extension",
    ):
        policy.validate_extension("datafile")


def test_missing_filename_is_rejected():
    policy = UploadPolicy.for_datasets()

    with pytest.raises(
        UploadRejected,
        match="No filename",
    ):
        policy.validate_extension(None)


def test_oversized_upload_is_rejected(tmp_path):
    """
    The limit must be enforced, not merely documented.
    """

    policy = UploadPolicy(
        max_bytes=100,
        allowed_extensions=DATASET_EXTENSIONS,
        label="dataset",
    )

    source = io.BytesIO(b"x" * 500)
    destination = tmp_path / "big.csv"

    with pytest.raises(
        UploadRejected,
        match="maximum upload size",
    ):
        policy.copy_stream_to(
            source, destination
        )


def test_oversized_upload_leaves_nothing_on_disk(tmp_path):
    """
    The partial file must be removed. Leaving it would mean an
    attacker can still fill the disk, just in truncated files,
    and the staging directory would accumulate garbage.
    """

    policy = UploadPolicy(
        max_bytes=100,
        allowed_extensions=DATASET_EXTENSIONS,
        label="dataset",
    )

    destination = tmp_path / "big.csv"

    with pytest.raises(UploadRejected):
        policy.copy_stream_to(
            io.BytesIO(b"x" * 5000), destination
        )

    assert not destination.exists()


def test_upload_within_limit_is_written(tmp_path):
    policy = UploadPolicy(
        max_bytes=1000,
        allowed_extensions=DATASET_EXTENSIONS,
        label="dataset",
    )

    destination = tmp_path / "ok.csv"
    payload = b"Date,Revenue\n2026-01-05,75000\n"

    written = policy.copy_stream_to(
        io.BytesIO(payload), destination
    )

    assert written == len(payload)
    assert destination.read_bytes() == payload


def test_upload_exactly_at_limit_is_accepted(tmp_path):
    """
    The limit is inclusive. A file of exactly max_bytes is
    allowed, one byte more is not, because a strict inequality
    would reject a file that fits.
    """

    policy = UploadPolicy(
        max_bytes=10,
        allowed_extensions=DATASET_EXTENSIONS,
        label="dataset",
    )

    destination = tmp_path / "exact.csv"

    written = policy.copy_stream_to(
        io.BytesIO(b"0123456789"), destination
    )

    assert written == 10

    with pytest.raises(UploadRejected):
        policy.copy_stream_to(
            io.BytesIO(b"0123456789A"),
            tmp_path / "over.csv",
        )


def test_copy_validates_extension_when_asked(tmp_path):
    """
    Passing a filename makes the copy check the type itself,
    so a caller cannot skip validation by using the streaming
    path.
    """

    policy = UploadPolicy.for_datasets()

    with pytest.raises(UploadRejected):
        policy.copy_stream_to(
            io.BytesIO(b"MZ"),
            tmp_path / "bad.exe",
            filename="bad.exe",
        )


# ====================================================
# FILENAME SANITISATION
# ====================================================


@pytest.mark.parametrize(
    "supplied, expected",
    [
        ("../../.env", ".env"),
        ("..\\..\\windows\\system32\\cfg", "cfg"),
        ("/etc/passwd", "passwd"),
        ("report.pdf", "report.pdf"),
        ("", "fallback.csv"),
        (None, "fallback.csv"),
        ("..", "fallback.csv"),
        (".", "fallback.csv"),
    ],
)
def test_sanitise_filename_strips_paths(
    supplied,
    expected,
):
    """
    A client controls this string completely, so only the final
    path component survives. Traversal attempts become bare
    filenames that then fail the extension check rather than
    escaping the upload directory.
    """

    assert (
        sanitise_filename(supplied, "fallback.csv")
        == expected
    )


def test_sanitise_filename_removes_shell_metacharacters():
    result = sanitise_filename(
        "sales; rm -rf.csv", "fallback.csv"
    )

    assert ";" not in result
    assert result.endswith(".csv")


# ====================================================
# TIMEOUTS
# ====================================================


def test_fast_operation_returns_result():
    result, report = run_with_timeout(
        lambda value: value * 2,
        21,
        timeout_seconds=5,
        label="double",
    )

    assert result == 42
    assert report.timed_out is False
    assert report.duration_ms >= 0


def test_slow_operation_raises_timeout():
    import time

    with pytest.raises(
        OperationTimeout,
        match="did not complete",
    ):
        run_with_timeout(
            time.sleep,
            5,
            timeout_seconds=0.2,
            label="sleeper",
        )


def test_timeout_message_names_the_operation():
    """
    The label reaches the operator, so a 504 says which stage
    was slow instead of leaving them to guess.
    """

    import time

    with pytest.raises(
        OperationTimeout,
        match="chat.orchestrator",
    ):
        run_with_timeout(
            time.sleep,
            5,
            timeout_seconds=0.2,
            label="chat.orchestrator",
        )


def test_exception_propagates_unchanged():
    """
    A genuine failure must not be reported as a timeout. The
    endpoint maps these to different status codes.
    """

    def explode():
        raise ValueError("provider refused")

    with pytest.raises(
        ValueError,
        match="provider refused",
    ):
        run_with_timeout(explode)


# ====================================================
# STRUCTURED LOGGING
# ====================================================


def make_record(**context):
    """
    A bare record, used where the point is the formatter and
    not the event payload.
    """

    return logging.LogRecord(
        name="ai_data_analyst.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )


def render(**fields) -> dict:
    """
    Emit one structured event through the real code path and
    parse the resulting line back to a dict.

    Formatting a record built by hand would not exercise
    log_event, so the record is captured by attaching the
    package's own handler and letting the call write it.
    """

    logger = get_logger("test")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        log_event(
            logger,
            logging.INFO,
            "unit_test",
            **fields,
        )
    finally:
        logger.removeHandler(handler)

    return json.loads(stream.getvalue().strip())


def test_log_line_is_valid_json():
    payload = render(duration_ms=42)

    assert payload["level"] == "INFO"
    assert payload["logger"].startswith(
        "ai_data_analyst"
    )
    assert payload["duration_ms"] == 42
    assert payload["timestamp"]


def test_log_line_carries_event_name():
    payload = render()

    assert payload["event"] == "unit_test"


def test_request_id_appears_on_every_line():
    request_id = set_request_id("abc123")

    assert request_id_context.get() == "abc123"

    payload = render()

    assert payload["request_id"] == "abc123"


def test_generated_request_id_when_absent():
    request_id = set_request_id(None)

    assert request_id
    assert request_id != "-"


def test_request_id_is_sanitised():
    """
    The id is client-controlled and written verbatim to the
    log, so newlines and log-forging characters must not
    survive.
    """

    request_id = set_request_id(
        "abc\n{\"level\":\"INFO\"}"
    )

    assert "\n" not in request_id
    assert "{" not in request_id


def test_request_id_length_is_bounded():
    request_id = set_request_id("a" * 500)

    assert len(request_id) <= 64


def test_answer_is_never_logged():
    """
    The LLM answer may carry figures from the customer
    dataset. A log file is an easier place to leak one than
    the database it came from.
    """

    payload = render(
        answer="Total revenue was R274,000",
        api_key="super-secret",
    )

    assert payload["answer"] == "[redacted]"
    assert payload["api_key"] == "[redacted]"
    assert "274,000" not in json.dumps(payload)


def test_nested_secrets_are_redacted():
    payload = render(
        request={"authorization": "Bearer abc"},
    )

    assert (
        payload["request"]["authorization"]
        == "[redacted]"
    )


def test_unserialisable_value_does_not_break_the_line():
    class Exotic:
        def __repr__(self):
            return "<exotic>"

    payload = render(thing=Exotic())

    assert payload["thing"] == "<exotic>"


def test_configure_logging_is_idempotent():
    """
    Both a host application and this module may configure
    logging. Configuring twice must not double every line.
    """

    logger = configure_logging("INFO")
    first = len(logger.handlers)

    configure_logging("INFO")
    second = len(logger.handlers)

    assert first == second


def test_configure_logging_respects_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    logger = configure_logging()

    assert logger.level == logging.WARNING