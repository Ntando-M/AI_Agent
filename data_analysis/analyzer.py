from typing import Any

import pandas as pd


def _validate_dataframe(df: pd.DataFrame) -> None:
    """
    Validate that the supplied object is a Pandas DataFrame.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "Expected a Pandas DataFrame."
        )


def _validate_column(
    df: pd.DataFrame,
    column: str,
) -> None:
    """
    Validate that a column exists in the DataFrame.
    """

    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found in dataset. "
            f"Available columns: {list(df.columns)}"
        )


def inspect_dataset(
    df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Inspect the basic structure of a dataset.

    Returns deterministic metadata about the DataFrame.
    """

    _validate_dataframe(df)

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": df.isna().sum().to_dict(),
    }


def filter_dataset(
    df: pd.DataFrame,
    column: str,
    value: Any,
) -> pd.DataFrame:
    """
    Filter a DataFrame using an exact column-value match.

    Example:
        filter_dataset(df, "Product", "Laptop")
    """

    _validate_dataframe(df)
    _validate_column(df, column)

    return df[df[column] == value].copy()


def get_unique_values(
    df: pd.DataFrame,
    column: str,
) -> list[Any]:
    """
    Return the unique non-null values from a dataset column.
    """

    _validate_dataframe(df)
    _validate_column(df, column)

    return df[column].dropna().unique().tolist()


def aggregate_dataset(
    df: pd.DataFrame,
    column: str,
    operation: str,
) -> float:
    """
    Perform a deterministic aggregation on a numeric column.

    Supported operations:
        sum
        mean
        min
        max
        count

    Example:
        aggregate_dataset(df, "Revenue", "sum")
    """

    _validate_dataframe(df)
    _validate_column(df, column)

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(
            f"Column '{column}' must be numeric for aggregation."
        )

    supported_operations = {
        "sum",
        "mean",
        "min",
        "max",
        "count",
    }

    operation = operation.lower()

    if operation not in supported_operations:
        raise ValueError(
            f"Unsupported aggregation operation: '{operation}'. "
            f"Supported operations: {sorted(supported_operations)}"
        )

    result = getattr(df[column], operation)()

    return float(result)


def calculate_statistics(
    df: pd.DataFrame,
    column: str,
) -> dict[str, float]:
    """
    Calculate deterministic descriptive statistics for a numeric column.

    Returns:
        count
        mean
        median
        min
        max
        standard_deviation
    """

    _validate_dataframe(df)
    _validate_column(df, column)

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(
            f"Column '{column}' must be numeric for statistics."
        )

    series = df[column].dropna()

    if series.empty:
        raise ValueError(
            f"Column '{column}' contains no valid numeric values."
        )

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
    """
    Group a dataset by one column and aggregate another column.

    Supported operations:
        sum
        mean
        min
        max
        count

    Example:
        group_by_column(
            df,
            "Product",
            "Revenue",
            "sum",
        )
    """

    _validate_dataframe(df)
    _validate_column(df, group_column)
    _validate_column(df, aggregation_column)

    if not pd.api.types.is_numeric_dtype(df[aggregation_column]):
        raise TypeError(
            f"Column '{aggregation_column}' must be numeric for grouping."
        )

    supported_operations = {
        "sum",
        "mean",
        "min",
        "max",
        "count",
    }

    operation = operation.lower()

    if operation not in supported_operations:
        raise ValueError(
            f"Unsupported aggregation operation: '{operation}'. "
            f"Supported operations: {sorted(supported_operations)}"
        )

    result = (
        df.groupby(group_column, dropna=False)[aggregation_column]
        .agg(operation)
        .reset_index()
    )

    return result


def sort_dataset(
    df: pd.DataFrame,
    column: str,
    ascending: bool = True,
) -> pd.DataFrame:
    """
    Sort a dataset by a specified column.

    The original DataFrame is not modified.

    Example:
        sort_dataset(df, "Revenue", ascending=False)
    """

    _validate_dataframe(df)
    _validate_column(df, column)

    return df.sort_values(
        by=column,
        ascending=ascending,
    ).copy()