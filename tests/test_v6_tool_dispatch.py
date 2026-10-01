from __future__ import annotations

import pandas as pd
import pytest

from data_analysis.agent import DataAnalysisAgent
from data_analysis.tool_models import AnalysisPlan
from data_analysis.tool_registry import (
    get_dataframe_tool_registry,
    get_sql_tool_registry,
    get_tool_data_source,
    get_tool_registry,
)


DATASET_PATH = "data/sample_sales.xlsx"
DATABASE_PATH = "data/sales.db"


@pytest.fixture
def sales_dataframe():
    return pd.DataFrame(
        {
            "Product": [
                "Laptop",
                "Monitor",
                "Laptop",
            ],
            "Revenue": [
                100000,
                50000,
                75000,
            ],
        }
    )


@pytest.fixture
def database_path(tmp_path):
    from sqlalchemy import create_engine

    from data_analysis.sql_database import (
        initialize_sales_database,
    )

    source = tmp_path / "source.csv"

    pd.DataFrame(
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
    ).to_csv(source, index=False)

    target = tmp_path / "sales.db"

    initialize_sales_database(
        source_path=source,
        database_path=target,
    )

    return target


# ========================================================
# REGISTRY SPLIT
# ========================================================


def test_registries_are_disjoint():
    dataframe_tools = get_dataframe_tool_registry()
    sql_tools = get_sql_tool_registry()

    shared = (
        set(dataframe_tools)
        & set(sql_tools)
    )

    assert shared == set()


def test_every_tool_is_in_exactly_one_registry():
    combined = get_tool_registry()

    expected = set(
        get_dataframe_tool_registry()
    ) | set(
        get_sql_tool_registry()
    )

    assert set(combined) == expected


def test_data_source_is_explicit_for_each_tool():
    assert get_tool_data_source(
        "group_by_column"
    ) == "dataframe"

    assert get_tool_data_source(
        "execute_read_only_sql"
    ) == "database"


def test_unknown_tool_has_no_data_source():
    with pytest.raises(
        ValueError,
        match="Unknown analysis tool",
    ):
        get_tool_data_source(
            "does_not_exist"
        )


# ========================================================
# TOOL ADVERTISEMENT
# ========================================================


def test_sql_tools_hidden_without_database():
    agent = DataAnalysisAgent(
        DATASET_PATH
    )

    assert agent.has_database is False

    advertised = agent.get_available_tool_descriptions()

    assert "execute_read_only_sql" not in advertised
    assert "group_by_column" in advertised


def test_sql_tools_advertised_with_database(
    database_path,
):
    agent = DataAnalysisAgent(
        DATASET_PATH,
        database_path=database_path,
    )

    assert agent.has_database is True

    advertised = agent.get_available_tool_descriptions()

    assert "execute_read_only_sql" in advertised
    assert "group_by_column" in advertised


# ========================================================
# DISPATCH
# ========================================================


def test_dataframe_tool_receives_dataframe():
    agent = DataAnalysisAgent(
        DATASET_PATH
    )

    dataframe, result = agent.execute_tool(
        agent.dataframe,
        "aggregate_dataset",
        {
            "column": "Revenue",
            "operation": "sum",
        },
    )

    assert result == 274000.0
    assert isinstance(
        dataframe, pd.DataFrame
    )


def test_sql_tool_receives_engine_not_dataframe(
    database_path,
):
    """
    This is the regression test for the defect where
    every tool was called with a DataFrame as its
    first argument, breaking all SQL tools.
    """

    agent = DataAnalysisAgent(
        DATASET_PATH,
        database_path=database_path,
    )

    dataframe, result = agent.execute_tool(
        agent.dataframe,
        "list_tables",
        {},
    )

    assert result == ["sales"]


def test_sql_tool_executes_read_only_query(
    database_path,
):
    agent = DataAnalysisAgent(
        DATASET_PATH,
        database_path=database_path,
    )

    dataframe, result = agent.execute_tool(
        agent.dataframe,
        "execute_read_only_sql",
        {
            "query": (
                "SELECT Product, SUM(Revenue) AS total "
                "FROM sales GROUP BY Product"
            ),
            "max_rows": 10,
        },
    )

    totals = {
        row["Product"]: row["total"]
        for row in result
    }

    assert totals == {
        "Laptop": 100000,
        "Monitor": 50000,
    }


def test_sql_tool_refused_without_database():
    agent = DataAnalysisAgent(
        DATASET_PATH
    )

    with pytest.raises(
        ValueError,
        match="requires an analytical database",
    ):
        agent.execute_tool(
            agent.dataframe,
            "list_tables",
            {},
        )


def test_unknown_tool_is_rejected():
    agent = DataAnalysisAgent(
        DATASET_PATH
    )

    with pytest.raises(
        ValueError,
        match="Unknown analysis tool",
    ):
        agent.execute_tool(
            agent.dataframe,
            "not_a_real_tool",
            {},
        )


# ========================================================
# MIXED PLANS
# ========================================================


def test_mixed_plan_runs_sql_then_dataframe_tool(
    database_path,
):
    """
    SQL results feed the next dataframe tool as the
    working dataset.
    """

    agent = DataAnalysisAgent(
        DATASET_PATH,
        database_path=database_path,
    )

    plan = AnalysisPlan.model_validate(
        {
            "steps": [
                {
                    "tool": "execute_read_only_sql",
                    "arguments": {
                        "query": (
                            "SELECT Product, "
                            "SUM(Revenue) AS total "
                            "FROM sales "
                            "GROUP BY Product"
                        ),
                        "max_rows": 10,
                    },
                },
                {
                    "tool": "aggregate_dataset",
                    "arguments": {
                        "column": "total",
                        "operation": "sum",
                    },
                },
            ]
        }
    )

    results = agent.execute_plan(plan)

    assert results[0]["tool"] == (
        "execute_read_only_sql"
    )
    assert results[1]["result"] == 150000.0


def test_mixed_plan_preserves_step_order(
    database_path,
):
    agent = DataAnalysisAgent(
        DATASET_PATH,
        database_path=database_path,
    )

    plan = AnalysisPlan.model_validate(
        {
            "steps": [
                {"tool": "inspect_database", "arguments": {}},
                {"tool": "inspect_dataset", "arguments": {}},
                {"tool": "list_tables", "arguments": {}},
            ]
        }
    )

    results = agent.execute_plan(plan)

    assert [
        result["tool"] for result in results
    ] == [
        "inspect_database",
        "inspect_dataset",
        "list_tables",
    ]


def test_write_query_still_rejected_through_agent(
    database_path,
):
    agent = DataAnalysisAgent(
        DATASET_PATH,
        database_path=database_path,
    )

    with pytest.raises(
        ValueError,
    ):
        agent.execute_tool(
            agent.dataframe,
            "execute_read_only_sql",
            {
                "query": "DELETE FROM sales",
            },
        )