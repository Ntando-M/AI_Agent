import pandas as pd
import pytest

from data_analysis.analyzer import (
    inspect_dataset,
    filter_dataset,
    get_unique_values,
)


DATASET_PATH = "data/sample_sales.xlsx"


@pytest.fixture
def sales_dataframe():
    return pd.read_excel(DATASET_PATH)


def test_inspect_dataset(sales_dataframe):
    result = inspect_dataset(sales_dataframe)

    assert result["rows"] == 8
    assert result["columns"] == 6

    assert result["column_names"] == [
        "Date",
        "Product",
        "Region",
        "Units",
        "Revenue",
        "Customer_Satisfaction",
    ]

    assert result["dtypes"]["Product"] in {"object", "str"}
    assert result["dtypes"]["Region"] in {"object", "str"}

    assert result["missing_values"]["Customer_Satisfaction"] == 1


def test_filter_dataset(sales_dataframe):
    result = filter_dataset(
        sales_dataframe,
        "Product",
        "Laptop",
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 4
    assert result["Product"].eq("Laptop").all()


def test_filter_dataset_gauteng(sales_dataframe):
    result = filter_dataset(
        sales_dataframe,
        "Region",
        "Gauteng",
    )

    assert len(result) == 4
    assert result["Region"].eq("Gauteng").all()


def test_get_unique_values(sales_dataframe):
    products = get_unique_values(
        sales_dataframe,
        "Product",
    )

    assert set(products) == {
        "Laptop",
        "Monitor",
        "Keyboard",
    }


def test_get_unique_regions(sales_dataframe):
    regions = get_unique_values(
        sales_dataframe,
        "Region",
    )

    assert set(regions) == {
        "Gauteng",
        "Western Cape",
        "KwaZulu-Natal",
    }


def test_filter_invalid_column(sales_dataframe):
    with pytest.raises(ValueError, match="Column 'InvalidColumn' not found"):
        filter_dataset(
            sales_dataframe,
            "InvalidColumn",
            "Laptop",
        )


def test_unique_values_invalid_column(sales_dataframe):
    with pytest.raises(ValueError, match="Column 'InvalidColumn' not found"):
        get_unique_values(
            sales_dataframe,
            "InvalidColumn",
        )


def test_inspect_requires_dataframe():
    with pytest.raises(TypeError, match="Expected a Pandas DataFrame"):
        inspect_dataset("not a dataframe")