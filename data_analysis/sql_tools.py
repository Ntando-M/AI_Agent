from __future__ import annotations

import re
from typing import Any

import pandas as pd
from sqlalchemy import Engine, inspect, text


DEFAULT_MAX_ROWS = 100


FORBIDDEN_SQL_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
    "GRANT",
    "REVOKE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "ANALYZE",
}


def _remove_sql_comments(query: str) -> str:
    """
    Remove SQL comments before security validation.
    """

    query = re.sub(
        r"--[^\n]*",
        "",
        query,
    )

    query = re.sub(
        r"/\*.*?\*/",
        "",
        query,
        flags=re.DOTALL,
    )

    return query


def validate_read_only_query(
    query: str,
) -> str:
    """
    Validate that a SQL statement is read-only.

    Allowed:
        SELECT
        WITH ... SELECT

    Rejected:
        INSERT
        UPDATE
        DELETE
        DROP
        ALTER
        CREATE
        etc.

    Multiple SQL statements are rejected.
    """

    if not isinstance(query, str):
        raise TypeError(
            "SQL query must be a string"
        )

    cleaned = _remove_sql_comments(
        query
    ).strip()

    if not cleaned:
        raise ValueError(
            "SQL query cannot be empty"
        )

    # Remove one optional trailing semicolon.
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()

    # Any remaining semicolon means multiple statements.
    if ";" in cleaned:
        raise ValueError(
            "Multiple SQL statements are not allowed"
        )

    upper_query = cleaned.upper()

    first_keyword_match = re.match(
        r"^\s*([A-Z]+)",
        upper_query,
    )

    if not first_keyword_match:
        raise ValueError(
            "Unable to determine SQL statement type"
        )

    first_keyword = (
        first_keyword_match.group(1)
    )

    if first_keyword not in {
        "SELECT",
        "WITH",
    }:
        raise ValueError(
            "Only SELECT and read-only WITH queries are allowed"
        )

    for keyword in FORBIDDEN_SQL_KEYWORDS:
        pattern = rf"\b{re.escape(keyword)}\b"

        if re.search(
            pattern,
            upper_query,
        ):
            raise ValueError(
                f"Forbidden SQL operation detected: {keyword}"
            )

    return cleaned


def inspect_database(
    engine: Engine,
) -> dict[str, Any]:
    """
    Return high-level database information.
    """

    inspector = inspect(engine)

    tables = sorted(
        inspector.get_table_names()
    )

    return {
        "table_count": len(tables),
        "tables": tables,
    }


def list_database_tables(
    engine: Engine,
) -> list[str]:
    """
    Return database table names.
    """

    inspector = inspect(engine)

    return sorted(
        inspector.get_table_names()
    )


def describe_database_table(
    engine: Engine,
    table_name: str,
) -> list[dict[str, Any]]:
    """
    Return column/schema information
    for a database table.
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


def _apply_sqlite_limit(
    query: str,
    max_rows: int,
) -> str:
    """
    Apply a hard result limit to a SQLite query.
    """

    return f"""
SELECT *
FROM (
    {query}
) AS _readonly_query
LIMIT {max_rows}
""".strip()


def execute_read_only_query(
    engine: Engine,
    query: str,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> list[dict[str, Any]]:
    """
    Execute a validated read-only SQL query.

    Results are capped at max_rows.
    """

    if not isinstance(max_rows, int):
        raise TypeError(
            "max_rows must be an integer"
        )

    if max_rows <= 0:
        raise ValueError(
            "max_rows must be greater than zero"
        )

    if max_rows > 10000:
        raise ValueError(
            "max_rows cannot exceed 10000"
        )

    validated_query = validate_read_only_query(
        query
    )

    dialect_name = engine.dialect.name

    if dialect_name == "sqlite":
        limited_query = _apply_sqlite_limit(
            validated_query,
            max_rows,
        )

    elif dialect_name == "mssql":
        limited_query = f"""
SELECT TOP {max_rows} *
FROM (
    {validated_query}
) AS _readonly_query
""".strip()

    else:
        raise ValueError(
            f"Unsupported SQL dialect for controlled execution: "
            f"{dialect_name}"
        )

    with engine.connect() as connection:
        result = connection.execute(
            text(limited_query)
        )

        rows = result.mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def query_to_dataframe(
    engine: Engine,
    query: str,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> pd.DataFrame:
    """
    Execute a read-only query and return
    the result as a DataFrame.
    """

    rows = execute_read_only_query(
        engine,
        query,
        max_rows=max_rows,
    )

    return pd.DataFrame(rows)