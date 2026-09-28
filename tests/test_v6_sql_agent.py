from __future__ import annotations

import pandas as pd

from data_analysis.sql_agent import (
    SQLAnalysisAgent,
)


def test_sql_analysis_agent(tmp_path):
    database_path = (
        tmp_path / "sales.db"
    )

    engine = __import__(
        "sqlalchemy"
    ).create_engine(
        f"sqlite:///{database_path}",
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

    engine.dispose()

    agent = SQLAnalysisAgent(
        database_path
    )

    database = (
        agent.inspect_database()
    )

    assert database["tables"] == [
        "sales"
    ]

    result = agent.execute_query(
        """
        SELECT
            Product,
            Revenue
        FROM sales
        ORDER BY Revenue DESC
        """
    )

    assert result[0]["Product"] == "Laptop"

    agent.close()