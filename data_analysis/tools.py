from typing import Any

import pandas as pd

from data_analysis.analyzer import (
    aggregate_dataset,
    calculate_statistics,
    filter_dataset,
    get_unique_values,
    group_by_column,
    inspect_dataset,
    sort_dataset,
)

from data_analysis.tool_models import (
    AggregateDatasetInput,
    CalculateStatisticsInput,
    FilterDatasetInput,
    GroupByColumnInput,
    InspectDatasetInput,
    SortDatasetInput,
    UniqueValuesInput,
)


def run_inspect_dataset(
    df: pd.DataFrame,
    inputs: InspectDatasetInput,
) -> dict[str, Any]:
    """
    Controlled wrapper for inspect_dataset.
    """

    return inspect_dataset(df)


def run_filter_dataset(
    df: pd.DataFrame,
    inputs: FilterDatasetInput,
) -> pd.DataFrame:
    """
    Controlled wrapper for filter_dataset.
    """

    return filter_dataset(
        df,
        column=inputs.column,
        value=inputs.value,
    )


def run_get_unique_values(
    df: pd.DataFrame,
    inputs: UniqueValuesInput,
) -> list[Any]:
    """
    Controlled wrapper for get_unique_values.
    """

    return get_unique_values(
        df,
        column=inputs.column,
    )


def run_aggregate_dataset(
    df: pd.DataFrame,
    inputs: AggregateDatasetInput,
) -> float:
    """
    Controlled wrapper for aggregate_dataset.
    """

    return aggregate_dataset(
        df,
        column=inputs.column,
        operation=inputs.operation,
    )


def run_calculate_statistics(
    df: pd.DataFrame,
    inputs: CalculateStatisticsInput,
) -> dict[str, float]:
    """
    Controlled wrapper for calculate_statistics.
    """

    return calculate_statistics(
        df,
        column=inputs.column,
    )


def run_group_by_column(
    df: pd.DataFrame,
    inputs: GroupByColumnInput,
) -> pd.DataFrame:
    """
    Controlled wrapper for group_by_column.
    """

    return group_by_column(
        df,
        group_column=inputs.group_column,
        aggregation_column=inputs.aggregation_column,
        operation=inputs.operation,
    )


def run_sort_dataset(
    df: pd.DataFrame,
    inputs: SortDatasetInput,
) -> pd.DataFrame:
    """
    Controlled wrapper for sort_dataset.
    """

    return sort_dataset(
        df,
        column=inputs.column,
        ascending=inputs.ascending,
    )