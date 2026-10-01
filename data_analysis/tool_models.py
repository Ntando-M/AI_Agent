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
    pass


class FilterDatasetInput(BaseModel):
    column: str = Field(min_length=1)
    value: Any


class GetUniqueValuesInput(BaseModel):
    column: str = Field(min_length=1)


class AggregateDatasetInput(BaseModel):
    column: str = Field(min_length=1)
    operation: AggregationOperation


class CalculateStatisticsInput(BaseModel):
    column: str = Field(min_length=1)


class GroupByColumnInput(BaseModel):
    group_column: str = Field(min_length=1)
    aggregation_column: str = Field(min_length=1)
    operation: AggregationOperation = "sum"


class SortDatasetInput(BaseModel):
    column: str = Field(min_length=1)
    ascending: bool = True


class MonthlyRevenueInput(BaseModel):
    date_column: str = Field(min_length=1)
    revenue_column: str = Field(min_length=1)


class MissingPercentageInput(BaseModel):
    pass


class ChartByCategoryInput(BaseModel):
    """
    Input for a bar chart comparing a measure across categories.
    """

    category_column: str = Field(
        min_length=1,
        description=(
            "The categorical column to group by, "
            "for example Product or Region"
        ),
    )

    value_column: str = Field(
        min_length=1,
        description=(
            "The numeric column to aggregate, "
            "for example Revenue"
        ),
    )


class TimeSeriesChartInput(BaseModel):
    """
    Input for a line chart over time.
    """

    date_column: str = Field(
        min_length=1,
        description=(
            "The column containing dates"
        ),
    )

    value_column: str = Field(
        min_length=1,
        description=(
            "The numeric column to plot, "
            "for example Revenue"
        ),
    )


class DistributionChartInput(BaseModel):
    """
    Input for a histogram of a numeric column.
    """

    value_column: str = Field(
        min_length=1,
        description=(
            "The numeric column whose distribution "
            "should be plotted"
        ),
    )

    bins: int = Field(
        default=10,
        ge=2,
        le=100,
        description="Number of histogram bins",
    )


class RelationshipChartInput(BaseModel):
    """
    Input for a scatter plot between two numeric columns.
    """

    x_column: str = Field(
        min_length=1,
        description=(
            "The numeric column for the horizontal axis"
        ),
    )

    y_column: str = Field(
        min_length=1,
        description=(
            "The numeric column for the vertical axis"
        ),
    )


class BoxPlotInput(BaseModel):
    """
    Input for a box plot of a measure per category.
    """

    category_column: str = Field(
        min_length=1,
        description=(
            "The categorical column that splits the data, "
            "for example Product"
        ),
    )

    value_column: str = Field(
        min_length=1,
        description=(
            "The numeric column to summarise, "
            "for example Revenue"
        ),
    )


class AnalysisStep(BaseModel):
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AnalysisPlan(BaseModel):
    steps: list[AnalysisStep] = Field(min_length=1)