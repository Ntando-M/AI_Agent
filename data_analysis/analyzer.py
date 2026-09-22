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


def filter_dataset(
    df: pd.DataFrame,
    column: str,
    value: Any,
) -> pd.DataFrame:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found"
        )

    return df[df[column] == value].copy()


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