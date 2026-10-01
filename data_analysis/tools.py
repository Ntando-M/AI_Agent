from __future__ import annotations

from typing import Any

import pandas as pd

from data_analysis.analyzer import (
    aggregate_dataset,
    calculate_missing_percentage,
    calculate_monthly_revenue,
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
    GetUniqueValuesInput,
    GroupByColumnInput,
    InspectDatasetInput,
    MissingPercentageInput,
    MonthlyRevenueInput,
    SortDatasetInput,
)

from data_analysis.sql_tools import (
    describe_database_table,
    execute_read_only_query,
    inspect_database,
    list_database_tables,
)

from data_analysis.sql_models import (
    DescribeTableInput,
    InspectDatabaseInput,
    ListTablesInput,
    ReadOnlySQLInput,
)


def run_inspect_dataset(
    df: pd.DataFrame,
    inputs: InspectDatasetInput,
) -> dict[str, Any]:
    return inspect_dataset(df)


def run_filter_dataset(
    df: pd.DataFrame,
    inputs: FilterDatasetInput,
) -> pd.DataFrame:
    return filter_dataset(
        df,
        inputs.column,
        inputs.value,
    )


def run_get_unique_values(
    df: pd.DataFrame,
    inputs: GetUniqueValuesInput,
) -> list[Any]:
    return get_unique_values(
        df,
        inputs.column,
    )


def run_aggregate_dataset(
    df: pd.DataFrame,
    inputs: AggregateDatasetInput,
) -> float:
    return aggregate_dataset(
        df,
        inputs.column,
        inputs.operation,
    )


def run_calculate_statistics(
    df: pd.DataFrame,
    inputs: CalculateStatisticsInput,
) -> dict[str, float]:
    return calculate_statistics(
        df,
        inputs.column,
    )


def run_group_by_column(
    df: pd.DataFrame,
    inputs: GroupByColumnInput,
) -> pd.DataFrame:
    return group_by_column(
        df,
        inputs.group_column,
        inputs.aggregation_column,
        inputs.operation,
    )


def run_sort_dataset(
    df: pd.DataFrame,
    inputs: SortDatasetInput,
) -> pd.DataFrame:
    return sort_dataset(
        df,
        inputs.column,
        inputs.ascending,
    )


def run_calculate_monthly_revenue(
    df: pd.DataFrame,
    inputs: MonthlyRevenueInput,
) -> pd.DataFrame:
    return calculate_monthly_revenue(
        df,
        inputs.date_column,
        inputs.revenue_column,
    )


def run_calculate_missing_percentage(
    df: pd.DataFrame,
    inputs: MissingPercentageInput,
) -> float:
    return calculate_missing_percentage(df)


def run_inspect_database(
    engine,
    inputs: InspectDatabaseInput,
) -> dict[str, Any]:
    return inspect_database(engine)


def run_list_tables(
    engine,
    inputs: ListTablesInput,
) -> list[str]:
    return list_database_tables(engine)


def run_describe_table(
    engine,
    inputs: DescribeTableInput,
) -> list[dict[str, Any]]:
    return describe_database_table(
        engine,
        inputs.table_name,
    )


def run_read_only_sql(
    engine,
    inputs: ReadOnlySQLInput,
) -> list[dict[str, Any]]:
    return execute_read_only_query(
        engine,
        inputs.query,
        max_rows=inputs.max_rows,
    )