"""Guards for untrusted input arriving over HTTP.

The API accepts two kinds of untrusted bytes: an uploaded
dataset and an uploaded document. Both are written to disk
before anything inspects them, so an endpoint that copies a
request body without a limit lets a caller fill the disk.

Two limits apply, and they are not interchangeable.

* A size limit bounds how much is written. It is enforced
  while streaming, so an oversized upload is abandoned at the
  limit rather than after the whole body has been received.

* A type limit bounds what is accepted. A filename extension is
  a claim by the client, so it is checked, but it is not proof:
  the extension is only ever a filter, never the reason a file
  is considered safe.

Neither replaces the parsers being defensive. A 1 MB file with
a .csv extension can still be malformed, and the loader has to
survive that. These limits keep the blast radius of a bad
request bounded; they do not make bad input good.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


# Defaults are deliberately conservative for a portfolio
# service: analytical datasets are small, and a document that
# genuinely exceeds these limits is unusual. Both are
# configurable so a real deployment can raise them.
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

DATASET_EXTENSIONS = frozenset(
    {".csv", ".xlsx", ".xls"}
)

DOCUMENT_EXTENSIONS = frozenset(
    {".txt", ".pdf", ".docx"}
)


class UploadRejected(Exception):
    """
    An upload failed a limit and must not be stored.

    A distinct exception type so the endpoint can map it to a
    413 or 400 and let genuine processing errors surface as
    500s. Raising ValueError for everything would make an
    oversized file indistinguishable from a corrupt one.
    """


# 64 KB is large enough that syscall overhead is irrelevant and
# small enough that the limit check happens often.
CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class UploadPolicy:
    """
    The limits applied to one class of upload.

    Separate policies rather than one global limit because a
    spreadsheet and a PDF have different legitimate sizes, and
    a single number would be either too tight for one or too
    loose for the other.
    """

    max_bytes: int
    allowed_extensions: frozenset[str]
    label: str

    @classmethod
    def for_datasets(
        cls,
        max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> "UploadPolicy":
        return cls(
            max_bytes=max_bytes,
            allowed_extensions=DATASET_EXTENSIONS,
            label="dataset",
        )

    @classmethod
    def for_documents(
        cls,
        max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> "UploadPolicy":
        return cls(
            max_bytes=max_bytes,
            allowed_extensions=DOCUMENT_EXTENSIONS,
            label="document",
        )

    def validate_extension(
        self,
        filename: str | None,
    ) -> str:
        """
        Check the claimed extension and return it.

        Rejecting an unknown extension is what stops a caller
        writing an executable or a .env to a directory the
        service later reads. The check is on the suffix only:
        a client fully controls the filename, so this filters
        accidents and casual misuse, not an attacker.
        """

        if not filename:
            raise UploadRejected(
                f"No filename was supplied for this "
                f"{self.label} upload."
            )

        # Only the final component is considered, so a path
        # traversal attempt in the filename cannot be laundered
        # into a plausible extension.
        safe_name = Path(
            filename
        ).name

        extension = Path(safe_name).suffix.lower()

        if not extension:
            raise UploadRejected(
                f"Unsupported {self.label} type: "
                f"'{safe_name}' has no extension. "
                f"Allowed: "
                f"{self.allowed_extension_list()}."
            )

        if extension not in self.allowed_extensions:
            raise UploadRejected(
                f"Unsupported {self.label} type: "
                f"'{extension}' is not accepted. "
                f"Allowed: "
                f"{self.allowed_extension_list()}."
            )

        return extension

    def allowed_extension_list(self) -> str:
        return ", ".join(
            sorted(self.allowed_extensions)
        )

    def copy_stream_to(
        self,
        source: BinaryIO,
        destination: Path,
        filename: str | None = None,
    ) -> int:
        """
        Copy an upload to disk, refusing to exceed the limit.

        The copy is chunked and the running total is checked
        per chunk, so the limit is enforced while streaming.
        Reading the whole body first and then measuring it would
        mean the bytes are already in memory or on disk before
        the limit is known, which defeats the point.

        Returns the number of bytes written.
        """

        if filename is not None:
            self.validate_extension(filename)

        written = 0

        with destination.open("wb") as handle:
            while True:
                chunk = source.read(
                    CHUNK_BYTES
                )

                if not chunk:
                    break

                written += len(chunk)

                if written > self.max_bytes:
                    handle.close()
                    destination.unlink(
                        missing_ok=True
                    )
                    raise UploadRejected(
                        f"The {self.label} exceeds the "
                        f"maximum upload size of "
                        f"{self.max_bytes:,} bytes."
                    )

                handle.write(chunk)

        return written


def sanitise_filename(
    filename: str | None,
    fallback: str,
) -> str:
    """
    Reduce a client filename to a bare, safe basename.

    The client controls this string completely, so it is
    treated as hostile. Taking only the final path component
    and stripping separators means a name like
    "../../.env" becomes ".env", which then fails the extension
    check rather than escaping the upload directory.
    """

    if not filename:
        return fallback

    safe_name = Path(
        filename.replace("\\", "/")
    ).name

    cleaned = "".join(
        character
        for character in safe_name
        if character.isalnum()
        or character in "._- "
    ).strip()

    if not cleaned or cleaned in {".", ".."}:
        return fallback

    return cleaned