from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from data_analysis import load_dataset


ALLOWED_DOCUMENT_SUFFIXES = (
    ".txt",
    ".pdf",
    ".docx",
)

# A hard ceiling on upload size. An unbounded upload is
# a denial-of-service vector, and the roadmap asks for file
# size limits.
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


def sanitise_filename(filename: str) -> str:
    """
    Reduce an uploaded filename to a safe basename.

    A client controls this string, so a path separator or a
    traversal segment must never escape the upload
    directory.
    """

    name = Path(filename).name

    cleaned = "".join(
        character
        for character in name
        if character.isalnum()
        or character in {"-", "_", "."}
    )

    cleaned = cleaned.strip(".")

    if not cleaned:
        raise ValueError(
            "The uploaded filename contained no usable "
            "characters."
        )

    return cleaned


class DatasetRegistry:
    """
    Datasets the API is allowed to analyse.

    Registration is explicit rather than directory
    scanning: the model must never be handed a file the
    caller did not ask for.
    """

    def __init__(
        self,
        upload_directory: str | Path = "data/uploads",
    ):
        self.upload_directory = Path(
            upload_directory
        )

        self.upload_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def register(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {path}"
            )

        dataframe = load_dataset(path)

        return {
            "name": path.name,
            "path": str(path),
            "rows": len(dataframe),
            "columns": list(dataframe.columns),
            "registered": True,
        }

    def register_from_upload(
        self,
        source: str | Path,
        filename: str,
    ) -> dict[str, Any]:
        """
        Move an uploaded dataset into the managed
        directory and register it.
        """

        safe_name = sanitise_filename(filename)

        target = (
            self.upload_directory / safe_name
        )

        source_path = Path(source)

        if source_path.resolve() != target.resolve():
            shutil.copy2(source_path, target)

        return self.register(target)

    def list_datasets(self) -> list[dict[str, Any]]:
        results = []

        for path in sorted(
            self.upload_directory.iterdir()
        ):
            if not path.is_file():
                continue

            results.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "rows": None,
                    "columns": [],
                    "registered": True,
                }
            )

        return results

    def get(
        self,
        name: str,
    ) -> Path | None:
        candidate = (
            self.upload_directory / sanitise_filename(name)
        )

        if candidate.exists():
            return candidate

        return None

class DocumentRegistry:
    """
    Documents available for RAG retrieval.

    Uploads land in a managed directory. Indexing is
    explicit, and a failure is reported rather than raised,
    so an unreadable PDF cannot 500 an otherwise valid
    upload.
    """

    def __init__(
        self,
        directory: str | Path = "documents",
        vector_store: Any | None = None,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.vector_store = vector_store

    def store(
        self,
        source: str | Path,
        filename: str,
        size_bytes: int,
    ) -> dict[str, Any]:
        if size_bytes > MAX_DOCUMENT_BYTES:
            raise ValueError(
                f"Document is {size_bytes} bytes, over the "
                f"{MAX_DOCUMENT_BYTES} byte limit."
            )

        safe_name = sanitise_filename(filename)

        if Path(safe_name).suffix.lower() not in (
            ALLOWED_DOCUMENT_SUFFIXES
        ):
            raise ValueError(
                f"Unsupported document type. Allowed: "
                f"{', '.join(ALLOWED_DOCUMENT_SUFFIXES)}"
            )

        target = self.directory / safe_name

        if Path(source).resolve() != target.resolve():
            shutil.copy2(source, target)

        indexed = False
        chunks = 0
        message = "Stored."

        try:
            chunks = self.index(target)
            indexed = True
            message = (
                f"Stored and indexed {chunks} chunk(s)."
            )
        except Exception as exc:
            message = (
                f"Stored but not indexed: {exc}. "
                f"The document will not be retrievable "
                f"until it indexes successfully."
            )

        return {
            "filename": safe_name,
            "stored_path": str(target),
            "size_bytes": size_bytes,
            "indexed": indexed,
            "chunks": chunks,
            "message": message,
        }

    def index(self, path: Path) -> int:
        """
        Chunk and embed one document into the vector store.
        """

        if self.vector_store is None:
            raise RuntimeError(
                "No vector store is configured, so "
                "documents cannot be indexed."
            )

        from rag.document_loader import (
            load_pdf_file,
            load_text_file,
        )

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            documents = load_pdf_file(str(path))
        elif suffix == ".txt":
            documents = load_text_file(str(path))
        else:
            raise ValueError(
                f"Indexing {suffix} is not implemented yet."
            )

        if not documents:
            return 0

        self.vector_store.add_documents(documents)

        return len(documents)

    def list_documents(self) -> list[str]:
        return sorted(
            path.name
            for path in self.directory.iterdir()
            if path.is_file()
            and path.suffix.lower()
            in ALLOWED_DOCUMENT_SUFFIXES
        )


class ReportStore:
    """
    Reports generated for a session, addressed by id.

    Kept in memory for V9. It is deliberately not the
    filesystem report directory: those files are generated
    output, whereas this is addressable state the API
    hands back by id.
    """

    def __init__(self) -> None:
        self._reports: dict[str, dict] = {}

    def save(
        self,
        session_id: str | None,
        content: str,
    ) -> str:
        report_id = uuid.uuid4().hex

        self._reports[report_id] = {
            "report_id": report_id,
            "session_id": session_id,
            "content": content,
        }

        return report_id

    def get(
        self,
        report_id: str,
    ) -> dict | None:
        return self._reports.get(report_id)

    def list_for_session(
        self,
        session_id: str,
    ) -> list[dict]:
        return [
            report
            for report in self._reports.values()
            if report["session_id"] == session_id
        ]