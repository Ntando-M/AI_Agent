import pandas as pd
import pytest

from data_analysis.analyzer import (
    aggregate_dataset,
    filter_dataset,
    get_unique_values,
    group_by_column,
    sort_dataset,
)

from data_analysis.tool_models import (
    AggregateDatasetInput,
    FilterDatasetInput,
    GetUniqueValuesInput,
    GroupByColumnInput,
    SortDatasetInput,
)


@pytest.fixture
def sales_dataframe():
    return pd.DataFrame(
        {
            "Product": [
                "Laptop",
                "Monitor",
                "Laptop",
                "Keyboard",
                "Monitor",
                "Laptop",
                "Keyboard",
                "Laptop",
            ],
            "Region": [
                "Gauteng",
                "Western Cape",
                "Gauteng",
                "KwaZulu-Natal",
                "Gauteng",
                "Western Cape",
                "Gauteng",
                "KwaZulu-Natal",
            ],
            "Revenue": [
                75000,
                24000,
                45000,
                12000,
                18000,
                60000,
                10000,
                30000,
            ],
        }
    )


def test_filter_tool_with_pydantic_input(sales_dataframe):
    input_data = FilterDatasetInput(
        column="Product",
        value="Laptop",
    )

    result = filter_dataset(
        sales_dataframe,
        input_data.column,
        input_data.value,
    )

    assert len(result) == 4
    assert result["Product"].tolist() == [
        "Laptop",
        "Laptop",
        "Laptop",
        "Laptop",
    ]


def test_unique_values_tool_with_pydantic_input(sales_dataframe):
    input_data = GetUniqueValuesInput(
        column="Product",
    )

    result = get_unique_values(
        sales_dataframe,
        input_data.column,
    )

    assert set(result) == {
        "Laptop",
        "Monitor",
        "Keyboard",
    }


def test_aggregate_tool_with_pydantic_input(sales_dataframe):
    input_data = AggregateDatasetInput(
        column="Revenue",
        operation="sum",
    )

    result = aggregate_dataset(
        sales_dataframe,
        input_data.column,
        input_data.operation,
    )

    assert result == 274000.0


def test_group_by_tool_with_pydantic_input(sales_dataframe):
    input_data = GroupByColumnInput(
        group_column="Product",
        aggregation_column="Revenue",
        operation="sum",
    )

    result = group_by_column(
        sales_dataframe,
        input_data.group_column,
        input_data.aggregation_column,
        input_data.operation,
    )

    result_dict = dict(
        zip(
            result["Product"],
            result["Revenue"],
        )
    )

    assert result_dict == {
        "Laptop": 210000,
        "Monitor": 42000,
        "Keyboard": 22000,
    }


def test_sort_tool_with_pydantic_input(sales_dataframe):
    input_data = SortDatasetInput(
        column="Revenue",
        ascending=False,
    )

    result = sort_dataset(
        sales_dataframe,
        input_data.column,
        input_data.ascending,
    )

    assert result.iloc[0]["Revenue"] == 75000
    assert result.iloc[-1]["Revenue"] == 10000