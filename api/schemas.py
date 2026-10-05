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


class CreateSessionRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        max_length=200,
    )


class TurnPayload(BaseModel):
    role: str
    content: str
    created_at: str | None = None


class SessionDetail(BaseModel):
    session_id: str
    turns: list[TurnPayload] = Field(
        default_factory=list
    )


class DeleteResponse(BaseModel):
    session_id: str
    deleted: bool


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


class ReportPayload(BaseModel):
    report_id: str
    session_id: str | None = None
    content: str


class HealthResponse(BaseModel):
    status: str
    provider: str
    dataset_loaded: bool
    database_loaded: bool
    documents_indexed: bool
    version: str


class ErrorResponse(BaseModel):
    detail: str