"""
Tool registries for the AI Data Analyst.

Tools are grouped by the data source they operate on:

DATAFRAME_TOOL_REGISTRY
    Tools whose first argument is a Pandas DataFrame. These
    operate on the current working dataset.

SQL_TOOL_REGISTRY
    Tools whose first argument is a SQLAlchemy Engine. These
    operate against the analytical database.

Keeping the two registries separate makes the data source an
explicit property of a tool rather than an accident of argument
position. The agent uses this to dispatch each planned step to
the correct executor.
"""

from data_analysis.tool_models import (
    AggregateDatasetInput,
    BoxPlotInput,
    CalculateStatisticsInput,
    ChartByCategoryInput,
    DistributionChartInput,
    FilterDatasetInput,
    GetUniqueValuesInput,
    GroupByColumnInput,
    InspectDatasetInput,
    MissingPercentageInput,
    MonthlyRevenueInput,
    RelationshipChartInput,
    SortDatasetInput,
    TimeSeriesChartInput,
)

from data_analysis.tools import (
    run_aggregate_dataset,
    run_calculate_missing_percentage,
    run_calculate_monthly_revenue,
    run_calculate_statistics,
    run_chart_box_plot,
    run_chart_distribution,
    run_chart_monthly_revenue,
    run_chart_revenue_by_category,
    run_chart_revenue_over_time,
    run_chart_relationship,
    run_filter_dataset,
    run_get_unique_values,
    run_group_by_column,
    run_inspect_dataset,
    run_sort_dataset,
)

from data_analysis.sql_models import (
    DescribeTableInput,
    InspectDatabaseInput,
    ListTablesInput,
    ReadOnlySQLInput,
)

from data_analysis.tools import (
    run_describe_table,
    run_inspect_database,
    run_list_tables,
    run_read_only_sql,
)

DATAFRAME_TOOL_REGISTRY = {
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
    "chart_revenue_by_category": {
        "function": run_chart_revenue_by_category,
        "input_model": ChartByCategoryInput,
        "description": (
            "Generate a bar chart comparing a numeric measure "
            "across the categories of a column, for example "
            "total revenue by product or by region. "
            "Use this when the user asks to compare, rank or "
            "show totals per category."
        ),
    },
    "chart_revenue_over_time": {
        "function": run_chart_revenue_over_time,
        "input_model": TimeSeriesChartInput,
        "description": (
            "Generate a line chart showing a numeric measure "
            "over time in chronological order. Use this when "
            "the user asks for a trend or how a value changed "
            "over a period."
        ),
    },
    "chart_monthly_revenue": {
        "function": run_chart_monthly_revenue,
        "input_model": TimeSeriesChartInput,
        "description": (
            "Generate a line chart of a numeric measure "
            "totalled per calendar month. Use this when the "
            "user asks for a monthly breakdown or trend."
        ),
    },
    "chart_distribution": {
        "function": run_chart_distribution,
        "input_model": DistributionChartInput,
        "description": (
            "Generate a histogram showing the distribution of "
            "a numeric column. Use this when the user asks about "
            "spread, distribution or how values are dispersed."
        ),
    },
    "chart_relationship": {
        "function": run_chart_relationship,
        "input_model": RelationshipChartInput,
        "description": (
            "Generate a scatter plot showing the relationship "
            "between two numeric columns. Use this when the user "
            "asks about correlation or how one numeric measure "
            "varies against another."
        ),
    },
    "chart_box_plot": {
        "function": run_chart_box_plot,
        "input_model": BoxPlotInput,
        "description": (
            "Generate a box plot showing the distribution of a "
            "numeric measure per category, which exposes "
            "outliers. Use this when the user asks about "
            "variability or outliers within groups."
        ),
    },
}


SQL_TOOL_REGISTRY = {
    "inspect_database": {
        "function": run_inspect_database,
    "input_model": InspectDatabaseInput,
    "description": (
        "Inspect the database and return the available "
        "tables."
        ),
    },

    "list_tables": {
        "function": run_list_tables,
        "input_model": ListTablesInput,
        "description": (
            "List all tables available in the analytical database."
        ),
    },

    "describe_table": {
        "function": run_describe_table,
        "input_model": DescribeTableInput,
        "description": (
            "Inspect the columns, data types, nullability, "
            "and primary-key information of a database table."
        ),
    },

    "execute_read_only_sql": {
        "function": run_read_only_sql,
        "input_model": ReadOnlySQLInput,
        "description": (
            "Execute a controlled read-only SELECT or WITH SQL "
            "query against the analytical database. "
            "INSERT, UPDATE, DELETE, DROP, ALTER, CREATE and "
            "other modifying operations are prohibited."
        ),
    },
}


def get_dataframe_tool_registry() -> dict:
    """
    Return the tools that operate on the current dataset.
    """

    return DATAFRAME_TOOL_REGISTRY


def get_sql_tool_registry() -> dict:
    """
    Return the tools that operate on the analytical database.
    """

    return SQL_TOOL_REGISTRY


def get_tool_registry() -> dict:
    """
    Return every available tool, keyed by tool name.

    Retained so callers that need the complete toolset, such as
    prompt building, do not have to merge the two registries.
    """

    combined = {}

    combined.update(
        DATAFRAME_TOOL_REGISTRY
    )

    combined.update(
        SQL_TOOL_REGISTRY
    )

    return combined


def get_tool_data_source(tool_name: str) -> str:
    """
    Return the data source a tool operates on.

    Returns:
        "dataframe"
        "database"

    Raises:
        ValueError: If the tool is not registered.
    """

    if tool_name in DATAFRAME_TOOL_REGISTRY:
        return "dataframe"

    if tool_name in SQL_TOOL_REGISTRY:
        return "database"

    raise ValueError(
        f"Unknown analysis tool: {tool_name}"
    )