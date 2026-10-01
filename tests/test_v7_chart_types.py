from __future__ import annotations

import pandas as pd
import pytest

from data_analysis.charts import (
    plot_revenue_box_plot,
    plot_revenue_distribution,
    plot_revenue_relationship,
)


@pytest.fixture
def sales_dataframe():
    return pd.DataFrame(
        {
            "Date": [
                "2026-01-01",
                "2026-01-02",
                "2026-02-01",
                "2026-02-02",
            ],
            "Product": [
                "Laptop",
                "Monitor",
                "Laptop",
                "Keyboard",
            ],
            "Region": [
                "Gauteng",
                "Western Cape",
                "Gauteng",
                "KwaZulu-Natal",
            ],
            "Revenue": [
                100000,
                50000,
                75000,
                25000,
            ],
            "Quantity": [
                10,
                20,
                8,
                30,
            ],
        }
    )


def test_revenue_distribution_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = tmp_path / "distribution.png"

    result = plot_revenue_distribution(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_revenue_distribution_rejects_unknown_column(
    sales_dataframe,
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        plot_revenue_distribution(
            sales_dataframe,
            revenue_column="NotAColumn",
            output_path=tmp_path / "x.png",
        )


def test_revenue_distribution_rejects_non_numeric(
    sales_dataframe,
    tmp_path,
):
    with pytest.raises(
        TypeError,
        match="must be numeric",
    ):
        plot_revenue_distribution(
            sales_dataframe,
            revenue_column="Product",
            output_path=tmp_path / "x.png",
        )


def test_revenue_relationship_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = tmp_path / "relationship.png"

    result = plot_revenue_relationship(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_revenue_relationship_requires_two_columns(
    sales_dataframe,
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        plot_revenue_relationship(
            sales_dataframe,
            y_column="NotAColumn",
            output_path=tmp_path / "x.png",
        )


def test_revenue_box_plot_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = tmp_path / "box_plot.png"

    result = plot_revenue_box_plot(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_revenue_box_plot_rejects_unknown_category(
    sales_dataframe,
    tmp_path,
):
    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        plot_revenue_box_plot(
            sales_dataframe,
            category_column="NotAColumn",
            output_path=tmp_path / "x.png",
        )


def test_default_output_directory_is_outputs_charts():
    from data_analysis.charts import (
        DEFAULT_OUTPUT_DIRECTORY,
    )

    assert (
        DEFAULT_OUTPUT_DIRECTORY.parts
    ) == ("outputs", "charts")