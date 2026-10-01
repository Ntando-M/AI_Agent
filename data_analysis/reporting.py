from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from data_analysis.analyzer import (
    calculate_statistics,
    group_by_column,
    inspect_dataset,
)
from data_analysis.charts import (
    generate_standard_sales_charts,
)


DEFAULT_REPORT_DIRECTORY = Path(
    "reports"
)


def build_dataset_summary(
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """
    Build a deterministic analytical summary
    of the supplied dataset.
    """

    inspection = inspect_dataset(
        dataframe
    )

    summary: dict[str, Any] = {
        "rows": inspection["rows"],
        "columns": inspection["columns"],
        "column_names": inspection[
            "column_names"
        ],
        "missing_values": inspection[
            "missing_values"
        ],
    }

    if "Revenue" in dataframe.columns:
        revenue_statistics = (
            calculate_statistics(
                dataframe,
                "Revenue",
            )
        )

        summary["revenue_statistics"] = (
            revenue_statistics
        )

    if {
        "Product",
        "Revenue",
    }.issubset(dataframe.columns):
        product_revenue = group_by_column(
            dataframe,
            "Product",
            "Revenue",
            "sum",
        )

        product_revenue = (
            product_revenue
            .sort_values(
                "Revenue",
                ascending=False,
            )
        )

        summary["revenue_by_product"] = (
            product_revenue.to_dict(
                orient="records"
            )
        )

    if {
        "Region",
        "Revenue",
    }.issubset(dataframe.columns):
        region_revenue = group_by_column(
            dataframe,
            "Region",
            "Revenue",
            "sum",
        )

        region_revenue = (
            region_revenue
            .sort_values(
                "Revenue",
                ascending=False,
            )
        )

        summary["revenue_by_region"] = (
            region_revenue.to_dict(
                orient="records"
            )
        )

    return summary


def generate_sales_report(
    dataframe: pd.DataFrame,
    report_directory: str | Path = (
        DEFAULT_REPORT_DIRECTORY
    ),
    chart_directory: str | Path = "outputs/charts",
) -> dict[str, Any]:
    """
    Generate a complete deterministic V7
    analytical report.

    Returns:
        A dictionary containing the summary
        and generated chart paths.
    """

    report_directory = Path(
        report_directory
    )

    chart_directory = Path(
        chart_directory
    )

    report_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = build_dataset_summary(
        dataframe
    )

    charts = generate_standard_sales_charts(
        dataframe,
        output_directory=chart_directory,
    )

    return {
        "summary": summary,
        "charts": charts,
    }


def save_report_summary(
    report: dict[str, Any],
    output_path: str | Path = (
        DEFAULT_REPORT_DIRECTORY
        / "sales_report.txt"
    ),
) -> str:
    """
    Save a human-readable text representation
    of the analytical report.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = report["summary"]
    charts = report["charts"]

    lines: list[str] = []

    lines.append(
        "AI DATA ANALYST - V7 SALES REPORT"
    )
    lines.append(
        "=" * 40
    )
    lines.append("")

    lines.append(
        f"Rows: {summary['rows']}"
    )
    lines.append(
        f"Columns: {summary['columns']}"
    )
    lines.append("")

    if "revenue_statistics" in summary:
        statistics = summary[
            "revenue_statistics"
        ]

        lines.append(
            "REVENUE STATISTICS"
        )
        lines.append(
            "-" * 40
        )

        for key, value in statistics.items():
            lines.append(
                f"{key}: {value}"
            )

        lines.append("")

    if "revenue_by_product" in summary:
        lines.append(
            "REVENUE BY PRODUCT"
        )
        lines.append(
            "-" * 40
        )

        for row in summary[
            "revenue_by_product"
        ]:
            lines.append(
                f"{row['Product']}: "
                f"{row['Revenue']}"
            )

        lines.append("")

    if "revenue_by_region" in summary:
        lines.append(
            "REVENUE BY REGION"
        )
        lines.append(
            "-" * 40
        )

        for row in summary[
            "revenue_by_region"
        ]:
            lines.append(
                f"{row['Region']}: "
                f"{row['Revenue']}"
            )

        lines.append("")

    lines.append(
        "GENERATED CHARTS"
    )
    lines.append(
        "-" * 40
    )

    for name, path in charts.items():
        lines.append(
            f"{name}: {path}"
        )

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return str(output_path)