"""Application settings, read from the environment.

Every setting has a working default so the service starts
without configuration, but the secret is the exception: a
missing API key is a hard startup error rather than a
silently open service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """
    Resolved once at startup.

    The provider is owned here rather than per request. A
    caller chooses the model through configuration, not
    through an argument, so every request is answered by
    the same engine. A later per-request override is a
    change to this object and the factory below, not to
    the endpoints.
    """

    provider: str = "groq"

    api_key_header: str = "X-API-Key"

    api_key: str | None = None

    dataset_path: str = "data/sample_sales.xlsx"

    analytics_database_path: str = "data/sales.db"

    chat_database_url: str = (
        "sqlite:///chat_history.db"
    )

    documents_directory: str = "documents"

    dataset_upload_directory: str = (
        "data/uploads"
    )

    reports_directory: str = "reports"

    # Where generated chart PNGs are written and read
    # from. It matches DEFAULT_OUTPUT_DIRECTORY in
    # data_analysis/charts.py, so the charts a report
    # references are the ones the analysis path wrote.
    chart_directory: str = "outputs/charts"

    version: str = "0.9.0"

    # V10 hardening. Both limits are configurable so a real
    # deployment can raise them without a code change, and so
    # a test can set an absurdly small one to exercise the
    # rejection path cheaply.
    max_dataset_upload_bytes: int = 10 * 1024 * 1024

    max_document_upload_bytes: int = 10 * 1024 * 1024

    analysis_timeout_seconds: float = 300.0

    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: (
            "http://localhost:4200",
            "http://127.0.0.1:4200",
        )
    )

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv(
            "API_ALLOWED_ORIGINS",
            "http://localhost:4200,"
            "http://127.0.0.1:4200",
        )

        return cls(
            provider=os.getenv(
                "LLM_PROVIDER", "groq"
            ).strip().lower(),
            api_key_header=os.getenv(
                "API_KEY_HEADER", "X-API-Key"
            ),
            api_key=os.getenv("API_KEY"),
            dataset_path=os.getenv(
                "API_DATASET_PATH",
                "data/sample_sales.xlsx",
            ),
            analytics_database_path=os.getenv(
                "API_ANALYTICS_DB_PATH",
                "data/sales.db",
            ),
            chat_database_url=os.getenv(
                "API_CHAT_DB_URL",
                "sqlite:///chat_history.db",
            ),
            documents_directory=os.getenv(
                "API_DOCUMENTS_DIR", "documents"
            ),
            dataset_upload_directory=os.getenv(
                "API_DATASET_UPLOAD_DIR",
                "data/uploads",
            ),
            reports_directory=os.getenv(
                "API_REPORTS_DIR", "reports"
            ),
            chart_directory=os.getenv(
                "API_CHART_DIR", "outputs/charts"
            ),
            max_dataset_upload_bytes=int(
                os.getenv(
                    "API_MAX_DATASET_UPLOAD_BYTES",
                    str(10 * 1024 * 1024),
                )
            ),
            max_document_upload_bytes=int(
                os.getenv(
                    "API_MAX_DOCUMENT_UPLOAD_BYTES",
                    str(10 * 1024 * 1024),
                )
            ),
            analysis_timeout_seconds=float(
                os.getenv(
                    "API_ANALYSIS_TIMEOUT_SECONDS",
                    "300",
                )
            ),
            allowed_origins=tuple(
                origin.strip()
                for origin in origins.split(",")
                if origin.strip()
            ),
        )

    # ====================================================
    # DERIVED PATHS
    # ====================================================

    def analytics_database_exists(self) -> bool:
        return Path(
            self.analytics_database_path
        ).exists()

    def dataset_exists(self) -> bool:
        return Path(self.dataset_path).exists()


def require_api_key(
    settings: Settings,
) -> str:
    """
    Return the configured secret or fail loudly.

    Defaulting to "no key required" would ship an open
    endpoint that can read every dataset and delete every
    session. Refusing to start is the safer failure.
    """

    if not settings.api_key:
        raise RuntimeError(
            "API_KEY is not set. The service refuses to "
            "start without a key, because every endpoint "
            "requires one. Set API_KEY in .env."
        )

    return settings.api_key