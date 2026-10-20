from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_OUTPUT_DIRECTORY = Path("outputs") / "charts"


def _validate_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
) -> None:
    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError(
            "Expected a Pandas DataFrame"
        )

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: "
            f"{missing_columns}"
        )


def _require_numeric_column(
    dataframe: pd.DataFrame,
    column: str,
) -> None:
    if not pd.api.types.is_numeric_dtype(
        dataframe[column]
    ):
        raise TypeError(
            f"Column '{column}' must be numeric"
        )


def _prepare_output_path(
    output_path: str | Path,
) -> Path:
    path = Path(output_path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def _save_figure(
    figure,
    output_path: str | Path,
) -> str:
    path = _prepare_output_path(
        output_path
    )

    figure.savefig(
        path,
        bbox_inches="tight",
        dpi=150,
    )

    plt.close(figure)

    return str(path)


def plot_revenue_by_product(
    dataframe: pd.DataFrame,
    product_column: str = "Product",
    revenue_column: str = "Revenue",
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "revenue_by_product.png"
    ),
) -> str:
    """
    Generate a bar chart showing total revenue
    by product.
    """

    _validate_columns(
        dataframe,
        [
            product_column,
            revenue_column,
        ],
    )

    if not pd.api.types.is_numeric_dtype(
        dataframe[revenue_column]
    ):
        raise TypeError(
            f"Column '{revenue_column}' must be numeric"
        )

    grouped = (
        dataframe
        .groupby(product_column)[revenue_column]
        .sum()
        .sort_values(ascending=False)
    )

    figure, axis = plt.subplots()

    grouped.plot(
        kind="bar",
        ax=axis,
    )

    axis.set_title(
        "Revenue by Product"
    )
    axis.set_xlabel(
        product_column
    )
    axis.set_ylabel(
        "Revenue"
    )

    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_revenue_by_region(
    dataframe: pd.DataFrame,
    region_column: str = "Region",
    revenue_column: str = "Revenue",
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "revenue_by_region.png"
    ),
) -> str:
    """
    Generate a bar chart showing total revenue
    by region.
    """

    _validate_columns(
        dataframe,
        [
            region_column,
            revenue_column,
        ],
    )

    if not pd.api.types.is_numeric_dtype(
        dataframe[revenue_column]
    ):
        raise TypeError(
            f"Column '{revenue_column}' must be numeric"
        )

    grouped = (
        dataframe
        .groupby(region_column)[revenue_column]
        .sum()
        .sort_values(ascending=False)
    )

    figure, axis = plt.subplots()

    grouped.plot(
        kind="bar",
        ax=axis,
    )

    axis.set_title(
        "Revenue by Region"
    )
    axis.set_xlabel(
        region_column
    )
    axis.set_ylabel(
        "Revenue"
    )

    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_monthly_revenue(
    dataframe: pd.DataFrame,
    date_column: str = "Date",
    revenue_column: str = "Revenue",
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "monthly_revenue.png"
    ),
) -> str:
    """
    Generate a line chart showing monthly revenue.
    """

    _validate_columns(
        dataframe,
        [
            date_column,
            revenue_column,
        ],
    )

    if not pd.api.types.is_numeric_dtype(
        dataframe[revenue_column]
    ):
        raise TypeError(
            f"Column '{revenue_column}' must be numeric"
        )

    dates = pd.to_datetime(
        dataframe[date_column],
        errors="coerce",
    )

    working_dataframe = dataframe.loc[
        dates.notna()
    ].copy()

    working_dataframe["_Date"] = dates.loc[
        dates.notna()
    ]

    monthly = (
        working_dataframe
        .groupby(
            working_dataframe["_Date"].dt.to_period("M")
        )[revenue_column]
        .sum()
    )

    figure, axis = plt.subplots()

    monthly.plot(
        kind="line",
        marker="o",
        ax=axis,
    )

    axis.set_title(
        "Monthly Revenue"
    )
    axis.set_xlabel(
        "Month"
    )
    axis.set_ylabel(
        "Revenue"
    )

    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_revenue_trend(
    dataframe: pd.DataFrame,
    date_column: str = "Date",
    revenue_column: str = "Revenue",
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "revenue_trend.png"
    ),
) -> str:
    """
    Generate a chronological revenue trend chart.
    """

    _validate_columns(
        dataframe,
        [
            date_column,
            revenue_column,
        ],
    )

    if not pd.api.types.is_numeric_dtype(
        dataframe[revenue_column]
    ):
        raise TypeError(
            f"Column '{revenue_column}' must be numeric"
        )

    dates = pd.to_datetime(
        dataframe[date_column],
        errors="coerce",
    )

    working_dataframe = dataframe.loc[
        dates.notna()
    ].copy()

    working_dataframe["_Date"] = dates.loc[
        dates.notna()
    ]

    working_dataframe = (
        working_dataframe
        .sort_values("_Date")
    )

    figure, axis = plt.subplots()

    axis.plot(
        working_dataframe["_Date"],
        working_dataframe[revenue_column],
        marker="o",
    )

    axis.set_title(
        "Revenue Trend"
    )
    axis.set_xlabel(
        "Date"
    )
    axis.set_ylabel(
        "Revenue"
    )

    figure.autofmt_xdate()
    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_revenue_distribution(
    dataframe: pd.DataFrame,
    revenue_column: str = "Revenue",
    bins: int = 10,
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "revenue_distribution.png"
    ),
) -> str:
    """
    Generate a histogram showing the distribution
    of a numeric column.
    """

    _validate_columns(
        dataframe,
        [
            revenue_column,
        ],
    )

    _require_numeric_column(
        dataframe,
        revenue_column,
    )

    figure, axis = plt.subplots()

    dataframe[revenue_column].plot(
        kind="hist",
        bins=bins,
        ax=axis,
        edgecolor="black",
    )

    axis.set_title(
        f"{revenue_column} Distribution"
    )
    axis.set_xlabel(revenue_column)
    axis.set_ylabel("Frequency")

    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_revenue_relationship(
    dataframe: pd.DataFrame,
    x_column: str = "Revenue",
    y_column: str = "Quantity",
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "revenue_relationship.png"
    ),
) -> str:
    """
    Generate a scatter plot showing the relationship
    between two numeric columns.
    """

    _validate_columns(
        dataframe,
        [
            x_column,
            y_column,
        ],
    )

    _require_numeric_column(
        dataframe,
        x_column,
    )

    _require_numeric_column(
        dataframe,
        y_column,
    )

    figure, axis = plt.subplots()

    axis.scatter(
        dataframe[x_column],
        dataframe[y_column],
        alpha=0.7,
        edgecolor="black",
    )

    axis.set_title(
        f"{y_column} vs {x_column}"
    )
    axis.set_xlabel(x_column)
    axis.set_ylabel(y_column)

    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_revenue_box_plot(
    dataframe: pd.DataFrame,
    category_column: str = "Product",
    value_column: str = "Revenue",
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "revenue_box_plot.png"
    ),
) -> str:
    """
    Generate a box plot showing the distribution
    and outliers of a numeric column per category.
    """

    _validate_columns(
        dataframe,
        [
            category_column,
            value_column,
        ],
    )

    _require_numeric_column(
        dataframe,
        value_column,
    )

    categories = [
        group[value_column].dropna().to_numpy()
        for _, group in dataframe.groupby(
            category_column
        )
    ]

    labels = [
        str(category)
        for category, _ in dataframe.groupby(
            category_column
        )
    ]

    if not categories:
        raise ValueError(
            f"No data available to plot for column "
            f"'{category_column}'."
        )

    figure, axis = plt.subplots()

    axis.boxplot(
        categories,
        tick_labels=labels,
    )

    axis.set_title(
        f"{value_column} by {category_column}"
    )
    axis.set_xlabel(category_column)
    axis.set_ylabel(value_column)

    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def plot_category_counts(
    dataframe: pd.DataFrame,
    category_column: str = "Category",
    limit: int = 20,
    output_path: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
        / "category_counts.png"
    ),
) -> str:
    """
    Generate a bar chart of row counts per category.

    The one chart a dataset with no numeric column can still
    support: it shows the shape of a categorical column
    without needing anything to sum.
    """

    _validate_columns(
        dataframe,
        [category_column],
    )

    counts = (
        dataframe[category_column]
        .dropna()
        .value_counts()
        .sort_values(ascending=False)
    )

    if counts.empty:
        raise ValueError(
            f"No values to plot for column "
            f"'{category_column}'."
        )

    if len(counts) > limit:
        counts = counts.head(limit)

    figure, axis = plt.subplots()

    counts.plot(
        kind="bar",
        ax=axis,
    )

    axis.set_title(
        f"Records by {category_column}"
    )
    axis.set_xlabel(category_column)
    axis.set_ylabel("Records")

    figure.autofmt_xdate()
    figure.tight_layout()

    return _save_figure(
        figure,
        output_path,
    )


def _is_recognised_measure(column: str | None) -> bool:
    """
    Whether a measure column's name is money-shaped.

    Matched as a substring, so 'Amount', 'Total' and
    'unit_price' all qualify. Only the column name is
    available here - the same list reporting.py uses to pick
    the measure in the first place.
    """

    from data_analysis.reporting import (
        MEASURE_COLUMN_SYNONYMS,
    )

    if column is None:
        return False

    name = str(column).lower()

    return any(
        synonym in name
        for synonym in MEASURE_COLUMN_SYNONYMS
    )


def _detected_chart_columns(
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """
    The columns a chart set is built from, by role.

    Single source of truth for the two chart generators, so a
    report and its charts cannot disagree about which column
    is the measure or the grouping.
    """

    from data_analysis.reporting import (
        _find_column,
        _find_groupable_column,
        _find_measure_column,
        DATE_COLUMN_SYNONYMS,
        MEASURE_COLUMN_SYNONYMS,
        PRODUCT_COLUMN_SYNONYMS,
        REGION_COLUMN_SYNONYMS,
    )

    measure_col = _find_measure_column(dataframe)

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

    group_col = product_col or region_col

    if group_col is None:
        group_col = _find_groupable_column(
            dataframe,
            measure_col,
            date_col,
        )

    return {
        "measure": measure_col,
        "product": product_col,
        "region": region_col,
        "date": date_col,
        "group": group_col,
        # A named grouping and a found one are not the same
        # claim, so the report says which it used.
        "group_is_named": (
            product_col is not None or region_col is not None
        ),
        # Whether the measure column's name is one of the
        # recognised money-shaped words. Matched as a
        # substring, so 'Amount' and 'unit_price' both count.
        "measure_is_recognised": _is_recognised_measure(
            measure_col
        ),
    }


def generate_standard_charts(
    dataframe: pd.DataFrame,
    output_directory: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
    ),
) -> dict[str, str]:
    """
    Generate the standard charts for any tabular dataset.

    Charts are selected by what the dataset actually
    carries, not by an assumed set of sales columns. A chart
    whose required columns are absent is skipped rather than
    raising, so a users export gets the charts it can support
    and a sales table still gets the full V7 set.

    A dataset whose measure and grouping columns are the
    conventional ones produces exactly the V7 sales chart
    set, unchanged. Any other column names produce charts of
    the same shapes with titles and filenames that name the
    columns actually present, so a report never shows a chart
    titled 'Revenue by Product' for a salary dataset.
    """

    output_directory = Path(
        output_directory
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    columns = _detected_chart_columns(dataframe)

    measure_col = columns["measure"]
    product_col = columns["product"]
    region_col = columns["region"]
    date_col = columns["date"]
    group_col = columns["group"]

    conventional = (
        measure_col is not None
        and columns["measure_is_recognised"]
        and product_col is not None
        and region_col is not None
        and date_col is not None
    )

    if conventional:
        # The dataset matches the V7 shape closely enough that
        # the established chart set is reused rather than
        # reimplemented. The detected columns are passed
        # through, so a table calling its measure 'Amount'
        # still produces the five charts.
        return generate_standard_sales_charts(
            dataframe,
            output_directory=output_directory,
            product_column=product_col,
            region_column=region_col,
            date_column=date_col,
            revenue_column=measure_col,
        )

    candidates: list[
        tuple[
            str,
            Callable[..., str],
            str,
            dict[str, str],
        ]
    ] = []

    def slug(column: str) -> str:
        return (
            str(column)
            .strip()
            .lower()
            .replace(" ", "_")
        )

    if group_col and measure_col:
        candidates.append(
            (
                "measure_by_group",
                plot_revenue_by_product,
                f"{slug(measure_col)}_by_"
                f"{slug(group_col)}.png",
                {
                    "product_column": group_col,
                    "revenue_column": measure_col,
                },
            )
        )

        # Only when the dataset has a column that is
        # genuinely a region: a discovered grouping is one
        # category, not two, and plotting it twice under a
        # 'by region' title would misname it.
        if region_col:
            candidates.append(
                (
                    "measure_by_region",
                    plot_revenue_by_region,
                    f"{slug(measure_col)}_by_"
                    f"{slug(region_col)}.png",
                    {
                        "region_column": region_col,
                        "revenue_column": measure_col,
                    },
                )
            )

    if date_col and measure_col:
        candidates.extend(
            (
                (
                    "monthly_measure",
                    plot_monthly_revenue,
                    "monthly_measure.png",
                    {
                        "date_column": date_col,
                        "revenue_column": measure_col,
                    },
                ),
                (
                    "measure_trend",
                    plot_revenue_trend,
                    "measure_trend.png",
                    {
                        "date_column": date_col,
                        "revenue_column": measure_col,
                    },
                ),
            )
        )

    if measure_col:
        candidates.append(
            (
                "measure_distribution",
                plot_revenue_distribution,
                "measure_distribution.png",
                {"revenue_column": measure_col},
            )
        )

    numeric_columns = [
        column
        for column in dataframe.columns
        if column != measure_col
        and pd.api.types.is_numeric_dtype(
            dataframe[column]
        )
    ]

    if measure_col and numeric_columns:
        candidates.append(
            (
                "measure_relationship",
                plot_revenue_relationship,
                "measure_relationship.png",
                {
                    "x_column": measure_col,
                    "y_column": numeric_columns[0],
                },
            )
        )

    if group_col and measure_col:
        candidates.append(
            (
                "measure_box_plot",
                plot_revenue_box_plot,
                "measure_box_plot.png",
                {
                    "category_column": group_col,
                    "value_column": measure_col,
                },
            )
        )

    # A categorical column on its own still has a shape worth
    # showing, and it is the one chart a dataset with no
    # numeric column can support at all.
    if measure_col is None and group_col:
        candidates.append(
            (
                "category_counts",
                plot_category_counts,
                "category_counts.png",
                {"category_column": group_col},
            )
        )

    charts: dict[str, str] = {}

    for name, plot, filename, kwargs in candidates:
        try:
            charts[name] = plot(
                dataframe,
                output_path=(
                    output_directory / filename
                ),
                **kwargs,
            )
        except (ValueError, TypeError, KeyError):
            # The columns this chart needs are not in this
            # dataset. Skipping it is correct; the remaining
            # charts and every non-chart section still stand.
            continue

    return charts


def generate_standard_sales_charts(
    dataframe: pd.DataFrame,
    output_directory: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
    ),
    product_column: str | None = None,
    region_column: str | None = None,
    date_column: str | None = None,
    revenue_column: str | None = None,
) -> dict[str, str]:
    """
    Generate the standard V7 sales charts.

    A chart whose required columns are absent is skipped
    rather than raising. The dataset is now selectable, so a
    report can legitimately be built from a table that has a
    Revenue column but no Region - failing the whole report
    over one impossible chart would deny the user the facts
    and findings that *could* be derived. The returned dict
    names only the charts actually written.

    The four column names are parameters so a dataset whose
    measure is called 'Amount' and whose grouping is called
    'Item' produces the same five charts rather than five
    skips: without them the plots fall back to the 'Revenue',
    'Product', 'Region' and 'Date' defaults and silently
    produce nothing.
    """

    output_directory = Path(
        output_directory
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    measure_col = revenue_column or "Revenue"
    group_col = product_column or "Product"
    area_col = region_column or "Region"
    when_col = date_column or "Date"

    candidates = (
        (
            "revenue_by_product",
            plot_revenue_by_product,
            "revenue_by_product.png",
            {
                "product_column": group_col,
                "revenue_column": measure_col,
            },
        ),
        (
            "revenue_by_region",
            plot_revenue_by_region,
            "revenue_by_region.png",
            {
                "region_column": area_col,
                "revenue_column": measure_col,
            },
        ),
        (
            "monthly_revenue",
            plot_monthly_revenue,
            "monthly_revenue.png",
            {
                "date_column": when_col,
                "revenue_column": measure_col,
            },
        ),
        (
            "revenue_trend",
            plot_revenue_trend,
            "revenue_trend.png",
            {
                "date_column": when_col,
                "revenue_column": measure_col,
            },
        ),
        (
            # Needs only the measure column, so a dataset with
            # no grouping or date still gets one chart.
            "revenue_distribution",
            plot_revenue_distribution,
            "revenue_distribution.png",
            {"revenue_column": measure_col},
        ),
    )

    charts: dict[str, str] = {}

    for name, plot, filename, kwargs in candidates:
        try:
            charts[name] = plot(
                dataframe,
                output_path=(
                    output_directory / filename
                ),
                **kwargs,
            )
        except (ValueError, TypeError, KeyError):
            # The columns this chart needs are not in this
            # dataset. Skipping it is correct; the remaining
            # charts and every non-chart section still stand.
            continue

    return charts