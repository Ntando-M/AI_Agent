from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine

from data_analysis.sql_tools import (
    execute_read_only_query,
    validate_read_only_query,
)


@pytest.fixture
def sales_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
    )

    dataframe = pd.DataFrame(
        {
            "Product": [
                "Laptop",
                "Monitor",
            ],
            "Revenue": [
                100000,
                50000,
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


@pytest.mark.parametrize(
    "query",
    [
        "INSERT INTO sales VALUES ('Mouse', 10)",
        "UPDATE sales SET Revenue = 0",
        "DELETE FROM sales",
        "DROP TABLE sales",
        "ALTER TABLE sales ADD COLUMN test TEXT",
        "CREATE TABLE test (id INTEGER)",
        "TRUNCATE TABLE sales",
        "REPLACE INTO sales VALUES ('Mouse', 10)",
        "PRAGMA table_info(sales)",
        "VACUUM",
    ],
)
def test_write_or_ddl_queries_are_rejected(
    query,
):
    with pytest.raises(
        ValueError
    ):
        validate_read_only_query(
            query
        )


def test_empty_query_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        validate_read_only_query("")


def test_whitespace_query_is_rejected():
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        validate_read_only_query("   ")


def test_non_sql_string_is_rejected():
    with pytest.raises(
        TypeError,
        match="must be a string",
    ):
        validate_read_only_query(
            123
        )


def test_multiple_statements_are_rejected():
    with pytest.raises(
        ValueError,
        match="Multiple SQL statements",
    ):
        validate_read_only_query(
            "SELECT * FROM sales; DELETE FROM sales"
        )


def test_trailing_semicolon_is_allowed():
    result = validate_read_only_query(
        "SELECT * FROM sales;"
    )

    assert result == (
        "SELECT * FROM sales"
    )


def test_select_is_allowed():
    result = validate_read_only_query(
        "SELECT * FROM sales"
    )

    assert result == (
        "SELECT * FROM sales"
    )


def test_with_query_is_allowed():
    result = validate_read_only_query(
        """
        WITH totals AS (
            SELECT SUM(Revenue) AS total
            FROM sales
        )
        SELECT *
        FROM totals
        """
    )

    assert result.startswith("WITH")


def test_query_cannot_modify_database(
    sales_engine,
):
    with pytest.raises(
        ValueError
    ):
        execute_read_only_query(
            sales_engine,
            "DELETE FROM sales",
        )


def test_max_rows_must_be_positive(
    sales_engine,
):
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        execute_read_only_query(
            sales_engine,
            "SELECT * FROM sales",
            max_rows=0,
        )


def test_max_rows_has_upper_limit(
    sales_engine,
):
    with pytest.raises(
        ValueError,
        match="cannot exceed 10000",
    ):
        execute_read_only_query(
            sales_engine,
            "SELECT * FROM sales",
            max_rows=10001,
        )