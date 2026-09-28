from __future__ import annotations

import sys
from pathlib import Path


# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from data_analysis.sql_database import (
    initialize_sales_database,
)


SOURCE_DATASET = (
    PROJECT_ROOT
    / "data"
    / "sample_sales.xlsx"
)

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "sales.db"
)


def main() -> None:
    initialize_sales_database(
        source_path=SOURCE_DATASET,
        database_path=DATABASE_PATH,
    )

    print(
        "Sales database created successfully."
    )

    print(
        f"Database: {DATABASE_PATH}"
    )


if __name__ == "__main__":
    main()