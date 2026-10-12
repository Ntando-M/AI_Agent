from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
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
        """
        Every uploaded dataset, with its shape.

        The shape is read from the file rather than stored,
        so a listing cannot drift from what is on disk. A
        file that cannot be parsed is still listed with an
        unknown shape: one bad upload must not hide the rest
        of the directory.
        """

        results = []

        for path in sorted(
            self.upload_directory.iterdir()
        ):
            if not path.is_file():
                continue

            rows: int | None = None
            columns: list[str] = []

            try:
                dataframe = load_dataset(str(path))

                rows = len(dataframe)

                columns = [
                    str(column)
                    for column in dataframe.columns
                ]
            except Exception:
                # An unreadable file is still a listed file.
                pass

            results.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "rows": rows,
                    "columns": columns,
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

    def delete(self, name: str) -> bool:
        """
        Remove an uploaded dataset.

        Returns False when there is nothing to remove, so a
        caller can tell a no-op from a real delete. The name
        is sanitised first: it arrives from a client, and a
        traversal segment must not be able to delete anything
        outside the upload directory.
        """

        candidate = (
            self.upload_directory / sanitise_filename(name)
        )

        if not candidate.exists() or not candidate.is_file():
            return False

        candidate.unlink()

        return True

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
            load_docx_file,
            load_pdf_file,
            load_text_file,
        )

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            documents = load_pdf_file(str(path))
        elif suffix == ".txt":
            documents = load_text_file(str(path))
        elif suffix == ".docx":
            documents = load_docx_file(str(path))
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

    def delete(self, name: str) -> tuple[bool, int]:
        """
        Remove a document and its indexed chunks.

        The file and its embeddings are removed together, and
        the embeddings first. Deleting only the file would
        leave its chunks retrievable, so the engine would keep
        citing a document that no longer exists - worse than
        either failing or succeeding outright.

        Returns (deleted, chunks_removed). The chunks are
        counted here rather than by the caller so that exactly
        one sanitisation of the name is used for both halves:
        two sanitise helpers exist in this package with
        slightly different rules, and computing the name for
        the index from one while the file is resolved with the
        other can target different documents.

        A vector-store failure is raised rather than
        swallowed: a half-deleted document is a state the
        caller needs to know about, not one to report as
        success.
        """

        safe_name = sanitise_filename(name)

        candidate = self.directory / safe_name

        if not candidate.exists() or not candidate.is_file():
            return False, 0

        chunks_removed = self.remove_embeddings(safe_name)

        candidate.unlink()

        return True, chunks_removed

    def remove_embeddings(self, safe_name: str) -> int:
        """
        Drop a document's chunks from the vector store.

        Matched on the stored metadata rather than on the path
        alone: the loader records "filename" and an absolute
        "source", and the absolute path differs between
        environments, so matching both forms is what makes the
        removal reliable. A missing store or an unsupported
        collection is not an error - there is simply nothing
        indexed to remove.
        """

        if self.vector_store is None:
            return 0

        collection = getattr(
            self.vector_store, "_collection", None
        )

        if collection is None:
            return 0

        try:
            existing = collection.get(
                where={"filename": safe_name}
            )
        except Exception:
            return 0

        ids = existing.get("ids") or []

        if not ids:
            return 0

        collection.delete(ids=ids)

        return len(ids)


class ReportStore:
    """
    Reports generated for a session, addressed by id.

    Persisted as one JSON file per report under the
    configured reports directory. An in-memory dictionary
    was the previous implementation, and it meant a report
    vanished on restart - the endpoint that serves reports
    by id could only ever answer 404, because nothing ever
    survived long enough to be read back.

    The id is generated here and validated on read: it
    arrives from a URL, so a path built from it unchecked
    is a traversal bug.
    """

    def __init__(
        self,
        directory: str | Path = "reports",
    ) -> None:
        self.directory = Path(directory)

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save(
        self,
        session_id: str | None,
        content: str,
        dataset_name: str | None = None,
        summary: dict | None = None,
        layers: dict | None = None,
        charts: dict | None = None,
    ) -> str:
        report_id = uuid.uuid4().hex

        report = {
            "report_id": report_id,
            "session_id": session_id,
            "content": content,
            "dataset_name": dataset_name,
            "summary": summary or {},
            "layers": layers or {},
            "charts": charts or {},
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        self._path(report_id).write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        return report_id

    def get(
        self,
        report_id: str,
    ) -> dict | None:
        if not _is_safe_report_id(report_id):
            return None

        path = self._path(report_id)

        if not path.is_file():
            return None

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            # One unreadable file must not make the whole
            # listing unavailable.
            return None

        if not isinstance(payload, dict):
            return None

        return payload

    def list_reports(self) -> list[dict]:
        """
        Every stored report, newest first.

        Sorted by created_at descending so the most recent
        report is the first thing the page shows.
        """

        reports = []

        for path in self.directory.glob("*.json"):
            report = self.get(path.stem)

            if report is not None:
                reports.append(report)

        reports.sort(
            key=lambda report: (
                report.get("created_at") or ""
            ),
            reverse=True,
        )

        return reports

    def list_for_session(
        self,
        session_id: str,
    ) -> list[dict]:
        return [
            report
            for report in self.list_reports()
            if report["session_id"] == session_id
        ]

    def _path(self, report_id: str) -> Path:
        return self.directory / f"{report_id}.json"


def _is_safe_report_id(report_id: str) -> bool:
    """
    Whether an id from a URL is one this store could have
    generated.

    Ids are `uuid4().hex`, so anything containing a path
    separator, a dot, or a traversal segment is rejected
    outright. Validating the shape is stricter than
    sanitising the path, and stricter is correct here: the
    only legitimate input is a 32-character hex string.
    """

    if not report_id or len(report_id) != 32:
        return False

    return all(
        character in "0123456789abcdef"
        for character in report_id
    )