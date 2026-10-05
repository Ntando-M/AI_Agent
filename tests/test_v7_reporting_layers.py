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

    assert any(
        "No revenue column" in entry
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