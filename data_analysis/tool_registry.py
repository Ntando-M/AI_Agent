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

from data_analysis.tools import (
    run_aggregate_dataset,
    run_calculate_missing_percentage,
    run_calculate_monthly_revenue,
    run_calculate_statistics,
    run_filter_dataset,
    run_get_unique_values,
    run_group_by_column,
    run_inspect_dataset,
    run_sort_dataset,
)


TOOL_REGISTRY = {
    "inspect_dataset": {
        "function": run_inspect_dataset,
        "input_model": InspectDatasetInput,
        "description": (
            "Inspect dataset structure, row count, columns, "
            "data types, and missing values."
        ),
    },
    "filter_dataset": {
        "function": run_filter_dataset,
        "input_model": FilterDatasetInput,
        "description": (
            "Filter the current dataset using an exact column value."
        ),
    },
    "get_unique_values": {
        "function": run_get_unique_values,
        "input_model": GetUniqueValuesInput,
        "description": (
            "Return the unique non-null values in a column."
        ),
    },
    "aggregate_dataset": {
        "function": run_aggregate_dataset,
        "input_model": AggregateDatasetInput,
        "description": (
            "Calculate sum, mean, minimum, maximum, "
            "or count for a numeric column."
        ),
    },
    "calculate_statistics": {
        "function": run_calculate_statistics,
        "input_model": CalculateStatisticsInput,
        "description": (
            "Calculate count, mean, median, minimum, "
            "maximum, and standard deviation."
        ),
    },
    "group_by_column": {
        "function": run_group_by_column,
        "input_model": GroupByColumnInput,
        "description": (
            "Group the dataset by one column and aggregate "
            "another column."
        ),
    },
    "sort_dataset": {
        "function": run_sort_dataset,
        "input_model": SortDatasetInput,
        "description": (
            "Sort the current dataset by a selected column."
        ),
    },
    "calculate_monthly_revenue": {
        "function": run_calculate_monthly_revenue,
        "input_model": MonthlyRevenueInput,
        "description": (
            "Calculate revenue totals grouped by calendar month."
        ),
    },
    "calculate_missing_percentage": {
        "function": run_calculate_missing_percentage,
        "input_model": MissingPercentageInput,
        "description": (
            "Calculate the percentage of rows containing "
            "at least one missing value."
        ),
    },
}


def get_tool_registry() -> dict:
    return TOOL_REGISTRY