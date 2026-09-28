from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_OUTPUT_DIRECTORY = Path("charts")


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


def generate_standard_sales_charts(
    dataframe: pd.DataFrame,
    output_directory: str | Path = (
        DEFAULT_OUTPUT_DIRECTORY
    ),
) -> dict[str, str]:
    """
    Generate the standard V7 sales charts.
    """

    output_directory = Path(
        output_directory
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return {
        "revenue_by_product": plot_revenue_by_product(
            dataframe,
            output_path=(
                output_directory
                / "revenue_by_product.png"
            ),
        ),
        "revenue_by_region": plot_revenue_by_region(
            dataframe,
            output_path=(
                output_directory
                / "revenue_by_region.png"
            ),
        ),
        "monthly_revenue": plot_monthly_revenue(
            dataframe,
            output_path=(
                output_directory
                / "monthly_revenue.png"
            ),
        ),
        "revenue_trend": plot_revenue_trend(
            dataframe,
            output_path=(
                output_directory
                / "revenue_trend.png"
            ),
        ),
    }