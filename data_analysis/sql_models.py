from __future__ import annotations

from pydantic import BaseModel, Field


class InspectDatabaseInput(BaseModel):
    """
    Input for database inspection.
    """

    pass


class ListTablesInput(BaseModel):
    """
    Input for listing database tables.
    """

    pass


class DescribeTableInput(BaseModel):
    """
    Input for describing a database table.
    """

    table_name: str = Field(
        min_length=1,
        description="Name of the database table",
    )


class ReadOnlySQLInput(BaseModel):
    """
    Input for controlled read-only SQL execution.
    """

    query: str = Field(
        min_length=1,
        description="A read-only SELECT or WITH SQL query",
    )

    max_rows: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of rows to return",
    )