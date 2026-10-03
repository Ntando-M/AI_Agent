"""
Regression tests for the laptop/laptops contradiction.

Asking "how many units of laptops were sold" returned zero while
"which product earned the most revenue" correctly returned Laptop.
Two causes, both in the deterministic layer:

1. filter_dataset matched the user's wording exactly, so "laptops"
   did not match the stored label "Laptop".
2. aggregate_dataset summed an empty frame to 0.0 without raising,
   so a failed filter was reported as a confident "none were sold".

These tests pin both behaviours.
"""

import pandas as pd
import pytest

from data_analysis.analyzer import (
    aggregate_dataset,
    filter_dataset,
    group_by_column,
)


DATASET_PATH = "data/sample.csv"


@pytest.fixture
def sales_dataframe():
    return pd.read_csv(DATASET_PATH)


class TestFilterValueResolution:
    """
    filter_dataset must resolve the caller's value against the
    labels actually present in the column.
    """

    def test_exact_match_still_works(self, sales_dataframe):
        result = filter_dataset(
            sales_dataframe,
            "Product",
            "Laptop",
        )

        assert len(result) == 4
        assert result["Product"].eq("Laptop").all()

    @pytest.mark.parametrize(
        "value",
        ["laptop", "LAPTOP", "Laptop ", " laptops"],
    )
    def test_case_and_whitespace_variants_resolve(
        self,
        sales_dataframe,
        value,
    ):
        result = filter_dataset(
            sales_dataframe,
            "Product",
            value,
        )

        assert len(result) == 4, (
            f"{value!r} should resolve to the stored label 'Laptop'"
        )

    def test_plural_resolves_to_singular_label(self, sales_dataframe):
        result = filter_dataset(
            sales_dataframe,
            "Product",
            "laptops",
        )

        assert len(result) == 4

    def test_singular_query_matches_plural_label(self, sales_dataframe):
        dataframe = sales_dataframe.copy()
        dataframe["Product"] = "Laptops"

        result = filter_dataset(
            dataframe,
            "Product",
            "laptop",
        )

        assert len(result) == len(dataframe)
        assert result["Product"].eq("Laptops").all()

    def test_numeric_column_filter_is_unchanged(self, sales_dataframe):
        result = filter_dataset(
            sales_dataframe,
            "Units",
            5,
        )

        assert len(result) > 0
        assert result["Units"].eq(5).all()

    def test_numeric_string_filter_resolves_to_number(
        self,
        sales_dataframe,
    ):
        result = filter_dataset(
            sales_dataframe,
            "Units",
            "5",
        )

        assert len(result) > 0
        assert result["Units"].eq(5).all()


class TestEmptyResultIsNotSilentlyZero:
    """
    An aggregation over an empty frame is a failed lookup, not a
    measurement of zero. It must raise.
    """

    def test_aggregate_raises_on_empty_frame(self):
        empty = pd.DataFrame({"Units": []})

        with pytest.raises(ValueError, match="no rows"):
            aggregate_dataset(empty, "Units", "sum")

    @pytest.mark.parametrize(
        "operation",
        ["sum", "mean", "min", "max"],
    )
    def test_every_operation_raises_on_empty_frame(self, operation):
        empty = pd.DataFrame({"Units": []})

        with pytest.raises(ValueError):
            aggregate_dataset(empty, "Units", operation)

    def test_unknown_value_raises_rather_than_returning_empty(
        self,
        sales_dataframe,
    ):
        with pytest.raises(ValueError, match="no rows"):
            aggregate_dataset(
                filter_dataset(
                    sales_dataframe,
                    "Product",
                    "Smartfridge",
                ),
                "Units",
                "sum",
            )

    def test_statistics_raises_on_empty_frame(self):
        from data_analysis.analyzer import (
            calculate_statistics,
        )

        empty = pd.DataFrame({"Units": []})

        with pytest.raises(ValueError, match="no rows"):
            calculate_statistics(empty, "Units")

    def test_group_by_raises_on_empty_frame(self):
        empty = pd.DataFrame({"Product": [], "Revenue": []})

        with pytest.raises(ValueError, match="no rows"):
            group_by_column(empty, "Product", "Revenue", "sum")


class TestTheTwoQuestionsAgree:
    """
    The user's actual symptom, asserted end to end on the
    deterministic layer: the revenue ranking and the units lookup
    must both put Laptop on the map.
    """

    def test_best_product_agrees_with_units_lookup(
        self,
        sales_dataframe,
    ):
        ranking = group_by_column(
            sales_dataframe,
            "Product",
            "Revenue",
            "sum",
        )

        best_product = ranking.sort_values(
            "Revenue",
            ascending=False,
        ).iloc[0]["Product"]

        filtered = filter_dataset(
            sales_dataframe,
            "Product",
            best_product.lower() + "s",
        )

        units = aggregate_dataset(
            filtered,
            "Units",
            "sum",
        )

        assert best_product == "Laptop"
        assert units > 0
        assert len(filtered) > 0