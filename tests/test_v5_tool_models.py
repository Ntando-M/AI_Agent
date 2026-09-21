import pytest
from pydantic import ValidationError

from data_analysis.tool_models import (
    InspectDatasetInput,
    FilterDatasetInput,
    GetUniqueValuesInput,
    AggregateDatasetInput,
    CalculateStatisticsInput,
    GroupByColumnInput,
    SortDatasetInput,
)


def test_inspect_dataset_input():
    data = InspectDatasetInput()

    assert data is not None


def test_filter_dataset_input():
    data = FilterDatasetInput(
        column="Product",
        value="Laptop",
    )

    assert data.column == "Product"
    assert data.value == "Laptop"


def test_filter_dataset_requires_column():
    with pytest.raises(ValidationError):
        FilterDatasetInput(
            value="Laptop",
        )


def test_get_unique_values_input():
    data = GetUniqueValuesInput(
        column="Product",
    )

    assert data.column == "Product"


def test_get_unique_values_requires_column():
    with pytest.raises(ValidationError):
        GetUniqueValuesInput()


def test_aggregate_dataset_input():
    data = AggregateDatasetInput(
        column="Revenue",
        operation="sum",
    )

    assert data.column == "Revenue"
    assert data.operation == "sum"


def test_aggregate_dataset_rejects_invalid_operation():
    with pytest.raises(ValidationError):
        AggregateDatasetInput(
            column="Revenue",
            operation="invalid",
        )


def test_calculate_statistics_input():
    data = CalculateStatisticsInput(
        column="Revenue",
    )

    assert data.column == "Revenue"


def test_group_by_column_input():
    data = GroupByColumnInput(
        group_column="Product",
        aggregation_column="Revenue",
        operation="sum",
    )

    assert data.group_column == "Product"
    assert data.aggregation_column == "Revenue"
    assert data.operation == "sum"


def test_group_by_column_default_operation():
    data = GroupByColumnInput(
        group_column="Product",
        aggregation_column="Revenue",
    )

    assert data.operation == "sum"


def test_sort_dataset_input():
    data = SortDatasetInput(
        column="Revenue",
        ascending=False,
    )

    assert data.column == "Revenue"
    assert data.ascending is False


def test_sort_dataset_default_ascending():
    data = SortDatasetInput(
        column="Revenue",
    )

    assert data.ascending is True