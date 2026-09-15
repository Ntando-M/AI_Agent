from pathlib import Path

from data_analysis.loader import load_csv, load_excel


def load_dataset(
    path: str,
    sheet_name: int | str = 0,
):
    """
    Load a CSV or Excel dataset based on its file extension.

    Args:
        path: Path to the dataset.
        sheet_name: Excel worksheet index or name. Defaults to the first sheet.

    Returns:
        A Pandas DataFrame containing the loaded dataset.

    Raises:
        ValueError: If the file format is unsupported.
    """

    file_path = Path(path)
    extension = file_path.suffix.lower()

    if extension == ".csv":
        return load_csv(path)

    if extension in {".xlsx", ".xlsm"}:
        return load_excel(
            path,
            sheet_name=sheet_name,
        )

    raise ValueError(
        f"Unsupported dataset format: '{extension or 'no extension'}'. "
        "Supported formats are: .csv, .xlsx, and .xlsm."
    )