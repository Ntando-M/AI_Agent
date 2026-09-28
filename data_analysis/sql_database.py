from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, inspect


DEFAULT_TABLE_NAME = "sales"


def create_sqlite_engine(
    database_path: str | Path,
) -> Engine:
    """
    Create a SQLAlchemy SQLite engine.

    Parameters
    ----------
    database_path:
        Path to the SQLite database file.

    Returns
    -------
    Engine
        SQLAlchemy engine.
    """

    database_path = Path(database_path)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return create_engine(
        f"sqlite:///{database_path}",
        future=True,
    )


def list_tables(
    engine: Engine,
) -> list[str]:
    """
    Return all tables in the database.
    """

    inspector = inspect(engine)

    return sorted(
        inspector.get_table_names()
    )


def describe_table(
    engine: Engine,
    table_name: str,
) -> list[dict[str, object]]:
    """
    Return schema information for a table.
    """

    inspector = inspect(engine)

    tables = inspector.get_table_names()

    if table_name not in tables:
        raise ValueError(
            f"Table '{table_name}' not found"
        )

    columns = inspector.get_columns(
        table_name
    )

    return [
        {
            "name": column["name"],
            "type": str(column["type"]),
            "nullable": column.get(
                "nullable",
                True,
            ),
            "primary_key": column.get(
                "primary_key",
                False,
            ),
        }
        for column in columns
    ]


def initialize_sales_database(
    source_path: str | Path,
    database_path: str | Path,
    table_name: str = DEFAULT_TABLE_NAME,
) -> None:
    """
    Create the analytical SQLite database
    from the existing V5 sales dataset.

    The source may be CSV or Excel.
    """

    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Source dataset not found: {source_path}"
        )

    suffix = source_path.suffix.lower()

    if suffix == ".csv":
        dataframe = pd.read_csv(source_path)

    elif suffix in {".xlsx", ".xlsm", ".xls"}:
        dataframe = pd.read_excel(source_path)

    else:
        raise ValueError(
            f"Unsupported dataset format: {suffix}"
        )

    engine = create_sqlite_engine(
        database_path
    )

    dataframe.to_sql(
        table_name,
        engine,
        if_exists="replace",
        index=False,
    )

    engine.dispose()