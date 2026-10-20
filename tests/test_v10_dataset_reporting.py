from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_analysis.charts import generate_standard_charts
from data_analysis.reporting import (
    build_dataset_summary,
    build_finding_layers,
    build_report_document,
    generate_sales_report,
    save_report_summary,
)


def staff_dataframe():
    """
    A non-sales dataset: salaries by department, dated.
    """

    return pd.DataFrame(
        {
            "Employee": [
                "A",
                "B",
                "C",
                "D",
                "E",
                "F",
            ],
            "Department": [
                "Engineering",
                "Engineering",
                "Sales",
                "Sales",
                "HR",
                "HR",
            ],
            "Salary": [
                95000,
                110000,
                70000,
                68000,
                55000,
                52000,
            ],
            "Start_Date": [
                "2023-01-10",
                "2023-03-05",
                "2023-02-01",
                "2023-06-15",
                "2023-01-20",
                "2024-01-08",
            ],
        }
    )


def sales_dataframe():
    return pd.DataFrame(
        {
            "Date": [
                "2026-01-01",
                "2026-01-02",
                "2026-02-01",
                "2026-02-02",
            ],
            "Product": [
                "Laptop",
                "Monitor",
                "Laptop",
                "Keyboard",
            ],
            "Region": [
                "Gauteng",
                "Western Cape",
                "Gauteng",
                "KwaZulu-Natal",
            ],
            "Revenue": [
                100000,
                50000,
                75000,
                25000,
            ],
        }
    )


# ========================================================
# THE MEASURE IS NOT ASSUMED TO BE REVENUE
# ========================================================


def test_a_non_sales_dataset_names_its_own_measure():
    """
    'Salary' must be reported as salary, never as revenue.
    The measure noun comes from the column, not from a
    sales-only vocabulary.
    """

    summary = build_dataset_summary(
        staff_dataframe()
    )

    assert summary["_detected_columns"]["revenue"] == (
        "Salary"
    )

    layers = build_finding_layers(
        staff_dataframe(),
        summary,
    )

    facts = " ".join(layers["facts"])

    assert "Total Salary" in facts
    assert "revenue" not in facts.lower()


def test_a_non_sales_dataset_groups_by_its_own_column():
    """
    'Department' is a grouping as readable as 'Product', so
    the report groups by it instead of reporting that nothing
    could be grouped.
    """

    dataframe = staff_dataframe()

    summary = build_dataset_summary(dataframe)

    assert summary["_detected_columns"]["grouped_by"] == (
        "Department"
    )

    assert "revenue_by_product" in summary


def test_a_non_sales_measure_is_never_given_a_currency_symbol():
    """
    A score or an age is not money. Only columns whose name
    is money-shaped get the currency form.
    """

    dataframe = pd.DataFrame(
        {
            "Student": ["a", "b", "c", "d"],
            "Score": [40, 55, 72, 88],
        }
    )

    summary = build_dataset_summary(dataframe)

    assert summary["_detected_columns"]["revenue"] == (
        "Score"
    )

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    findings = " ".join(
        layers["calculated_findings"]
    )

    assert "Score ranges from 40 to 88" in findings
    assert "R40" not in findings


def test_a_money_measure_is_still_given_a_currency_symbol():
    """
    The salary column is monetary, so its figures keep the
    currency form - the guard is on the name, not on whether
    the dataset is sales data.
    """

    dataframe = staff_dataframe()

    summary = build_dataset_summary(dataframe)

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    facts = " ".join(layers["facts"])

    assert "R450,000.00" in facts


# ========================================================
# AGGREGATION MUST MATCH WHAT THE COLUMN MEANS
# ========================================================


def test_an_average_measure_is_not_summed():
    """
    Summing ages describes nothing. A column whose name
    marks it as an average gets averaged instead, and the
    report says 'average' rather than 'total'.
    """

    dataframe = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "name": ["a", "b", "c", "d"],
            "city": ["CPT", "JHB", "CPT", "DBN"],
            "age": [22, 35, 41, 29],
        }
    )

    summary = build_dataset_summary(dataframe)

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    facts = " ".join(layers["facts"])

    assert "Average age across all cities" in facts
    assert "Total age" not in facts

    # The grouped finding describes a level, not a share.
    findings = " ".join(
        layers["calculated_findings"]
    )

    assert "averages" in findings
    assert "accounts for" not in findings


def test_a_single_group_is_not_reported_as_concentration():
    """
    One group is the whole dataset, not a dominant
    category. A one-row table must not claim 100%
    concentration.
    """

    dataframe = pd.DataFrame(
        {
            "Product": ["A"],
            "Revenue": [10],
        }
    )

    summary = build_dataset_summary(dataframe)

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    assert not any(
        "concentrated" in entry
        for entry in layers["interpretations"]
    )

    assert not any(
        "concentration" in entry
        for entry in layers["recommendations"]
    )


def test_a_column_with_no_variation_is_stated_once():
    """
    'Ranges from 100 to 100, averaging 100' restates one
    number three times. It is stated once instead.
    """

    dataframe = pd.DataFrame(
        {
            "Revenue": [100.0],
        }
    )

    summary = build_dataset_summary(dataframe)

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    assert any(
        "is R100.00 for all 1 records" in entry
        for entry in layers["calculated_findings"]
    )


# ========================================================
# CHARTS FOLLOW THE SAME DETECTION
# ========================================================


def test_a_non_sales_dataset_still_gets_charts(tmp_path):
    """
    A report with no charts reads as a broken engine. A
    salary dataset must produce charts of the same shapes,
    named for the columns it actually has.
    """

    charts = generate_standard_charts(
        staff_dataframe(),
        output_directory=tmp_path,
    )

    assert charts

    for path in charts.values():
        assert Path(path).exists()


def test_a_conventional_sales_dataset_keeps_the_v7_chart_set(
    tmp_path,
):
    """
    Generalising the charts must not change what a sales
    report produces - the V7 set is the contract.
    """

    charts = generate_standard_charts(
        sales_dataframe(),
        output_directory=tmp_path,
    )

    assert set(charts) == {
        "revenue_by_product",
        "revenue_by_region",
        "monthly_revenue",
        "revenue_trend",
        "revenue_distribution",
    }


def test_a_dataset_with_no_numeric_column_gets_one_chart(tmp_path):
    """
    A users export has no measure to sum, but its categorical
    columns still have a shape worth plotting.
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

    charts = generate_standard_charts(
        dataframe,
        output_directory=tmp_path,
    )

    assert "category_counts" in charts


# ========================================================
# THE TEXT REPORT NAMES THE COLUMNS IT FOUND
# ========================================================


def test_the_saved_report_names_the_measure_column(
    tmp_path,
):
    """
    A report must read as being about the dataset it was
    built from, so its headings carry the detected column
    names rather than hardcoded sales wording.
    """

    report = generate_sales_report(
        staff_dataframe(),
        report_directory=tmp_path / "reports",
        chart_directory=tmp_path / "charts",
    )

    path = save_report_summary(
        report,
        output_path=tmp_path / "report.txt",
    )

    content = open(
        path,
        encoding="utf-8",
    ).read()

    assert "SALARY STATISTICS" in content
    assert "SALARY BY DEPARTMENT" in content


def test_the_saved_report_keeps_sales_headings_for_sales(
    tmp_path,
):
    """
    The sales wording is not removed - it is the special
    case that the general case must still produce.
    """

    report = generate_sales_report(
        sales_dataframe(),
        report_directory=tmp_path / "reports",
        chart_directory=tmp_path / "charts",
    )

    path = save_report_summary(
        report,
        output_path=tmp_path / "report.txt",
    )

    content = open(
        path,
        encoding="utf-8",
    ).read()

    assert "REVENUE STATISTICS" in content
    assert "REVENUE BY PRODUCT" in content


def test_the_report_document_carries_non_sales_layers(tmp_path):
    """
    The document served over the API is built by the same
    deterministic path, so a non-sales dataset gets the same
    four layers.
    """

    document = build_report_document(
        staff_dataframe(),
        dataset_name="staff.csv",
        report_directory=tmp_path / "reports",
        chart_directory=tmp_path / "charts",
    )

    assert set(document["layers"]) == {
        "facts",
        "calculated_findings",
        "interpretations",
        "recommendations",
    }

    assert document["layers"]["facts"]
    assert document["layers"]["calculated_findings"]
    assert document["charts"]
    assert "Salary" in document["content"]


# ========================================================
# DEGRADED INPUT
# ========================================================


def test_a_text_only_dataset_says_nothing_could_be_derived():
    """
    Every row unique in every column: no measure and no
    repeating category, so the report must say so rather
    than inventing a number.
    """

    dataframe = pd.DataFrame(
        {
            "Name": ["a", "b"],
            "Email": ["a@x.com", "b@x.com"],
        }
    )

    summary = build_dataset_summary(dataframe)

    assert summary["_detected_columns"]["revenue"] is None
    assert summary["general_column"] is None

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    assert any(
        "no numeric column to measure and no "
        "repeating category to count" in entry
        for entry in layers["calculated_findings"]
    )


def test_a_non_numeric_column_named_like_a_measure_is_not_summed():
    """
    A 'Sales' column holding labels - a channel, a status -
    is not a measure. It must not be summed.
    """

    dataframe = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "Name": ["a", "b", "c", "d"],
            "Sales": [
                "Online",
                "Retail",
                "Online",
                "Retail",
            ],
        }
    )

    summary = build_dataset_summary(dataframe)

    assert summary["_detected_columns"]["revenue"] is None
    assert "revenue_statistics" not in summary
