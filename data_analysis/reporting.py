from __future__ import annotations

from collections.abc import Sequence
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
    generate_standard_charts,
)


DEFAULT_REPORT_DIRECTORY = Path(
    "reports"
)


def _find_column(
    dataframe: pd.DataFrame,
    candidates: Sequence[str],
) -> str | None:
    """
    Find the first column whose lowercase name matches
    any candidate (case-insensitive, also matches common
    synonyms like 'sales' or 'amount' for 'revenue').

    A candidate matches when the column name equals it or
    contains it, so 'registration_date' is recognised as a
    date column. The exact match is tried first so a column
    literally named 'Date' wins over one that merely
    contains the word.
    """

    lowered = {
        str(col).lower(): str(col)
        for col in dataframe.columns
    }

    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    for candidate in candidates:
        needle = candidate.lower()

        for lowered_name, original in lowered.items():
            if needle in lowered_name:
                return original

    return None


MEASURE_COLUMN_CANDIDATES = (
    "revenue",
    "sales",
    "amount",
    "total",
    "income",
    "turnover",
    "profit",
    "price",
    "value",
    "salary",
    "wage",
    "spend",
    "cost",
    "fee",
    "charge",
    "budget",
)

MEASURE_COLUMN_SYNONYMS = tuple(
    dict.fromkeys(
        MEASURE_COLUMN_CANDIDATES + ("units",)
    )
)

PRODUCT_COLUMN_SYNONYMS = (
    "Product",
    "product",
    "Item",
    "item",
    "Category",
    "category",
    "SKU",
    "sku",
)

REGION_COLUMN_SYNONYMS = (
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
)

DATE_COLUMN_SYNONYMS = (
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
)


def _is_identifier(column: object) -> bool:
    """
    Whether a numeric column is a surrogate key.

    An id's min, max and mean are properties of the row
    numbering, not of anything a reader can act on, so it
    must not be picked as the column a report describes.
    Matched on whole words: 'user_id' and 'id' are keys,
    'valid' and 'grid' are not.
    """

    name = str(column).lower()

    return (
        name in {"id", "key", "index", "uuid"}
        or name.endswith("_id")
        or name.startswith("id_")
    )


def _find_numeric_column(
    dataframe: pd.DataFrame,
) -> str | None:
    """
    The first numeric column that measures something,
    preferring one whose name looks like money.

    Used by the general summary, which must pick one column
    to describe rather than assume the dataset has a
    'Revenue' column at all. Identifier columns are skipped:
    a report whose headline figure is 'id ranges from 1 to
    4' is not analysis.
    """

    numeric = [
        column
        for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(
            dataframe[column]
        )
        and not _is_identifier(column)
    ]

    for candidate in MEASURE_COLUMN_CANDIDATES:
        for column in numeric:
            if candidate in str(column).lower():
                return column

    return numeric[0] if numeric else None


def _categorical_counts(
    dataframe: pd.DataFrame,
    date_column: str | None,
) -> dict[str, dict[str, int]]:
    """
    Value counts for each non-numeric column that repeats a
    value.

    A column where every row is unique - an email, an ip
    address - has no distribution to report, so it is left
    out. What remains is the categorical shape of the data,
    which is the one thing a users export does carry.
    """

    counts: dict[str, dict[str, int]] = {}

    for column in dataframe.columns:
        if column == date_column:
            continue

        if pd.api.types.is_numeric_dtype(
            dataframe[column]
        ):
            continue

        values = (
            dataframe[column].dropna().value_counts()
        )

        if values.empty:
            continue

        if len(values) >= len(dataframe):
            continue

        # Sorted by count then by label: a tie must always
        # name the same value, or the finding changes between
        # pandas versions.
        ordered = sorted(
            values.items(),
            key=lambda item: (
                -item[1],
                str(item[0]),
            ),
        )

        counts[str(column)] = {
            str(value): int(count)
            for value, count in ordered
        }

    return counts


def _find_measure_column(
    dataframe: pd.DataFrame,
) -> str | None:
    """
    The column a report measures, whatever the dataset.

    A recognised money-shaped column wins when it is numeric;
    otherwise the first numeric column that is not a surrogate
    key is the measure. A score, an age or a count is a
    measure like any other, and reporting only works when one
    exists, so this falls through to a plain numeric column
    rather than returning None for a non-sales table.
    """

    recognised = _find_column(
        dataframe,
        [
            synonym.capitalize()
            for synonym in MEASURE_COLUMN_SYNONYMS
        ],
    )

    if recognised is not None and (
        pd.api.types.is_numeric_dtype(
            dataframe[recognised]
        )
    ):
        return recognised

    return _find_numeric_column(dataframe)


def _is_additive(column: str | None) -> bool:
    """
    Whether summing a column means anything.

    Money sums: total revenue is revenue. Extensive measures
    like counts and amounts sum too. An age, a score, a
    rating or a percentage does not - summing the ages of
    everyone in a room is a number that describes nothing -
    so for those the measure is aggregated by its mean
    instead, which is the statistic that does carry meaning.
    """

    if column is None:
        return False

    name = str(column).lower()

    if any(hint in name for hint in MONETARY_COLUMN_HINTS):
        return True

    return not any(
        hint in name
        for hint in (
            "age",
            "score",
            "rating",
            "percent",
            "rate",
            "ratio",
            "avg",
            "average",
            "mean",
            "temperature",
            "temp",
        )
    )


def _measure_aggregation(column: str | None) -> str:
    """
    The aggregation a measure column is grouped by.
    """

    return "sum" if _is_additive(column) else "mean"


def _find_groupable_column(
    dataframe: pd.DataFrame,
    measure_column: str | None,
    date_column: str | None,
) -> str | None:
    """
    The first non-numeric column with a readable number of
    distinct values, for grouping a measure that has no
    named Product or Region column.

    A column whose every row differs - an email, an ip
    address - produces one group per row, which is a
    listing rather than a grouping, so it is skipped.
    'Too many groups to be a category' is capped at the row
    count, which keeps a dataset with a handful of rows
    groupable while refusing a free-text column.

    The measure column itself is excluded: a column cannot
    group itself into a total.
    """

    for column in dataframe.columns:
        if column in (measure_column, date_column):
            continue

        if pd.api.types.is_numeric_dtype(
            dataframe[column]
        ):
            continue

        distinct = (
            dataframe[column].dropna().nunique()
        )

        if distinct == 0 or distinct >= len(dataframe):
            continue

        if distinct > 50:
            continue

        return str(column)

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

    measure_col = _find_measure_column(dataframe)

    if measure_col:
        measure_statistics = (
            calculate_statistics(
                dataframe,
                measure_col,
            )
        )

        summary["revenue_statistics"] = (
            measure_statistics
        )

    product_col = _find_column(
        dataframe,
        PRODUCT_COLUMN_SYNONYMS,
    )

    region_col = _find_column(
        dataframe,
        REGION_COLUMN_SYNONYMS,
    )

    date_col = _find_column(
        dataframe,
        DATE_COLUMN_SYNONYMS,
    )

    summary["_detected_columns"] = {
        "revenue": measure_col,
        "product": product_col,
        "region": region_col,
        "date": date_col,
    }

    # The first categorical column with a manageable number
    # of distinct values, for grouping a measure that has no
    # named Product or Region column. A 'Department' or
    # 'Team' column is as readable a grouping as either, and
    # a report that only groups by a handful of hardcoded
    # names is not general.
    #
    # It is looked for even when the dataset has no measure,
    # so a text-only table still gets one chart of its own
    # shape. Summing is skipped in that case, since there is
    # nothing to sum.
    groupable_col = product_col or region_col

    if groupable_col is None:
        groupable_col = _find_groupable_column(
            dataframe,
            measure_col,
            date_col,
        )

    if groupable_col and measure_col:
        measure_by_group = group_by_column(
            dataframe,
            groupable_col,
            measure_col,
            _measure_aggregation(measure_col),
        )

        measure_by_group = (
            measure_by_group
            .sort_values(
                measure_col,
                ascending=False,
            )
        )

        summary["revenue_by_product"] = (
            measure_by_group.to_dict(
                orient="records"
            )
        )

        summary["_detected_columns"]["grouped_by"] = (
            groupable_col
        )

        # A named grouping and a found one are not the same
        # claim: 'by Product' and 'by Department' are
        # business language, but a grouping discovered by
        # scanning the columns is a heuristic, so the report
        # says how it was chosen rather than asserting it.
        summary["_detected_columns"]["grouped_by_named"] = (
            product_col is not None or region_col is not None
        )

    # The column the report describes in prose. When a
    # category groups the measure, the measure is named in
    # every grouped finding and no separate column needs
    # describing; otherwise the measure column is the one
    # thing the dataset measures, so it is the one described.
    summary["general_column"] = (
        None if groupable_col else measure_col
    )

    if measure_col is None:
        # No numeric column at all, so no measure exists to
        # group. Describe the columns that are present
        # instead, or the report has nothing to say.
        summary["categorical_counts"] = (
            _categorical_counts(
                dataframe,
                date_col,
            )
        )

        if date_col:
            summary["records_by_period"] = (
                _records_by_period(
                    dataframe,
                    date_col,
                )
            )

        return summary

    if groupable_col is None:
        # A measure column exists but nothing is recognised
        # to group it by. Its own distribution is still
        # arithmetic worth reporting.
        summary["general_statistics"] = (
            calculate_statistics(
                dataframe,
                measure_col,
            )
        )

        summary["categorical_counts"] = (
            _categorical_counts(
                dataframe,
                date_col,
            )
        )

    if date_col:
        summary["records_by_period"] = (
            _records_by_period(
                dataframe,
                date_col,
            )
        )

    return summary


def _records_by_period(
    dataframe: pd.DataFrame,
    date_column: str,
) -> dict[str, int]:
    """
    Row counts grouped by calendar month.

    A count is the one arithmetic every dataset supports, so
    a table with no numeric column still gets a finding: how
    its records are distributed over time.
    """

    dates = pd.to_datetime(
        dataframe[date_column],
        errors="coerce",
    )

    working = dataframe.loc[dates.notna()].copy()
    working["_Date"] = dates[dates.notna()]

    if working.empty:
        return {}

    monthly = (
        working["_Date"]
        .dt.to_period("M")
        .astype(str)
        .value_counts()
        .sort_index()
    )

    return {
        str(month): int(count)
        for month, count in monthly.items()
    }


def _format_currency(value: float) -> str:
    """
    Render a revenue figure in a consistent, readable form.

    Deterministic formatting keeps calculated findings
    comparable across report sections.
    """

    return f"R{value:,.2f}"


def _format_number(value: float) -> str:
    """
    Render a figure from a non-monetary column.

    The general summary describes whatever numeric column a
    dataset has - an id, an age, a score - and prefixing those
    with a currency symbol would misrepresent them. A whole
    number is rendered without decimals, so a count is not
    printed as '1,234.00'.
    """

    if float(value).is_integer():
        return f"{value:,.0f}"

    return f"{value:,.2f}"


def _percent(value: float) -> str:
    return f"{value:.1f}%"


MONETARY_COLUMN_HINTS = (
    "revenue",
    "sales",
    "amount",
    "total",
    "income",
    "price",
    "value",
    "turnover",
    "profit",
    "cost",
    "spend",
    "salary",
    "wage",
    "fee",
    "charge",
    "budget",
)


def _is_monetary(column: str) -> bool:
    """
    Whether a column name suggests money.

    The report must not prefix a figure with a currency
    symbol unless the column is known to hold money: an
    age, a score or a count would be misrepresented by
    one. Matched as a substring so 'unit_price' and
    'salary' both qualify.
    """

    name = str(column).lower()

    return any(
        hint in name for hint in MONETARY_COLUMN_HINTS
    )


def _measure_noun(column: str | None) -> str:
    """
    The word the report uses for the measure column.

    A column named for revenue or sales is reported as
    'revenue', which keeps the existing sales wording.
    Any other column is named as it appears in the
    dataset, so an 'Amount' column is never called
    revenue and a 'Salary' column is never called
    revenue.
    """

    if column is None:
        return "value"

    name = str(column)

    if (
        "revenue" in name.lower()
        or "sales" in name.lower()
    ):
        return "revenue"

    return name


def _is_money_measure(column: str | None) -> bool:
    """
    Whether the measure column is the sales/revenue one.

    Kept separate from _is_monetary, which is used to decide
    whether a figure gets a currency symbol. 'Salary' is
    monetary, so its figures are rendered as money, but it is
    not the sales measure - and the sales-specific wording
    ('revenue', 'pricing changes') belongs to revenue alone.
    """

    if column is None:
        return False

    return _measure_noun(column) == "revenue"


def _capitalise(value: str) -> str:
    return value[:1].upper() + value[1:]


def _cause_context(column: str | None) -> str:
    """
    The kind of event that could explain a movement in a
    measure column.

    A recommendation that tells the reader to look for
    'pricing changes' is only useful for money data; the same
    advice against a count of incidents or a test score sends
    them looking for the wrong cause. Non-monetary measures
    get neutral wording.
    """

    if _is_money_measure(column):
        return "strategy or pricing changes"

    return "operational changes"


def _pluralise(column: str) -> str:
    """
    A readable plural for a column name.

    'Product' becomes 'Products' and 'Category' becomes
    'Categories', so a sentence can say 'across all
    products' rather than naming the column.
    """

    name = str(column)
    lowered = name.lower()

    if lowered.endswith("ies"):
        return f"{name[:-3]}ies"

    if lowered.endswith(("_s", "ss", "x", "ch", "sh")):
        return f"{name}es"

    if (
        lowered.endswith("y")
        and len(name) > 1
        and name[-2].lower() not in "aeiou"
    ):
        return f"{name[:-1]}ies"

    return f"{name}s"


def _singular(column: str) -> str:
    """
    A readable singular for a column name.

    'Products' becomes 'Product'. Used where a sentence
    names one row's category rather than the whole set.
    """

    name = str(column)
    lowered = name.lower()

    if lowered.endswith("ies"):
        return f"{name[:-3]}y"

    if lowered.endswith("s") and not lowered.endswith("ss"):
        return name[:-1]

    return name


def _format_value(column: str | None, value: float) -> str:
    """
    Render a measure column's figure in its own unit.

    Money columns get the currency form; anything else - a
    count, an age, a score - gets the neutral form, because
    a currency symbol on a non-monetary value is a false
    claim about what the column holds.
    """

    if column and _is_monetary(column):
        return _format_currency(value)

    return _format_number(value)


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
    measure_col = detected.get("revenue")
    date_col = detected.get("date")
    group_col = detected.get("grouped_by")

    group_rows = summary.get("revenue_by_product")

    measure_noun = _measure_noun(measure_col)

    grouped_total = None

    grouped_by_named = detected.get("grouped_by_named")

    # How the measure is combined within a group. A total
    # only means something for an additive measure, so the
    # same rule the summary used decides both the arithmetic
    # and the word used to describe it.
    aggregation = _measure_aggregation(measure_col)
    aggregate_word = (
        "total" if aggregation == "sum" else "average"
    )

    if group_rows and measure_col:
        if aggregation == "sum":
            grouped_total = sum(
                row[measure_col] for row in group_rows
            )
        else:
            grouped_total = (
                sum(row[measure_col] for row in group_rows)
                / len(group_rows)
            )

        group_word = (
            _pluralise(group_col).lower()
            if grouped_by_named
            else f"{group_col.lower()} groups"
        )

        facts.append(
            f"{_capitalise(aggregate_word)} {measure_noun} "
            f"across all {group_word} is "
            f"{_format_value(measure_col, grouped_total)}."
        )

    if (
        group_rows
        and grouped_total
        and group_col
    ):
        top_group = group_rows[0]

        group_label = (
            _singular(group_col).lower()
            if grouped_by_named
            else f"{group_col.lower()} group"
        )

        facts.append(
            f"The highest-{measure_noun} "
            f"{group_label} is "
            f"{top_group[group_col]} at "
            f"{_format_value(measure_col, top_group[measure_col])}."
        )

        share = (
            top_group[measure_col] / grouped_total * 100
        )

        if aggregation == "sum":
            findings.append(
                f"{top_group[group_col]} accounts for "
                f"{_percent(share)} of total {measure_noun}."
            )
        else:
            # A share of a mean is not a share: it is how far
            # this group's average sits above or below the
            # overall average, expressed as a percentage.
            deviation = (
                (top_group[measure_col] - grouped_total)
                / grouped_total
                * 100
            )

            findings.append(
                f"{top_group[group_col]} averages "
                f"{_format_value(measure_col, top_group[measure_col])}, "
                f"which is {abs(deviation):.1f}% "
                f"{'above' if deviation > 0 else 'below'} "
                f"the overall average of "
                f"{_format_value(measure_col, grouped_total)}."
            )

        # A single group is not concentration, it is the
        # whole dataset: claiming a dominant category from
        # one row would be a claim the data cannot support.
        # Nor is a group whose average is highest
        # 'concentrated' - that is a difference in level, not
        # a share of a total.
        if (
            share >= 50
            and len(group_rows) > 1
            and aggregation == "sum"
        ):
            interpretations.append(
                f"{_capitalise(measure_noun)} appears "
                f"concentrated in "
                f"{top_group[group_col]}, which alone "
                f"exceeds half of the total."
            )

            recommendations.append(
                f"Review the pipeline feeding "
                f"{top_group[group_col]} - concentration "
                f"of this size makes overall {measure_noun} "
                f"sensitive to that one category."
            )

    monthly = None

    if date_col and measure_col:
        monthly = (
            calculate_monthly_revenue(
                dataframe,
                date_col,
                measure_col,
            )
            .sort_values("Month")
        )

    if (
        monthly is not None
        and len(monthly) >= 2
    ):
        first_month = monthly.iloc[0]
        last_month = monthly.iloc[-1]

        first_value = first_month[measure_col]
        last_value = last_month[measure_col]

        if first_value:
            change = (
                (last_value - first_value) / first_value * 100
            )

            findings.append(
                f"{_capitalise(measure_noun)} moved from "
                f"{_format_value(measure_col, first_value)} "
                f"in {first_month['Month']} to "
                f"{_format_value(measure_col, last_value)} "
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
                    f"documented "
                    f"{_cause_context(measure_col)} "
                    f"before acting on it."
                )

            elif change > 0:
                interpretations.append(
                    f"{_capitalise(measure_noun)} appears to "
                    f"be growing across the period covered "
                    f"by the dataset."
                )

    general_column = summary.get("general_column")

    if general_column:
        statistics = summary["general_statistics"]

        # A single row, or a column with no variation, makes
        # min, max and mean the same number: the sentence
        # would read 'ranges from 100 to 100, averaging
        # 100', which is a restatement rather than a
        # finding. Report the value once instead.
        if statistics["min"] == statistics["max"]:
            findings.append(
                f"{general_column} is "
                f"{_format_value(general_column, statistics['min'])} "
                f"for all {int(statistics['count'])} records."
            )
        else:
            findings.append(
                f"{general_column} ranges from "
                f"{_format_value(general_column, statistics['min'])} to "
                f"{_format_value(general_column, statistics['max'])}, "
                f"averaging "
                f"{_format_value(general_column, statistics['mean'])} "
                f"across {int(statistics['count'])} records."
            )

    records_by_period = summary.get(
        "records_by_period"
    )

    if records_by_period:
        busiest_month = max(
            records_by_period.items(),
            key=lambda item: item[1],
        )

        findings.append(
            f"{busiest_month[0]} holds the most records "
            f"({busiest_month[1]} of {summary['rows']})."
        )

    categorical_counts = summary.get(
        "categorical_counts"
    )

    for column, counts in (
        categorical_counts or {}
    ).items():
        top_value, top_count = next(
            iter(counts.items())
        )

        share = (
            top_count / summary["rows"] * 100
        )

        findings.append(
            f"{column} is dominated by {top_value} "
            f"({top_count} of {summary['rows']} records, "
            f"{_percent(share)})."
        )

    if not findings:
        # Reached only when the dataset has no numeric column
        # at all and no repeating category to count: a table
        # of unique text values, which has no arithmetic.
        findings.append(
            "The dataset has no numeric column to measure "
            "and no repeating category to count, so no "
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

    Works for any tabular dataset, not only sales data:
    the measure column is whichever numeric column the
    dataset carries, and the grouping column is whichever
    categorical column it carries.

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

    charts = generate_standard_charts(
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
        "AI DATA ANALYST - DATASET REPORT"
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

    detected = summary.get("_detected_columns", {})
    measure_col = detected.get("revenue")
    group_col = detected.get("grouped_by")
    measure_noun = _measure_noun(measure_col)

    if "revenue_statistics" in summary:
        statistics = summary[
            "revenue_statistics"
        ]

        lines.append(
            f"{_capitalise(measure_noun).upper()} STATISTICS"
        )
        lines.append(
            "-" * 40
        )

        for key, value in statistics.items():
            lines.append(
                f"{key}: "
                f"{_format_value(measure_col, value)}"
            )

        lines.append("")

    general_column = summary.get("general_column")

    if general_column:
        lines.append(
            f"{general_column.upper()} STATISTICS"
        )
        lines.append(
            "-" * 40
        )

        for key, value in summary[
            "general_statistics"
        ].items():
            lines.append(
                f"{key}: "
                f"{_format_value(general_column, value)}"
            )

        lines.append("")

    records_by_period = summary.get(
        "records_by_period"
    )

    if records_by_period:
        lines.append(
            "RECORDS BY MONTH"
        )
        lines.append(
            "-" * 40
        )

        for month, count in records_by_period.items():
            lines.append(f"{month}: {count}")

        lines.append("")

    categorical_counts = summary.get(
        "categorical_counts"
    )

    for column, counts in (
        categorical_counts or {}
    ).items():
        lines.append(f"{column.upper()} VALUES")
        lines.append("-" * 40)

        for value, count in counts.items():
            lines.append(f"{value}: {count}")

        lines.append("")

    if "revenue_by_product" in summary:
        lines.append(
            f"{_capitalise(measure_noun).upper()} "
            f"BY {group_col.upper()}"
        )
        lines.append(
            "-" * 40
        )

        for row in summary[
            "revenue_by_product"
        ]:
            lines.append(
                f"{row[group_col]}: "
                f"{_format_value(measure_col, row[measure_col])}"
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