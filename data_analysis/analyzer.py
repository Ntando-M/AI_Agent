from __future__ import annotations

from typing import Any

import pandas as pd


def inspect_dataset(df: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Expected a Pandas DataFrame")

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
        "dtypes": {
            column: str(dtype)
            for column, dtype in df.dtypes.items()
        },
        "missing_values": df.isna().sum().to_dict(),
    }


def _normalise_label(value: Any) -> str:
    """
    Reduce a category label to a comparable form.

    Lowercases, trims surrounding whitespace, and strips a
    trailing plural 's' so that a query for "laptops" can be
    matched against a stored "Laptop".
    """

    text = str(value).strip().lower()

    if len(text) > 1 and text.endswith("s"):
        return text[:-1]

    return text


def resolve_filter_value(
    df: pd.DataFrame,
    column: str,
    value: Any,
) -> Any:
    """
    Resolve a requested value against the labels actually
    present in a column.

    A user asks about "laptops" and the column stores "Laptop".
    Matching the request literally returns an empty frame, which
    downstream reads as "no data" rather than "you named it
    slightly differently". Resolution is attempted in order:

    1. exact match on the stored label
    2. case-insensitive match
    3. singular/plural match

    Numeric columns are compared numerically, so a requested "5"
    matches a stored 5.

    Returns the stored value to filter on, or the original value
    when nothing matches, so an unresolvable filter still yields
    an empty frame rather than silently matching the wrong label.
    """

    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    series = df[column]

    if pd.api.types.is_numeric_dtype(series):
        try:
            return type(series.dropna().iloc[0])(value)
        except (ValueError, TypeError, IndexError):
            return value

    labels = series.dropna().unique().tolist()

    if value in labels:
        return value

    requested = _normalise_label(value)

    # Case-insensitive, ignoring whitespace and plural form.
    normalised = {
        _normalise_label(label): label
        for label in labels
    }

    if requested in normalised:
        return normalised[requested]

    return value


def filter_dataset(
    df: pd.DataFrame,
    column: str,
    value: Any,
) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    resolved = resolve_filter_value(
        df,
        column,
        value,
    )

    return df[df[column] == resolved].copy()


def get_unique_values(
    df: pd.DataFrame,
    column: str,
) -> list[Any]:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    return df[column].dropna().unique().tolist()


def aggregate_dataset(
    df: pd.DataFrame,
    column: str,
    operation: str,
) -> float:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    if operation not in {
        "sum",
        "mean",
        "min",
        "max",
    }:
        raise ValueError(
            f"Unsupported aggregation operation: {operation}"
        )

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(
            f"Column '{column}' must be numeric"
        )

    if df.empty:
        raise ValueError(
            "Cannot aggregate: the dataset has no rows. "
            "A filter probably matched nothing."
        )

    operations = {
        "sum": df[column].sum,
        "mean": df[column].mean,
        "min": df[column].min,
        "max": df[column].max,
    }

    return float(operations[operation]())


def calculate_statistics(
    df: pd.DataFrame,
    column: str,
) -> dict[str, float]:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(
            f"Column '{column}' must be numeric"
        )

    if df.empty:
        raise ValueError(
            "Cannot calculate statistics: the dataset has no "
            "rows. A filter probably matched nothing."
        )

    series = df[column].dropna()

    return {
        "count": float(series.count()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "min": float(series.min()),
        "max": float(series.max()),
        "standard_deviation": float(series.std()),
    }


def group_by_column(
    df: pd.DataFrame,
    group_column: str,
    aggregation_column: str,
    operation: str = "sum",
) -> pd.DataFrame:
    if group_column not in df.columns:
        raise ValueError(
            f"Column '{group_column}' not found"
        )

    if aggregation_column not in df.columns:
        raise ValueError(
            f"Column '{aggregation_column}' not found"
        )

    if operation not in {
        "sum",
        "mean",
        "min",
        "max",
    }:
        raise ValueError(
            f"Unsupported aggregation operation: {operation}"
        )

    if not pd.api.types.is_numeric_dtype(
        df[aggregation_column]
    ):
        raise TypeError(
            f"Column '{aggregation_column}' must be numeric"
        )

    if df.empty:
        raise ValueError(
            "Cannot group: the dataset has no rows. "
            "A filter probably matched nothing."
        )

    result = (
        df.groupby(group_column, as_index=False)
        .agg(
            **{
                aggregation_column: (
                    aggregation_column,
                    operation,
                )
            }
        )
    )

    return result


def sort_dataset(
    df: pd.DataFrame,
    column: str,
    ascending: bool = True,
) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    return df.sort_values(
        by=column,
        ascending=ascending,
    ).copy()


def calculate_monthly_revenue(
    df: pd.DataFrame,
    date_column: str,
    revenue_column: str,
) -> pd.DataFrame:
    if date_column not in df.columns:
        raise ValueError(
            f"Column '{date_column}' not found"
        )

    if revenue_column not in df.columns:
        raise ValueError(
            f"Column '{revenue_column}' not found"
        )

    if not pd.api.types.is_numeric_dtype(
        df[revenue_column]
    ):
        raise TypeError(
            f"Column '{revenue_column}' must be numeric"
        )

    if df.empty:
        raise ValueError(
            "Cannot calculate monthly revenue: the dataset "
            "has no rows. A filter probably matched nothing."
        )

    dates = pd.to_datetime(
        df[date_column],
        errors="coerce",
    )

    valid_dates = dates.notna()

    working_df = df.loc[
        valid_dates,
        [revenue_column],
    ].copy()

    working_df["Date"] = dates.loc[valid_dates]

    working_df["Month"] = (
        working_df["Date"]
        .dt.to_period("M")
        .astype(str)
    )

    result = (
        working_df
        .groupby("Month", as_index=False)[revenue_column]
        .sum()
    )

    return result


def calculate_missing_percentage(
    df: pd.DataFrame,
) -> float:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Expected a Pandas DataFrame")

    total_cells = df.shape[0] * df.shape[1]

    if total_cells == 0:
        return 0.0

    missing_cells = int(df.isna().sum().sum())

    return float(
        (missing_cells / total_cells) * 100
    )