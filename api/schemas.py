"""Typed request and response bodies for the HTTP API.

Separate from the FastAPI app so the API contract can be
tested and reviewed without importing the framework, and so
the ASP.NET Core layer has one obvious place to mirror.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AnalysisType = Literal[
    "general",
    "document",
    "dataset",
    "database",
    "visualisation",
]


class ChatRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Conversation to append this exchange to. "
            "Created automatically if it does not exist."
        ),
    )

    message: str = Field(
        min_length=1,
        max_length=8000,
        description="The user's question.",
    )


class AnalysisPayload(BaseModel):
    """The AnalysisResponse contract, unchanged."""

    answer: str

    analysis_type: AnalysisType

    datasets_used: list[str] = Field(
        default_factory=list
    )

    calculations_performed: list[str] = Field(
        default_factory=list
    )

    key_findings: list[str] = Field(
        default_factory=list
    )

    sources: list[str] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class ChatResponse(BaseModel):
    session_id: str

    response: AnalysisPayload

    visualisations: list[str] = Field(
        default_factory=list
    )

    tools_used: list[str] = Field(
        default_factory=list
    )

    source_labels: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


class SessionPayload(BaseModel):
    session_id: str
    message_count: int
    created_at: str | None = None
    last_activity_at: str | None = None
    preview: str | None = None
    name: str


class CreateSessionRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        max_length=200,
    )

    name: str | None = Field(
        default=None,
        max_length=120,
    )


class TurnPayload(BaseModel):
    """
    One stored turn.

    `evidence` is present only on assistant turns recorded
    after answers began carrying their supporting metadata.
    It is optional rather than defaulted so a restored turn
    can be told apart from one that genuinely had no
    evidence - the client renders the first as answer-only
    instead of as a finding with zero confidence.
    """

    role: str
    content: str
    created_at: str | None = None
    evidence: dict[str, Any] | None = None


class SessionDetail(BaseModel):
    session_id: str
    turns: list[TurnPayload] = Field(
        default_factory=list
    )


class DeleteResponse(BaseModel):
    session_id: str
    deleted: bool


class DeleteUploadResponse(BaseModel):
    """
    The result of deleting an upload.

    `name` rather than `session_id`, and `chunks_removed` so
    a document delete reports how much of the index went with
    it - the file and the vectors are removed together, and
    the caller should be able to see both halves happened.
    """

    name: str
    deleted: bool
    chunks_removed: int = 0


class AnalyseRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=8000
    )

    session_id: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Optional conversation to read context from. "
            "Omit for a stateless question."
        ),
    )


class AnalyseResponse(BaseModel):
    response: AnalysisPayload

    visualisations: list[str] = Field(
        default_factory=list
    )

    tools_used: list[str] = Field(
        default_factory=list
    )

    plan: dict[str, Any] = Field(
        default_factory=dict
    )

    warnings: list[str] = Field(
        default_factory=list
    )


class DatasetPayload(BaseModel):
    name: str
    path: str
    rows: int | None = None
    columns: list[str] = Field(
        default_factory=list
    )
    registered: bool = True


class DatasetListResponse(BaseModel):
    datasets: list[DatasetPayload] = Field(
        default_factory=list
    )


class UploadResponse(BaseModel):
    filename: str
    stored_path: str
    size_bytes: int
    indexed: bool
    chunks: int = 0
    message: str


class DocumentListResponse(BaseModel):
    documents: list[str] = Field(
        default_factory=list
    )


class GenerateReportRequest(BaseModel):
    """
    A request to generate a report for the loaded dataset.

    `session_id` is optional: a report can be generated
    without being attached to a conversation, and the
    reports page lists both.
    """

    session_id: str | None = None


class ReportPayload(BaseModel):
    """
    One generated report.

    `content` is the plain-text rendering and remains the
    canonical artefact. The structured fields are additive:
    they let the client render the four evidence layers as
    distinct sections instead of re-parsing the text, and
    `chart_images` carries each chart as a data URL so the
    browser can display it through the JSON proxy, which
    cannot carry PNG bytes.
    """

    report_id: str
    session_id: str | None = None
    content: str

    created_at: str | None = None
    dataset_name: str | None = None

    summary: dict[str, Any] = Field(
        default_factory=dict
    )

    layers: dict[str, list[str]] = Field(
        default_factory=dict
    )

    # Chart name -> path on disk.
    charts: dict[str, str] = Field(
        default_factory=dict
    )

    # Chart name -> "data:image/png;base64,...".
    chart_images: dict[str, str] = Field(
        default_factory=dict
    )


class ReportSummaryPayload(BaseModel):
    """A report as it appears in the list."""

    report_id: str
    session_id: str | None = None
    dataset_name: str | None = None
    created_at: str | None = None
    preview: str = ""


class HealthResponse(BaseModel):
    status: str
    provider: str
    dataset_loaded: bool
    database_loaded: bool
    documents_indexed: bool
    version: str


class ErrorResponse(BaseModel):
    detail: str