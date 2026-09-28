from __future__ import annotations

import pandas as pd
import pytest

from data_analysis.charts import (
    generate_standard_sales_charts,
    plot_monthly_revenue,
    plot_revenue_by_product,
    plot_revenue_by_region,
    plot_revenue_trend,
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
        }
    )


def test_revenue_by_product_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = (
        tmp_path
        / "product.png"
    )

    result = plot_revenue_by_product(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(
        output_path
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_revenue_by_region_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = (
        tmp_path
        / "region.png"
    )

    result = plot_revenue_by_region(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(
        output_path
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_monthly_revenue_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = (
        tmp_path
        / "monthly.png"
    )

    result = plot_monthly_revenue(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(
        output_path
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_revenue_trend_chart(
    sales_dataframe,
    tmp_path,
):
    output_path = (
        tmp_path
        / "trend.png"
    )

    result = plot_revenue_trend(
        sales_dataframe,
        output_path=output_path,
    )

    assert result == str(
        output_path
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_standard_sales_charts(
    sales_dataframe,
    tmp_path,
):
    result = (
        generate_standard_sales_charts(
            sales_dataframe,
            output_directory=tmp_path,
        )
    )

    assert set(result.keys()) == {
        "revenue_by_product",
        "revenue_by_region",
        "monthly_revenue",
        "revenue_trend",
    }

    for path in result.values():
        assert (
            tmp_path
            / path.split("\\")[-1]
        ).exists() or (
            tmp_path
            / path.split("/")[-1]
        ).exists()