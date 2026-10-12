from __future__ import annotations

import json

import pytest

from api.registry import ReportStore


@pytest.fixture
def store(tmp_path):
    return ReportStore(
        directory=tmp_path / "reports"
    )


def test_saved_report_is_written_to_disk(store):
    """
    A report must outlive the process. The in-memory
    dictionary this replaced lost every report on restart,
    which is why the endpoint could only ever answer 404.
    """

    report_id = store.save(
        "s1",
        "the report body",
        dataset_name="sample_sales.xlsx",
        summary={"rows": 8},
        layers={"facts": ["A fact."]},
        charts={
            "revenue_trend": (
                "outputs/charts/revenue_trend.png"
            )
        },
    )

    path = store.directory / f"{report_id}.json"

    assert path.is_file()

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert payload["report_id"] == report_id
    assert payload["session_id"] == "s1"
    assert payload["dataset_name"] == "sample_sales.xlsx"
    assert payload["layers"] == {"facts": ["A fact."]}
    assert payload["created_at"]


def test_a_second_store_instance_reads_the_same_report(
    tmp_path,
):
    """
    Two instances over one directory must agree, which is
    what "persisted" means.
    """

    first = ReportStore(directory=tmp_path / "reports")

    report_id = first.save("s1", "body")

    second = ReportStore(directory=tmp_path / "reports")

    assert second.get(report_id)["content"] == "body"


def test_reports_are_listed_newest_first(store):
    store.save("s1", "older")
    store.save("s1", "newer")

    listed = store.list_reports()

    assert len(listed) == 2
    assert listed[0]["content"] == "newer"


def test_report_id_cannot_escape_the_directory(store):
    """
    The id arrives from the URL. Building a path from it
    without validating is a traversal bug.
    """

    for attempt in (
        "../../.env",
        "..\\..\\windows",
        "a/b",
        "",
        "....",
    ):
        assert store.get(attempt) is None


def test_a_default_store_does_not_share_state(tmp_path):
    """
    Two stores over different directories must not see each
    other's reports.

    This is the regression for a real bug: the in-memory
    store was isolated per instance, so tests called
    ReportStore() bare. Once the store became
    directory-backed, those bare calls shared the production
    reports/ directory and leaked state between tests.
    """

    first = ReportStore(directory=tmp_path / "one")
    second = ReportStore(directory=tmp_path / "two")

    first.save("s1", "only in one")

    assert first.list_reports()
    assert second.list_reports() == []
