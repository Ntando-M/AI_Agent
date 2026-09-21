from typing import Any, Literal

from pydantic import BaseModel, Field


AggregationOperation = Literal[
    "sum",
    "mean",
    "min",
    "max",
    "count",
]


class InspectDatasetInput(BaseModel):
    """
    Input model for inspect_dataset.
    """

    pass


class FilterDatasetInput(BaseModel):
    """
    Input model for filter_dataset.
    """

    column: str = Field(
        min_length=1,
        description="Column to filter.",
    )

    value: Any = Field(
        description="Exact value to match.",
    )


class GetUniqueValuesInput(BaseModel):
    """
    Input model for get_unique_values.
    """

    column: str = Field(
        min_length=1,
        description="Column for which unique values should be returned.",
    )


class AggregateDatasetInput(BaseModel):
    """
    Input model for aggregate_dataset.
    """

    column: str = Field(
        min_length=1,
        description="Numeric column to aggregate.",
    )

    operation: AggregationOperation = Field(
        description="Aggregation operation to perform.",
    )


class CalculateStatisticsInput(BaseModel):
    """
    Input model for calculate_statistics.
    """

    column: str = Field(
        min_length=1,
        description="Numeric column for which statistics should be calculated.",
    )


class GroupByColumnInput(BaseModel):
    """
    Input model for group_by_column.
    """

    group_column: str = Field(
        min_length=1,
        description="Column used to create groups.",
    )

    aggregation_column: str = Field(
        min_length=1,
        description="Numeric column to aggregate.",
    )

    operation: AggregationOperation = Field(
        default="sum",
        description="Aggregation operation to perform.",
    )


class SortDatasetInput(BaseModel):
    """
    Input model for sort_dataset.
    """

    column: str = Field(
        min_length=1,
        description="Column used for sorting.",
    )

    ascending: bool = Field(
        default=True,
        description="Whether to sort in ascending order.",
    )