from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine

from data_analysis.sql_tools import (
    describe_database_table,
    execute_read_only_query,
    inspect_database,
    list_database_tables,
    query_to_dataframe,
)


@pytest.fixture
def sales_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )

    dataframe = pd.DataFrame(
        {
            "Date": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-02-01",
            ],
            "Product": [
                "Laptop",
                "Monitor",
                "Keyboard",
                "Laptop",
            ],
            "Region": [
                "Gauteng",
                "Western Cape",
                "Gauteng",
                "Gauteng",
            ],
            "Revenue": [
                100000,
                50000,
                25000,
                75000,
            ],
        }
    )

    dataframe.to_sql(
        "sales",
        engine,
        index=False,
    )

    yield engine

    engine.dispose()


def test_inspect_database(
    sales_engine,
):
    result = inspect_database(
        sales_engine
    )

    assert result["table_count"] == 1
    assert result["tables"] == ["sales"]


def test_list_database_tables(
    sales_engine,
):
    result = list_database_tables(
        sales_engine
    )

    assert result == ["sales"]


def test_describe_database_table(
    sales_engine,
):
    result = describe_database_table(
        sales_engine,
        "sales",
    )

    names = [
        column["name"]
        for column in result
    ]

    assert "Product" in names
    assert "Revenue" in names


def test_select_query(
    sales_engine,
):
    result = execute_read_only_query(
        sales_engine,
        """
        SELECT Product, Revenue
        FROM sales
        ORDER BY Revenue DESC
        """,
    )

    assert len(result) == 4
    assert result[0]["Product"] == "Laptop"
    assert result[0]["Revenue"] == 100000


def test_aggregate_query(
    sales_engine,
):
    result = execute_read_only_query(
        sales_engine,
        """
        SELECT
            SUM(Revenue) AS total_revenue,
            AVG(Revenue) AS average_revenue
        FROM sales
        """,
    )

    assert result[0]["total_revenue"] == 250000
    assert result[0]["average_revenue"] == 62500


def test_group_by_query(
    sales_engine,
):
    result = execute_read_only_query(
        sales_engine,
        """
        SELECT
            Region,
            SUM(Revenue) AS total_revenue
        FROM sales
        GROUP BY Region
        ORDER BY total_revenue DESC
        """,
    )

    assert result[0]["Region"] == "Gauteng"
    assert result[0]["total_revenue"] == 200000


def test_with_query(
    sales_engine,
):
    result = execute_read_only_query(
        sales_engine,
        """
        WITH revenue_summary AS (
            SELECT
                Product,
                SUM(Revenue) AS total_revenue
            FROM sales
            GROUP BY Product
        )
        SELECT *
        FROM revenue_summary
        ORDER BY total_revenue DESC
        """,
    )

    assert result[0]["Product"] == "Laptop"


def test_query_limit(
    sales_engine,
):
    result = execute_read_only_query(
        sales_engine,
        "SELECT * FROM sales",
        max_rows=2,
    )

    assert len(result) == 2


def test_query_to_dataframe(
    sales_engine,
):
    result = query_to_dataframe(
        sales_engine,
        """
        SELECT Product, Revenue
        FROM sales
        """,
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )

    assert list(result.columns) == [
        "Product",
        "Revenue",
    ]


def test_invalid_table(
    sales_engine,
):
    with pytest.raises(
        ValueError,
        match="Table 'missing' not found",
    ):
        describe_database_table(
            sales_engine,
            "missing",
        )