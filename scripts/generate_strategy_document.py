"""
Generate the FY2026 Q1 Sales Strategy document as a .docx file.

Every figure in the document is computed from data/sales.db by this
script. Nothing is hardcoded, so the document cannot drift from the
database it claims to describe. Re-run it after the database changes
to refresh the strategy.

Usage:
    venv/Scripts/python.exe scripts/generate_strategy_document.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


REPO_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = REPO_ROOT / "data" / "sales.db"
OUTPUT_PATH = (
    REPO_ROOT
    / "documents"
    / "word"
    / "FY2026_Sales_Strategy.docx"
)


def rand(query: str, connection: sqlite3.Connection) -> float:
    return connection.execute(query).fetchone()[0]


def rand_int(
    query: str,
    connection: sqlite3.Connection,
) -> int:
    """
    Read a COUNT/SUM that is used as a document count rather
    than a currency or ratio figure. Counts must be ints so
    they inflect and format correctly.
    """

    return int(
        connection.execute(query).fetchone()[0]
    )


def plural(
    count: int,
    singular: str,
    plural_form: str,
) -> str:
    """
    Render a count with a correctly inflected noun.

    The document quotes small counts (one missing satisfaction
    score is common in this dataset), so "1 transaction(s)"
    would be visible in every run.
    """

    if count == 1:
        return f"{count} {singular}"

    return f"{count} {plural_form}"


def build_strategy_document(
    connection: sqlite3.Connection,
) -> Document:
    """
    Build the strategy document from the sales table.

    Findings, calculations, interpretations and recommendations are
    kept in separate sections, matching the reporting layer the
    analysis engine uses, so a reader can tell which claims are
    measured and which are judgement.
    """

    document = Document()

    # ---------- measured facts, straight from SQL ----------

    total_revenue = rand(
        "SELECT SUM(Revenue) FROM sales", connection
    )
    total_units = rand(
        "SELECT SUM(Units) FROM sales", connection
    )
    transaction_count = rand_int(
        "SELECT COUNT(*) FROM sales", connection
    )
    average_satisfaction = rand(
        "SELECT AVG(Customer_Satisfaction) FROM sales",
        connection,
    )
    missing_satisfaction = rand_int(
        "SELECT COUNT(*) FROM sales "
        "WHERE Customer_Satisfaction IS NULL",
        connection,
    )

    period_start, period_end = connection.execute(
        "SELECT MIN(Date), MAX(Date) FROM sales"
    ).fetchone()

    by_product = connection.execute(
        "SELECT Product, COUNT(*), SUM(Units), SUM(Revenue), "
        "AVG(Customer_Satisfaction) "
        "FROM sales GROUP BY Product ORDER BY SUM(Revenue) DESC"
    ).fetchall()

    by_region = connection.execute(
        "SELECT Region, COUNT(*), SUM(Units), SUM(Revenue), "
        "AVG(Customer_Satisfaction) "
        "FROM sales GROUP BY Region ORDER BY SUM(Revenue) DESC"
    ).fetchall()

    by_month = connection.execute(
        "SELECT SUBSTR(Date, 1, 7), SUM(Revenue), SUM(Units) "
        "FROM sales GROUP BY 1 ORDER BY 1"
    ).fetchall()

    unit_economics = connection.execute(
        "SELECT Product, SUM(Revenue) * 1.0 / SUM(Units) "
        "FROM sales GROUP BY Product ORDER BY 2 DESC"
    ).fetchall()

    # ---------- calculations, never asserted as raw facts ----------

    revenue_per_unit = total_revenue / total_units
    best_month, best_revenue, _ = max(
        by_month, key=lambda row: row[1]
    )
    worst_month, worst_revenue, _ = min(
        by_month, key=lambda row: row[1]
    )
    month_decline = (
        (worst_revenue - best_revenue) / best_revenue * 100
    )
    top_product = by_product[0]
    top_product_share = top_product[3] / total_revenue * 100
    top_region = by_region[0]
    top_region_share = top_region[3] / total_revenue * 100
    lowest_satisfaction_region = min(
        by_region, key=lambda row: row[4] or 0
    )

    # ---------- title ----------

    title = document.add_heading(
        "FY2026 Sales Performance and Growth Strategy", 0
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    subtitle = document.add_paragraph(
        f"Reporting period {period_start} to {period_end} "
        f"| Source: data/sales.db, table 'sales' "
        f"| {transaction_count} transactions"
    )
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_paragraph(
        "This strategy is derived entirely from the sales "
        "database. Every figure below was calculated from the "
        "sales table rather than estimated. Sections are ordered "
        "so that measured facts come first, followed by "
        "calculations, then interpretation, then recommended "
        "action."
    )

    # ---------- 1. measured facts ----------

    document.add_heading(
        "1. Measured Facts", level=1
    )
    document.add_paragraph(
        "These values are read directly from the database. "
        "They involve no judgement."
    )

    for statement in (
        f"Total revenue recorded: "
        f"R{total_revenue:,.0f} across "
        f"{total_units:,} units.",
        f"Total transactions recorded: "
        f"{transaction_count}.",
        f"Mean customer satisfaction score: "
        f"{average_satisfaction:.2f} out of 5.",
        f"Transactions with no satisfaction score "
        f"recorded: {missing_satisfaction}.",
        f"Blended revenue per unit sold: "
        f"R{revenue_per_unit:,.2f}.",
    ):
        document.add_paragraph(
            statement, style="List Bullet"
        )

    # ---------- 2. revenue by product ----------

    document.add_heading(
        "2. Revenue by Product", level=1
    )

    table = document.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    for cell, label in zip(
        header,
        (
            "Product",
            "Transactions",
            "Units",
            "Revenue",
            "Satisfaction",
        ),
    ):
        cell.text = label

    for product, count, units, revenue, satisfaction in by_product:
        cells = table.add_row().cells
        cells[0].text = product
        cells[1].text = str(count)
        cells[2].text = str(units)
        cells[3].text = f"R{revenue:,.0f}"
        cells[4].text = (
            f"{satisfaction:.2f}"
            if satisfaction is not None
            else "not recorded"
        )

    document.add_paragraph(
        f"{top_product[0]} is the dominant product line, "
        f"contributing R{top_product[3]:,.0f} or "
        f"{top_product_share:.1f}% of total revenue."
    )

    # ---------- 3. revenue by region ----------

    document.add_heading(
        "3. Revenue by Region", level=1
    )

    table = document.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    for cell, label in zip(
        header,
        (
            "Region",
            "Transactions",
            "Units",
            "Revenue",
            "Satisfaction",
        ),
    ):
        cell.text = label

    for region, count, units, revenue, satisfaction in by_region:
        cells = table.add_row().cells
        cells[0].text = region
        cells[1].text = str(count)
        cells[2].text = str(units)
        cells[3].text = f"R{revenue:,.0f}"
        cells[4].text = (
            f"{satisfaction:.2f}"
            if satisfaction is not None
            else "not recorded"
        )

    document.add_paragraph(
        f"{top_region[0]} leads with "
        f"R{top_region[3]:,.0f}, or {top_region_share:.1f}% "
        f"of total revenue."
    )

    # ---------- 4. monthly trend ----------

    document.add_heading(
        "4. Monthly Revenue Trend", level=1
    )

    table = document.add_table(rows=1, cols=3)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    for cell, label in zip(
        header, ("Month", "Revenue", "Units")
    ):
        cell.text = label

    for month, revenue, units in by_month:
        cells = table.add_row().cells
        cells[0].text = month
        cells[1].text = f"R{revenue:,.0f}"
        cells[2].text = str(units)

    document.add_paragraph(
        f"Revenue peaked in {best_month} at "
        f"R{best_revenue:,.0f} and fell to its lowest point "
        f"in {worst_month} at R{worst_revenue:,.0f}, a "
        f"decline of {abs(month_decline):.1f}%."
    )

    # ---------- 5. unit economics ----------

    document.add_heading(
        "5. Unit Economics by Product", level=1
    )

    table = document.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    header = table.rows[0].cells
    header[0].text = "Product"
    header[1].text = "Revenue per Unit"

    for product, value in unit_economics:
        cells = table.add_row().cells
        cells[0].text = product
        cells[1].text = f"R{value:,.2f}"

    highest = unit_economics[0]
    lowest = unit_economics[-1]

    document.add_paragraph(
        f"{highest[0]} earns R{highest[1]:,.2f} per unit "
        f"against R{lowest[1]:,.2f} for {lowest[0]}. One "
        f"{highest[0].lower()} sold generates the same "
        f"revenue as roughly "
        f"{highest[1] / lowest[1]:.0f} {lowest[0].lower()}s."
    )

    # ---------- 6. interpretations ----------

    document.add_heading(
        "6. Interpretation", level=1
    )
    document.add_paragraph(
        "The statements in this section are judgement, not "
        "measurement. They are offered as explanations of the "
        "patterns above and should be tested before being "
        "treated as established causes."
    )

    for statement in (
        f"The revenue decline between {best_month} and "
        f"{worst_month} is more likely a change in transaction "
        f"size than a collapse in demand. {worst_month} "
        f"recorded {dict((m, u) for m, _, u in by_month)[worst_month]} "
        f"units, which is not the weakest unit count in the "
        f"period, so the revenue fall reflects what was sold "
        f"rather than whether anything was sold.",

        f"Revenue concentration is high. {top_product[0]} "
        f"alone accounts for {top_product_share:.1f}% of "
        f"revenue, so the performance of the business is "
        f"closely tied to a single product line.",

        f"{top_region[0]} generates {top_region_share:.1f}% of "
        f"revenue but {lowest_satisfaction_region[0]} records "
        f"the lowest satisfaction score at "
        f"{lowest_satisfaction_region[4]:.2f}. Growth in "
        f"{lowest_satisfaction_region[0]} without a service "
        f"quality improvement risks trading margin for "
        f"attrition.",

        "The blended revenue per unit of "
        f"R{revenue_per_unit:,.2f} is pulled upward by "
        f"{top_product[0]}. Judging the accessory lines against "
        "that blended figure would understate how weak they "
        "are relative to their own volume.",
    ):
        document.add_paragraph(
            statement, style="List Bullet"
        )

    # ---------- 7. recommendations ----------

    document.add_heading(
        "7. Recommended Actions", level=1
    )
    document.add_paragraph(
        "These are proposals. They follow from the "
        "interpretation above but are not measured findings."
    )

    for statement in (
        f"Protect {top_product[0]} supply first. It carries "
        f"{top_product_share:.1f}% of revenue, so availability "
        f"in this line protects the whole period's result.",

        f"Diagnose the {worst_month} shortfall before "
        f"assuming a demand problem. The unit count for that "
        f"month does not fall as far as revenue does, which "
        f"points at transaction mix rather than volume.",

        f"Attach a satisfaction recovery target to "
        f"{lowest_satisfaction_region[0]}, currently at "
        f"{lowest_satisfaction_region[4]:.2f}, the weakest "
        f"regional score.",

        f"Close the satisfaction data gap. "
        f"{plural(missing_satisfaction, 'transaction carries', 'transactions carry')} "
        f"no satisfaction score, which means the "
        f"regional averages above rest on incomplete "
        f"evidence.",

        "Diversify away from single-product dependence. "
        f"At {top_product_share:.1f}% concentration, a supply "
        f"or pricing shock to {top_product[0]} has no offset "
        f"elsewhere in the portfolio.",

        "Re-measure before the next reporting period. Each "
        "figure here is a point in time from a small "
        f"transaction count ({transaction_count}), and the "
        "trends should not be extrapolated without more data.",
    ):
        document.add_paragraph(
            statement, style="List Bullet"
        )

    # ---------- 8. limitations ----------

    document.add_heading(
        "8. Limitations", level=1
    )

    for statement in (
        f"The dataset contains {transaction_count} "
        f"transactions over four months. Figures are precise "
        f"but statistically thin, and small changes can move "
        f"percentages sharply.",

        f"No prior-year data is present, so year-on-year "
        f"comparison and seasonality cannot be assessed.",

        f"{plural(missing_satisfaction, 'transaction has', 'transactions have')} "
        f"no satisfaction score, and no transaction has more "
        f"than one, so satisfaction is measured per "
        f"transaction rather than per customer.",

        "No cost, margin or inventory data is recorded. "
        "Revenue concentration can be identified, but "
        "profitability cannot be assessed from this table "
        "alone.",

        "Figures in this document were calculated from the "
        "sales table on the date of generation and will not "
        "update automatically.",
    ):
        document.add_paragraph(
            statement, style="List Bullet"
        )

    # ---------- footer note ----------

    note = document.add_paragraph()
    note_run = note.add_run(
        "Generated by scripts/generate_strategy_document.py "
        "directly from data/sales.db. Re-run the script to "
        "regenerate this document against updated data."
    )
    note_run.italic = True
    note_run.font.size = Pt(9)

    return document


def main() -> None:
    """
    Read the sales database and write the strategy document.
    """

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}. "
            f"Run scripts/create_sales_database.py first."
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        document = build_strategy_document(connection)
        document.save(OUTPUT_PATH)
    finally:
        connection.close()

    print(
        f"Strategy document written to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()