from pathlib import Path

import pandas as pd


def load_csv(path: str) -> pd.DataFrame:
    """
    Load a CSV file into a Pandas DataFrame.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"CSV file not found: {path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Expected a file path, received: {path}"
        )

    if file_path.suffix.lower() != ".csv":
        raise ValueError(
            f"Expected a CSV file, received: {file_path.suffix}"
        )

    try:
        return pd.read_csv(file_path)

    except Exception as e:
        raise ValueError(
            f"Failed to parse CSV at {path}: {e}"
        ) from e


def load_excel(
    path: str,
    sheet_name: int | str = 0,
) -> pd.DataFrame:
    """
    Load an Excel worksheet into a Pandas DataFrame.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Excel file not found: {path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Expected a file path, received: {path}"
        )

    if file_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError(
            "Expected an Excel file with a .xlsx or .xlsm extension."
        )

    try:
        return pd.read_excel(
            file_path,
            sheet_name=sheet_name,
        )

    except Exception as e:
        raise ValueError(
            f"Failed to parse Excel at {path}: {e}"
        ) from e