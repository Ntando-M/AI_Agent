from typing import Any

import pandas as pd


def _detect_date_columns(
    df: pd.DataFrame,
    categorical_columns: list[str],
) -> list[str]:
    """
    Detect columns that are already datetime columns or appear
    to contain date values.
    """

    date_columns = [
        column
        for column in df.select_dtypes(
            include=["datetime", "datetimetz"]
        ).columns
    ]

    for column in categorical_columns:
        if column in date_columns:
            continue

        converted_values = pd.to_datetime(
            df[column],
            errors="coerce",
        )

        valid_dates = converted_values.notna().sum()

        if len(df) > 0 and valid_dates / len(df) > 0.5:
            date_columns.append(column)

    return date_columns


def profile_dataframe(
    df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Generate deterministic metadata for a Pandas DataFrame.

    The function does not use an LLM.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "Expected a Pandas DataFrame."
        )

    numeric_columns = (
        df.select_dtypes(include=["number"])
        .columns
        .tolist()
    )

    categorical_columns = (
        df.select_dtypes(
            include=["object", "category", "string"]
        )
        .columns
        .tolist()
    )

    date_columns = _detect_date_columns(
        df,
        categorical_columns,
    )

    if numeric_columns:
        numeric_summary = (
            df[numeric_columns]
            .describe()
            .to_dict()
        )
    else:
        numeric_summary = {}

    return {
        "rows": int(len(df)),
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": df.isna().sum().to_dict(),
        "numeric_summary": numeric_summary,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "date_columns": date_columns,
    }