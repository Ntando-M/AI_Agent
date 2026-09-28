from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from data_analysis.sql_database import (
    create_sqlite_engine,
)
from data_analysis.sql_tools import (
    describe_database_table,
    execute_read_only_query,
    inspect_database,
    list_database_tables,
)


class SQLAnalysisAgent:
    """
    Deterministic SQL analysis service.

    This class does not decide what SQL should be generated.
    It provides controlled database-analysis capabilities
    for the future AI orchestrator.
    """

    def __init__(
        self,
        database_path: str | Path,
    ):
        self.database_path = Path(
            database_path
        )

        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Database not found: "
                f"{self.database_path}"
            )

        self.engine: Engine = (
            create_sqlite_engine(
                self.database_path
            )
        )

    def inspect_database(
        self,
    ) -> dict[str, Any]:
        return inspect_database(
            self.engine
        )

    def list_tables(
        self,
    ) -> list[str]:
        return list_database_tables(
            self.engine
        )

    def describe_table(
        self,
        table_name: str,
    ) -> list[dict[str, Any]]:
        return describe_database_table(
            self.engine,
            table_name,
        )

    def execute_query(
        self,
        query: str,
        max_rows: int = 100,
    ) -> list[dict[str, Any]]:
        return execute_read_only_query(
            self.engine,
            query,
            max_rows=max_rows,
        )

    def close(self) -> None:
        self.engine.dispose()