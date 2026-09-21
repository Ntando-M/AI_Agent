import pandas as pd
import pytest

from data_analysis.analyzer import (
    aggregate_dataset,
    calculate_statistics,
    group_by_column,
    sort_dataset,
)


DATASET_PATH = "data/sample_sales.xlsx"


@pytest.fixture
def sales_dataframe():
    return pd.read_excel(DATASET_PATH)


def test_aggregate_revenue_sum(sales_dataframe):
    result = aggregate_dataset(
        sales_dataframe,
        "Revenue",
        "sum",
    )

    assert result == 274000.0


def test_aggregate_revenue_mean(sales_dataframe):
    result = aggregate_dataset(
        sales_dataframe,
        "Revenue",
        "mean",
    )

    assert result == 34250.0


def test_aggregate_revenue_max(sales_dataframe):
    result = aggregate_dataset(
        sales_dataframe,
        "Revenue",
        "max",
    )

    assert result == 75000.0


def test_aggregate_revenue_min(sales_dataframe):
    result = aggregate_dataset(
        sales_dataframe,
        "Revenue",
        "min",
    )

    assert result == 10000.0


def test_aggregate_invalid_operation(sales_dataframe):
    with pytest.raises(
        ValueError,
        match="Unsupported aggregation operation",
    ):
        aggregate_dataset(
            sales_dataframe,
            "Revenue",
            "invalid",
        )


def test_calculate_revenue_statistics(sales_dataframe):
    result = calculate_statistics(
        sales_dataframe,
        "Revenue",
    )

    assert result["count"] == 8.0
    assert result["mean"] == 34250.0
    assert result["median"] == 27000.0
    assert result["min"] == 10000.0
    assert result["max"] == 75000.0

    assert result["standard_deviation"] == pytest.approx(
    23632.604596,
    rel=1e-6,
)


def test_calculate_statistics_invalid_column(sales_dataframe):
    with pytest.raises(
        ValueError,
        match="Column 'InvalidColumn' not found",
    ):
        calculate_statistics(
            sales_dataframe,
            "InvalidColumn",
        )


def test_calculate_statistics_non_numeric_column(sales_dataframe):
    with pytest.raises(
        TypeError,
        match="must be numeric",
    ):
        calculate_statistics(
            sales_dataframe,
            "Product",
        )


def test_group_by_product_revenue(sales_dataframe):
    result = group_by_column(
        sales_dataframe,
        "Product",
        "Revenue",
        "sum",
    )

    result = result.sort_values("Product")

    expected = {
        "Keyboard": 22000.0,
        "Laptop": 210000.0,
        "Monitor": 42000.0,
    }

    actual = dict(
        zip(
            result["Product"],
            result["Revenue"],
        )
    )

    assert actual == expected


def test_group_by_region_revenue(sales_dataframe):
    result = group_by_column(
        sales_dataframe,
        "Region",
        "Revenue",
        "sum",
    )

    result = result.sort_values("Region")

    expected = {
        "Gauteng": 148000.0,
        "KwaZulu-Natal": 42000.0,
        "Western Cape": 84000.0,
    }

    actual = dict(
        zip(
            result["Region"],
            result["Revenue"],
        )
    )

    assert actual == expected


def test_group_by_invalid_column(sales_dataframe):
    with pytest.raises(
        ValueError,
        match="Column 'InvalidColumn' not found",
    ):
        group_by_column(
            sales_dataframe,
            "InvalidColumn",
            "Revenue",
        )


def test_sort_revenue_descending(sales_dataframe):
    result = sort_dataset(
        sales_dataframe,
        "Revenue",
        ascending=False,
    )

    assert result.iloc[0]["Revenue"] == 75000
    assert result.iloc[1]["Revenue"] == 60000
    assert result.iloc[-1]["Revenue"] == 10000


def test_sort_revenue_ascending(sales_dataframe):
    result = sort_dataset(
        sales_dataframe,
        "Revenue",
        ascending=True,
    )

    assert result.iloc[0]["Revenue"] == 10000
    assert result.iloc[-1]["Revenue"] == 75000


def test_sort_does_not_modify_original_dataframe(sales_dataframe):
    original = sales_dataframe.copy()

    sort_dataset(
        sales_dataframe,
        "Revenue",
        ascending=False,
    )

    pd.testing.assert_frame_equal(
        sales_dataframe,
        original,
    )


def test_sort_invalid_column(sales_dataframe):
    with pytest.raises(
        ValueError,
        match="Column 'InvalidColumn' not found",
    ):
        sort_dataset(
            sales_dataframe,
            "InvalidColumn",
        )