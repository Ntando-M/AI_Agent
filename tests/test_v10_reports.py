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


def test_generate_report_document_layers_and_charts(tmp_path):
    """
    The document carries all four evidence layers and a
    path per chart. The layers are the roadmap's reporting
    requirement, so losing them here would silently reduce
    the report to a summary table.
    """

    import pandas as pd

    from data_analysis.reporting import (
        build_report_document,
    )

    dataframe = pd.DataFrame(
        {
            "Date": ["2026-01-01", "2026-02-01"],
            "Product": ["Laptop", "Keyboard"],
            "Region": ["Gauteng", "Western Cape"],
            "Units": [2, 5],
            "Revenue": [100000, 25000],
        }
    )

    document = build_report_document(
        dataframe,
        dataset_name="sample.csv",
        report_directory=tmp_path / "reports",
        chart_directory=tmp_path / "charts",
    )

    assert document["dataset_name"] == "sample.csv"
    assert set(document["layers"]) == {
        "facts",
        "calculated_findings",
        "interpretations",
        "recommendations",
    }
    assert document["layers"]["facts"]
    assert document["charts"]
    assert "FACTS" in document["content"]


def test_chart_data_url_is_produced_for_a_real_png(tmp_path):
    """
    The client cannot reach chart files: its only route is
    the gateway, whose proxy forwards JSON and text, not
    PNG bytes. So the image has to travel inside the JSON.
    """

    import base64

    from api.app import _chart_data_url

    charts = tmp_path / "charts"
    charts.mkdir()

    # A 1x1 PNG, so the test does not depend on matplotlib.
    png = charts / "chart.png"
    png.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
            "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJ"
            "RU5ErkJggg=="
        )
    )

    data_url = _chart_data_url(
        str(png), str(charts)
    )

    assert data_url is not None
    assert data_url.startswith("data:image/png;base64,")


def test_chart_outside_the_directory_is_refused(tmp_path):
    """
    A stored report is data on disk and could have been
    edited. Its chart paths must not be able to read
    arbitrary files.
    """

    from api.app import _chart_data_url

    charts = tmp_path / "charts"
    charts.mkdir()

    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")

    assert (
        _chart_data_url(str(secret), str(charts))
        is None
    )


def test_delete_removes_the_stored_report(store):
    report_id = store.save("s1", "the report body")

    assert store.delete(report_id) is True

    assert store.get(report_id) is None
    assert store.list_reports() == []


def test_delete_removes_the_file_not_just_the_record(store):
    """
    A report is one JSON file. Deleting must remove it from
    disk, or the next listing still finds it.
    """

    report_id = store.save("s1", "body")

    path = store.directory / f"{report_id}.json"

    assert path.is_file()

    store.delete(report_id)

    assert not path.exists()


def test_deleting_an_unknown_report_is_false(store):
    """
    A caller must be able to tell a real delete from a
    no-op, so deleting an id that never existed reports
    False rather than claiming success.
    """

    assert store.delete("0" * 32) is False


def test_delete_refuses_an_unsafe_id(store):
    """
    The id comes from a URL. A traversal segment must not be
    able to delete anything outside the reports directory.
    """

    victim = store.directory.parent / "victim.json"
    victim.write_text("{}", encoding="utf-8")

    for attempt in (
        "../victim",
        "..\\victim",
        "a/b",
        "",
        "....",
    ):
        assert store.delete(attempt) is False

    assert victim.exists()


def test_delete_leaves_other_reports_alone(store):
    keep = store.save("s1", "keep me")
    remove = store.save("s1", "remove me")

    store.delete(remove)

    remaining = store.list_reports()

    assert len(remaining) == 1
    assert remaining[0]["report_id"] == keep


def test_report_document_records_the_source_dataset(tmp_path):
    """
    A report must name the dataset it was built from. The
    whole point of choosing a source is that the report
    records which one it used, so a reader can tell two
    reports apart.
    """

    import pandas as pd

    from data_analysis.reporting import (
        build_report_document,
    )

    dataframe = pd.DataFrame(
        {
            "Product": ["A", "B"],
            "Revenue": [10, 20],
        }
    )

    document = build_report_document(
        dataframe,
        dataset_name="chosen.csv",
        report_directory=tmp_path / "reports",
        chart_directory=tmp_path / "charts",
    )

    assert document["dataset_name"] == "chosen.csv"
