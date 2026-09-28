from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import create_engine

from data_analysis.sql_database import (
    describe_table,
    list_tables,
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
            ],
            "Product": [
                "Laptop",
                "Monitor",
                "Keyboard",
            ],
            "Region": [
                "Gauteng",
                "Western Cape",
                "Gauteng",
            ],
            "Revenue": [
                100000,
                50000,
                25000,
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


def test_list_tables(
    sales_engine,
):
    tables = list_tables(
        sales_engine
    )

    assert tables == ["sales"]


def test_describe_table(
    sales_engine,
):
    schema = describe_table(
        sales_engine,
        "sales",
    )

    column_names = [
        column["name"]
        for column in schema
    ]

    assert column_names == [
        "Date",
        "Product",
        "Region",
        "Revenue",
    ]


def test_describe_invalid_table(
    sales_engine,
):
    with pytest.raises(
        ValueError,
        match="Table 'missing' not found",
    ):
        describe_table(
            sales_engine,
            "missing",
        )