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


class AnalysisStep(BaseModel):
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AnalysisPlan(BaseModel):
    steps: list[AnalysisStep] = Field(min_length=1)