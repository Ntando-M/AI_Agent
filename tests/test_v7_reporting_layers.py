from __future__ import annotations

import pandas as pd
import pytest

from data_analysis.reporting import (
    build_dataset_summary,
    build_finding_layers,
    generate_sales_report,
    save_report_summary,
)


@pytest.fixture
def sales_dataframe():
    return pd.DataFrame(
        {
            "Date": [
                "2026-01-05",
                "2026-01-12",
                "2026-02-03",
                "2026-02-15",
                "2026-03-01",
                "2026-04-02",
                "2026-04-21",
                "2026-05-10",
            ],
            "Product": [
                "Laptop",
                "Monitor",
                "Laptop",
                "Keyboard",
                "Monitor",
                "Keyboard",
                "Laptop",
                "Monitor",
            ],
            "Region": [
                "Gauteng",
                "Western Cape",
                "Gauteng",
                "KwaZulu-Natal",
                "Gauteng",
                "Gauteng",
                "KwaZulu-Natal",
                "Western Cape",
            ],
            "Revenue": [
                75000,
                24000,
                45000,
                12000,
                18000,
                10000,
                30000,
                40000,
            ],
        }
    )


@pytest.fixture
def layers(sales_dataframe):
    summary = build_dataset_summary(
        sales_dataframe
    )

    return build_finding_layers(
        sales_dataframe,
        summary,
    )


# ========================================================
# LAYER SHAPE
# ========================================================


def test_all_four_layers_present(layers):
    assert set(layers) == {
        "facts",
        "calculated_findings",
        "interpretations",
        "recommendations",
    }


def test_every_layer_is_a_list_of_strings(layers):
    for entries in layers.values():
        assert isinstance(entries, list)

        for entry in entries:
            assert isinstance(entry, str)
            assert entry.strip()


def test_facts_state_observed_values(layers):
    joined = " ".join(layers["facts"])

    assert "8 rows" in joined
    assert "4 columns" in joined


def test_findings_are_arithmetic_not_observations(layers):
    joined = " ".join(
        layers["calculated_findings"]
    )

    assert "%" in joined


# ========================================================
# CLAIM STRENGTH SEPARATION
# ========================================================


def test_interpretations_are_hedged(layers):
    """
    An interpretation states meaning, not fact. Each must
    hedge, so a reader never mistakes it for a measurement.
    """

    assert layers["interpretations"]

    for entry in layers["interpretations"]:
        assert (
            " appears" in entry
            or " does not contain" in entry
        ), entry


def test_facts_contain_no_hedging(layers):
    """
    Facts are what the data contains, so they must not
    hedge or speculate.
    """

    for entry in layers["facts"]:
        assert " appears" not in entry


def test_recommendations_are_actions(layers):
    assert layers["recommendations"]

    for entry in layers["recommendations"]:
        assert entry.split()[0] in {
            "Review",
            "Correlate",
            "Investigate",
            "Consider",
            "Monitor",
        }, entry


# ========================================================
# CONCENTRATION FINDING
# ========================================================


def test_dominant_product_share_is_calculated(layers):
    joined = " ".join(
        layers["calculated_findings"]
    )

    assert "Laptop" in joined
    assert "%" in joined


def test_concentration_triggers_interpretation_and_recommendation(
    layers,
):
    """
    Laptop is over half of revenue in the fixture, so the
    report must escalate from finding to interpretation
    to recommendation.
    """

    assert any(
        "concentrated" in entry
        for entry in layers["interpretations"]
    )

    assert any(
        "Laptop" in entry
        for entry in layers["recommendations"]
    )


def test_even_revenue_yields_no_concentration_claim():
    """
    With no dominant category, the report must not
    manufacture a concentration finding.
    """

    dataframe = pd.DataFrame(
        {
            "Date": [
                "2026-01-01",
                "2026-02-01",
                "2026-01-05",
                "2026-02-05",
                "2026-01-09",
                "2026-02-09",
                "2026-01-13",
                "2026-02-13",
            ],
            "Product": [
                "Laptop",
                "Laptop",
                "Monitor",
                "Monitor",
                "Keyboard",
                "Keyboard",
                "Mouse",
                "Mouse",
            ],
            "Region": [
                "Gauteng",
                "Gauteng",
                "Gauteng",
                "Gauteng",
                "Gauteng",
                "Gauteng",
                "Gauteng",
                "Gauteng",
            ],
            "Revenue": [
                25000,
                25000,
                25000,
                25000,
                25000,
                25000,
                25000,
                25000,
            ],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    result = build_finding_layers(
        dataframe,
        summary,
    )

    assert not any(
        "concentrated" in entry
        for entry in result["interpretations"]
    )

    assert not any(
        "concentration" in entry
        for entry in result["recommendations"]
    )


# ========================================================
# TREND DIRECTION
# ========================================================


def test_decline_is_detected_and_hedged(layers):
    """
    Monthly revenue falls across the fixture, so a
    decline finding and a hedged interpretation must
    both be present.
    """

    findings = " ".join(
        layers["calculated_findings"]
    )

    assert "Revenue moved from" in findings
    assert "-" in findings

    assert any(
        "decline appears" in entry
        for entry in layers["interpretations"]
    )


def test_growth_does_not_claim_a_decline():
    dataframe = pd.DataFrame(
        {
            "Date": [
                "2026-01-01",
                "2026-02-01",
                "2026-01-05",
                "2026-02-05",
            ],
            "Product": [
                "Laptop",
                "Laptop",
                "Monitor",
                "Monitor",
            ],
            "Region": [
                "Gauteng",
                "Gauteng",
                "Gauteng",
                "Gauteng",
            ],
            "Revenue": [
                10000,
                50000,
                10000,
                50000,
            ],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    result = build_finding_layers(
        dataframe,
        summary,
    )

    joined = " ".join(
        result["interpretations"]
    )

    assert "decline" not in joined
    assert "growing" in joined


# ========================================================
# DEGRADED INPUT
# ========================================================


def test_no_revenue_column_still_reports_a_finding():
    """
    A dataset without revenue must degrade honestly rather
    than crash or invent a number.

    'Score' is numeric, so the report describes it instead of
    claiming a revenue column is missing.
    """

    dataframe = pd.DataFrame(
        {
            "Name": ["a", "b"],
            "Score": [1, 2],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    result = build_finding_layers(
        dataframe,
        summary,
    )

    assert result["facts"]

    assert summary["general_column"] == "Score"

    assert any(
        "Score ranges from" in entry
        for entry in result["calculated_findings"]
    )

    assert not any(
        "No revenue column" in entry
        for entry in result["calculated_findings"]
    )


def test_measure_column_with_no_variation_says_so_once():
    """
    A single row, or a column with no variation, must not be
    reported as 'ranges from 100 to 100, averaging 100' -
    that restates one number three times. The value is
    stated once instead.
    """

    dataframe = pd.DataFrame(
        {
            "Revenue": [100.0],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    result = build_finding_layers(
        dataframe,
        summary,
    )

    assert any(
        "is R100.00 for all 1 records" in entry
        for entry in result["calculated_findings"]
    )

    assert not any(
        "ranges from" in entry
        for entry in result["calculated_findings"]
    )


def test_a_users_dataset_reports_real_findings():
    """
    A table with no sales columns at all - the shape of an
    uploaded users export - must still produce arithmetic.

    This is the regression for a real report: sample-users.csv
    produced one fact, an empty chart set and a claim that no
    revenue column existed, which read as 'the engine is
    broken' rather than 'this dataset is not sales data'.
    """

    dataframe = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "first_name": [
                "Jeanette",
                "Giavani",
                "Noell",
                "Willard",
            ],
            "gender": [
                "Female",
                "Male",
                "Female",
                "Male",
            ],
            "registration_date": [
                "2023-10-12",
                "2024-01-05",
                "2023-11-20",
                "2024-02-14",
            ],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    # 'registration_date' contains 'date', so it is found
    # rather than missed by exact-name matching alone.
    assert summary["_detected_columns"]["date"] == (
        "registration_date"
    )

    assert "revenue_by_product" not in summary

    result = build_finding_layers(
        dataframe,
        summary,
    )

    # 'id' is a surrogate key, so it is not reported as a
    # measure - its min and max describe the row numbering.
    assert summary["general_column"] is None

    assert summary["categorical_counts"] == {
        "gender": {"Female": 2, "Male": 2}
    }

    assert summary["records_by_period"] == {
        "2023-10": 1,
        "2023-11": 1,
        "2024-01": 1,
        "2024-02": 1,
    }

    assert any(
        "gender is dominated by Female" in entry
        for entry in result["calculated_findings"]
    )

    assert any(
        "holds the most records" in entry
        for entry in result["calculated_findings"]
    )

    assert not any(
        "ranges from" in entry
        for entry in result["calculated_findings"]
    )


def test_a_dataset_with_nothing_to_calculate_says_so():
    """
    Text columns only, and every row distinct in each: the
    report must say it could derive nothing, rather than
    silently returning an empty layer.
    """

    dataframe = pd.DataFrame(
        {
            "Name": ["a", "b"],
            "Email": ["a@x.com", "b@x.com"],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    result = build_finding_layers(
        dataframe,
        summary,
    )

    assert any(
        "no numeric column to measure and no "
        "repeating category to count" in entry
        for entry in result["calculated_findings"]
    )


def test_single_month_yields_no_trend_claim():
    dataframe = pd.DataFrame(
        {
            "Date": ["2026-01-01"],
            "Product": ["Laptop"],
            "Region": ["Gauteng"],
            "Revenue": [10000],
        }
    )

    summary = build_dataset_summary(
        dataframe
    )

    result = build_finding_layers(
        dataframe,
        summary,
    )

    findings = " ".join(
        result["calculated_findings"]
    )

    assert "Revenue moved from" not in findings


# ========================================================
# REPORT INTEGRATION
# ========================================================


def test_generate_sales_report_includes_layers(
    sales_dataframe,
    tmp_path,
):
    report = generate_sales_report(
        sales_dataframe,
        report_directory=tmp_path,
        chart_directory=tmp_path / "charts",
    )

    assert set(report["layers"]) == {
        "facts",
        "calculated_findings",
        "interpretations",
        "recommendations",
    }


def test_saved_report_contains_all_four_headings(
    sales_dataframe,
    tmp_path,
):
    report = generate_sales_report(
        sales_dataframe,
        report_directory=tmp_path,
        chart_directory=tmp_path / "charts",
    )

    path = save_report_summary(
        report,
        output_path=tmp_path / "report.txt",
    )

    text = open(
        path,
        encoding="utf-8",
    ).read()

    for heading in (
        "FACTS",
        "CALCULATED FINDINGS",
        "INTERPRETATIONS",
        "RECOMMENDATIONS",
    ):
        assert heading in text


def test_saved_report_still_has_dataset_detail(
    sales_dataframe,
    tmp_path,
):
    report = generate_sales_report(
        sales_dataframe,
        report_directory=tmp_path,
        chart_directory=tmp_path / "charts",
    )

    path = save_report_summary(
        report,
        output_path=tmp_path / "report.txt",
    )

    text = open(
        path,
        encoding="utf-8",
    ).read()

    assert "Rows: 8" in text
    assert "Columns: 4" in text


def test_report_without_layers_still_renders(
    sales_dataframe,
    tmp_path,
):
    """
    A report built before the layers existed must still
    save, marking each layer as underivable.
    """

    report = generate_sales_report(
        sales_dataframe,
        report_directory=tmp_path,
        chart_directory=tmp_path / "charts",
    )

    del report["layers"]

    path = save_report_summary(
        report,
        output_path=tmp_path / "report.txt",
    )

    text = open(
        path,
        encoding="utf-8",
    ).read()

    assert "None could be derived" in text