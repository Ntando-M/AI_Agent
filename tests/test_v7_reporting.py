from __future__ import annotations

import pandas as pd

from data_analysis.reporting import (
    build_dataset_summary,
    generate_sales_report,
    save_report_summary,
)


def create_sales_dataframe():
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
            "Units": [
                2,
                3,
                1,
                5,
            ],
            "Revenue": [
                100000,
                50000,
                75000,
                25000,
            ],
        }
    )


def test_build_dataset_summary():
    dataframe = (
        create_sales_dataframe()
    )

    result = build_dataset_summary(
        dataframe
    )

    assert result["rows"] == 4
    assert result["columns"] == 5

    statistics = result[
        "revenue_statistics"
    ]

    assert statistics["count"] == 4
    assert statistics["mean"] == 62500
    assert statistics["min"] == 25000
    assert statistics["max"] == 100000

    products = result[
        "revenue_by_product"
    ]

    assert products[0] == {
        "Product": "Laptop",
        "Revenue": 175000,
    }


def test_generate_sales_report(
    tmp_path,
):
    dataframe = (
        create_sales_dataframe()
    )

    chart_directory = (
        tmp_path / "charts"
    )

    report_directory = (
        tmp_path / "reports"
    )

    result = generate_sales_report(
        dataframe,
        report_directory=report_directory,
        chart_directory=chart_directory,
    )

    assert "summary" in result
    assert "charts" in result

    assert len(
        result["charts"]
    ) == 4

    for chart_path in result[
        "charts"
    ].values():
        assert (
            chart_path
        )

        assert (
            __import__(
                "pathlib"
            ).Path(
                chart_path
            ).exists()
        )


def test_save_report_summary(
    tmp_path,
):
    dataframe = (
        create_sales_dataframe()
    )

    report = generate_sales_report(
        dataframe,
        report_directory=tmp_path / "reports",
        chart_directory=tmp_path / "charts",
    )

    output_path = (
        tmp_path
        / "reports"
        / "sales_report.txt"
    )

    result = save_report_summary(
        report,
        output_path=output_path,
    )

    assert result == str(
        output_path
    )

    assert output_path.exists()

    content = (
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        "AI DATA ANALYST - V7 SALES REPORT"
        in content
    )

    assert (
        "REVENUE STATISTICS"
        in content
    )

    assert (
        "REVENUE BY PRODUCT"
        in content
    )

    assert (
        "REVENUE BY REGION"
        in content
    )