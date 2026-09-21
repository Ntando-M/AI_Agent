from data_analysis.tools import (
    run_aggregate_dataset,
    run_calculate_statistics,
    run_filter_dataset,
    run_get_unique_values,
    run_group_by_column,
    run_inspect_dataset,
    run_sort_dataset,
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


TOOL_REGISTRY = {
    "inspect_dataset": {
        "function": run_inspect_dataset,
        "input_model": InspectDatasetInput,
        "description": (
            "Inspect the structure of the loaded dataset, "
            "including row count, column count, column names, "
            "data types, and missing values."
        ),
    },

    "filter_dataset": {
        "function": run_filter_dataset,
        "input_model": FilterDatasetInput,
        "description": (
            "Filter the dataset using an exact value match "
            "on a specified column."
        ),
    },

    "get_unique_values": {
        "function": run_get_unique_values,
        "input_model": UniqueValuesInput,
        "description": (
            "Return the unique non-null values from a dataset column."
        ),
    },

    "aggregate_dataset": {
        "function": run_aggregate_dataset,
        "input_model": AggregateDatasetInput,
        "description": (
            "Perform a numeric aggregation using sum, mean, "
            "min, max, or count."
        ),
    },

    "calculate_statistics": {
        "function": run_calculate_statistics,
        "input_model": CalculateStatisticsInput,
        "description": (
            "Calculate count, mean, median, minimum, maximum, "
            "and standard deviation for a numeric column."
        ),
    },

    "group_by_column": {
        "function": run_group_by_column,
        "input_model": GroupByColumnInput,
        "description": (
            "Group the dataset by one column and aggregate "
            "a numeric column."
        ),
    },

    "sort_dataset": {
        "function": run_sort_dataset,
        "input_model": SortDatasetInput,
        "description": (
            "Sort the dataset by a specified column."
        ),
    },
}