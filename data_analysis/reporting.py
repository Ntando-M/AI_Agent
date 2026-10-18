from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from data_analysis.analyzer import (
    calculate_monthly_revenue,
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


def _find_column(
    dataframe: pd.DataFrame,
    candidates: list[str],
) -> str | None:
    """
    Find the first column whose lowercase name matches
    any candidate (case-insensitive, also matches common
    synonyms like 'sales' or 'amount' for 'revenue').
    """

    lowered = {
        str(col).lower(): str(col)
        for col in dataframe.columns
    }

    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    return None


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

    revenue_col = _find_column(
        dataframe,
        [
            "Revenue",
            "revenue",
            "Sales",
            "sales",
            "Amount",
            "amount",
            "Total",
            "total",
            "Income",
            "income",
        ],
    )

    if revenue_col:
        revenue_statistics = (
            calculate_statistics(
                dataframe,
                revenue_col,
            )
        )

        summary["revenue_statistics"] = (
            revenue_statistics
        )

    product_col = _find_column(
        dataframe,
        [
            "Product",
            "product",
            "Item",
            "item",
            "Category",
            "category",
            "SKU",
            "sku",
        ],
    )

    if product_col and revenue_col:
        product_revenue = group_by_column(
            dataframe,
            product_col,
            revenue_col,
            "sum",
        )

        product_revenue = (
            product_revenue
            .sort_values(
                revenue_col,
                ascending=False,
            )
        )

        summary["revenue_by_product"] = (
            product_revenue.to_dict(
                orient="records"
            )
        )

    region_col = _find_column(
        dataframe,
        [
            "Region",
            "region",
            "Location",
            "location",
            "City",
            "city",
            "Country",
            "country",
            "Store",
            "store",
        ],
    )

    if region_col and revenue_col:
        region_revenue = group_by_column(
            dataframe,
            region_col,
            revenue_col,
            "sum",
        )

        region_revenue = (
            region_revenue
            .sort_values(
                revenue_col,
                ascending=False,
            )
        )

        summary["revenue_by_region"] = (
            region_revenue.to_dict(
                orient="records"
            )
        )

    date_col = _find_column(
        dataframe,
        [
            "Date",
            "date",
            "Month",
            "month",
            "Year",
            "year",
            "Period",
            "period",
            "Time",
            "time",
        ],
    )

    summary["_detected_columns"] = {
        "revenue": revenue_col,
        "product": product_col,
        "region": region_col,
        "date": date_col,
    }

    return summary


def _format_currency(value: float) -> str:
    """
    Render a revenue figure in a consistent, readable form.

    Deterministic formatting keeps calculated findings
    comparable across report sections.
    """

    return f"R{value:,.2f}"


def _percent(value: float) -> str:
    return f"{value:.1f}%"


def build_finding_layers(
    dataframe: pd.DataFrame,
    summary: dict[str, Any],
) -> dict[str, list[str]]:
    """
    Separate the report into the four evidence layers
    the roadmap requires.

    A report must distinguish:
      facts               - what the data literally contains
      calculated findings - what deterministic arithmetic derived
      interpretations     - what the pattern appears to mean
      recommendations     - what to do about it

    Every string is produced without an LLM. The layers differ
    by claim strength: facts state observed values, findings
    state arithmetic, interpretations hedge with "appears",
    and recommendations are actions. A finding that cannot be
    derived is never invented - its layer stays empty.
    """

    facts: list[str] = []
    findings: list[str] = []
    interpretations: list[str] = []
    recommendations: list[str] = []

    facts.append(
        f"The dataset contains {summary['rows']} rows "
        f"across {summary['columns']} columns."
    )

    missing_total = sum(
        summary["missing_values"].values()
    )

    if missing_total:
        facts.append(
            f"{missing_total} cell(s) contain missing "
            f"values."
        )

    detected = summary.get("_detected_columns", {})
    revenue_col = detected.get("revenue")
    product_col = detected.get("product")
    region_col = detected.get("region")
    date_col = detected.get("date")

    product_rows = summary.get(
        "revenue_by_product"
    )

    region_rows = summary.get(
        "revenue_by_region"
    )

    revenue_sum = None

    if product_rows and revenue_col:
        revenue_sum = sum(
            row[revenue_col]
            for row in product_rows
        )

        facts.append(
            f"Total revenue across all products is "
            f"{_format_currency(revenue_sum)}."
        )

    if (
        product_rows
        and revenue_sum
        and product_col
    ):
        top_product = product_rows[0]

        facts.append(
            f"The highest-revenue product is "
            f"{top_product[product_col]} at "
            f"{_format_currency(top_product[revenue_col])}."
        )

        share = (
            top_product[revenue_col] / revenue_sum * 100
        )

        findings.append(
            f"{top_product[product_col]} accounts for "
            f"{_percent(share)} of total revenue."
        )

        if share >= 50:
            interpretations.append(
                f"Revenue appears concentrated in "
                f"{top_product[product_col]}, which alone "
                f"exceeds half of the total."
            )

            recommendations.append(
                f"Review the pipeline feeding "
                f"{top_product[product_col]} - concentration "
                f"of this size makes overall revenue "
                f"sensitive to that one category."
            )

    if (
        region_rows
        and revenue_sum
        and region_col
    ):
        top_region = region_rows[0]

        findings.append(
            f"{top_region[region_col]} generates the most "
            f"revenue at "
            f"{_format_currency(top_region[revenue_col])}."
        )

    monthly = None

    if date_col and revenue_col:
        monthly = (
            calculate_monthly_revenue(
                dataframe,
                date_col,
                revenue_col,
            )
            .sort_values("Month")
        )

    if (
        monthly is not None
        and len(monthly) >= 2
    ):
        first_month = monthly.iloc[0]
        last_month = monthly.iloc[-1]

        if first_month["Revenue"]:
            change = (
                (
                    last_month["Revenue"]
                    - first_month["Revenue"]
                )
                / first_month["Revenue"]
                * 100
            )

            findings.append(
                f"Revenue moved from "
                f"{_format_currency(first_month['Revenue'])} "
                f"in {first_month['Month']} to "
                f"{_format_currency(last_month['Revenue'])} "
                f"in {last_month['Month']}, a change of "
                f"{change:+.1f}%."
            )

            if change < 0:
                interpretations.append(
                    f"The decline appears to begin in "
                    f"{last_month['Month']}; the dataset does "
                    f"not contain evidence of its cause."
                )

                recommendations.append(
                    f"Correlate the movement in "
                    f"{last_month['Month']} with any "
                    f"documented strategy or pricing "
                    f"changes before acting on it."
                )

            elif change > 0:
                interpretations.append(
                    f"Revenue appears to be growing across "
                    f"the period covered by the dataset."
                )

    if not findings:
        findings.append(
            "No revenue column was available, so no "
            "calculated findings could be derived."
        )

    return {
        "facts": facts,
        "calculated_findings": findings,
        "interpretations": interpretations,
        "recommendations": recommendations,
    }


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

    layers = build_finding_layers(
        dataframe,
        summary,
    )

    charts = generate_standard_sales_charts(
        dataframe,
        output_directory=chart_directory,
    )

    return {
        "summary": summary,
        "layers": layers,
        "charts": charts,
    }


def build_report_document(
    dataframe: pd.DataFrame,
    dataset_name: str | None = None,
    report_directory: str | Path = (
        DEFAULT_REPORT_DIRECTORY
    ),
    chart_directory: str | Path = "outputs/charts",
) -> dict[str, Any]:
    """
    Assemble one complete, persistable report document.

    Wraps the existing summary, layer and chart builders
    rather than duplicating them, so a report served over
    the API and a report written by the CLI are produced by
    the same deterministic code.

    `content` is the human-readable text rendering, kept so
    a report is still readable as plain text and so the
    existing text format stays the canonical artefact.
    """

    report = generate_sales_report(
        dataframe,
        report_directory=report_directory,
        chart_directory=chart_directory,
    )

    content = save_report_summary(
        report,
        Path(report_directory) / "latest_report.txt",
    )

    return {
        "content": Path(content).read_text(
            encoding="utf-8"
        ),
        "dataset_name": dataset_name,
        "summary": report["summary"],
        "layers": report["layers"],
        "charts": report["charts"],
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
    layers = report.get("layers")
    charts = report["charts"]

    lines: list[str] = []

    lines.append(
        "AI DATA ANALYST - V7 SALES REPORT"
    )
    lines.append(
        "=" * 40
    )
    lines.append("")

    section_order = (
        (
            "FACTS",
            "What the data contains.",
            "facts",
        ),
        (
            "CALCULATED FINDINGS",
            "Derived by deterministic arithmetic.",
            "calculated_findings",
        ),
        (
            "INTERPRETATIONS",
            "What the pattern appears to mean.",
            "interpretations",
        ),
        (
            "RECOMMENDATIONS",
            "Suggested actions.",
            "recommendations",
        ),
    )

    for heading, description, key in section_order:
        entries = (layers or {}).get(key) or []

        lines.append(heading)
        lines.append("-" * 40)
        lines.append(description)

        if not entries:
            lines.append(
                "- None could be derived "
                "from the available data."
            )
        else:
            for entry in entries:
                lines.append(f"- {entry}")

        lines.append("")

    lines.append(
        "DATASET DETAIL"
    )
    lines.append("-" * 40)
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

    detected = summary.get("_detected_columns", {})
    revenue_col = detected.get("revenue", "Revenue")
    product_col = detected.get("product", "Product")
    region_col = detected.get("region", "Region")

    if "revenue_by_product" in summary:
        lines.append(
            f"REVENUE BY {product_col.upper()}"
        )
        lines.append(
            "-" * 40
        )

        for row in summary[
            "revenue_by_product"
        ]:
            lines.append(
                f"{row[product_col]}: "
                f"{row[revenue_col]}"
            )

        lines.append("")

    if "revenue_by_region" in summary:
        lines.append(
            f"REVENUE BY {region_col.upper()}"
        )
        lines.append(
            "-" * 40
        )

        for row in summary[
            "revenue_by_region"
        ]:
            lines.append(
                f"{row[region_col]}: "
                f"{row[revenue_col]}"
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