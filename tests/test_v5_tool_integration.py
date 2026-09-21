import pandas as pd

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


DATASET_PATH = "data/sample_sales.xlsx"


def test_filter_tool_input_to_dataframe():
    df = pd.read_excel(DATASET_PATH)

    tool_input = FilterDatasetInput(
        column="Product",
        value="Laptop",
    )

    result = filter_dataset(
        df,
        tool_input.column,
        tool_input.value,
    )

    assert len(result) == 4


def test_unique_values_tool_input_to_dataframe():
    df = pd.read_excel(DATASET_PATH)

    tool_input = GetUniqueValuesInput(
        column="Product",
    )

    result = get_unique_values(
        df,
        tool_input.column,
    )

    assert set(result) == {
        "Laptop",
        "Monitor",
        "Keyboard",
    }


def test_aggregate_tool_input_to_dataframe():
    df = pd.read_excel(DATASET_PATH)

    tool_input = AggregateDatasetInput(
        column="Revenue",
        operation="sum",
    )

    result = aggregate_dataset(
        df,
        tool_input.column,
        tool_input.operation,
    )

    assert result == 274000.0


def test_group_by_tool_input_to_dataframe():
    df = pd.read_excel(DATASET_PATH)

    tool_input = GroupByColumnInput(
        group_column="Product",
        aggregation_column="Revenue",
        operation="sum",
    )

    result = group_by_column(
        df,
        tool_input.group_column,
        tool_input.aggregation_column,
        tool_input.operation,
    )

    totals = dict(
        zip(
            result["Product"],
            result["Revenue"],
        )
    )

    assert totals == {
        "Laptop": 210000.0,
        "Monitor": 42000.0,
        "Keyboard": 22000.0,
    }


def test_sort_tool_input_to_dataframe():
    df = pd.read_excel(DATASET_PATH)

    tool_input = SortDatasetInput(
        column="Revenue",
        ascending=False,
    )

    result = sort_dataset(
        df,
        tool_input.column,
        tool_input.ascending,
    )

    assert result.iloc[0]["Revenue"] == 75000
    assert result.iloc[-1]["Revenue"] == 10000