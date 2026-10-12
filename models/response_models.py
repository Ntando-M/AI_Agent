from typing import Literal

from pydantic import BaseModel, Field, field_validator


AnalysisType = Literal[
    "general",
    "document",
    "dataset",
    "database",
    "visualisation",
]


class AnalysisResponse(BaseModel):
    """
    The structured response returned by the AI Data Analyst.

    Replaces the original AIResponse, whose topic and difficulty
    fields had no meaning for an analytical system. These fields
    record which evidence was used, so a finding can be traced
    back to the tool that produced it.
    """

    answer: str = Field(
        description=(
            "The complete answer to the user's question, "
            "written in clear natural language"
        )
    )

    analysis_type: AnalysisType = Field(
        description=(
            "The kind of analysis performed: general chat, "
            "document retrieval, dataset calculation, "
            "database query, or visualisation"
        )
    )

    datasets_used: list[str] = Field(
        default_factory=list,
        description=(
            "The names of the datasets or database tables "
            "used to produce the answer"
        ),
    )

    calculations_performed: list[str] = Field(
        default_factory=list,
        description=(
            "A description of each deterministic calculation "
            "or query that was actually executed"
        ),
    )

    key_findings: list[str] = Field(
        default_factory=list,
        description=(
            "The most important findings, each stated as a "
            "concrete result supported by the evidence"
        ),
    )

    sources: list[str] = Field(
        default_factory=list,
        description=(
            "The documents, filenames or database tables that "
            "provided the evidence. Empty when no source was used."
        ),
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The model's confidence in the answer, from 0.0 to "
            "1.0. Reduce this when the evidence is incomplete."
        ),
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, value):
        """
        Clamp confidence to [0.0, 1.0].

        LLMs frequently return confidence as a percentage (e.g. 100)
        even when the schema says 0.0-1.0. Rather than rejecting the
        entire response, scale values above 1.0 down to the valid
        range. Values already in range pass through unchanged.
        """
        if value is None:
            return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if numeric > 1.0:
            return 1.0
        if numeric < 0.0:
            return 0.0
        return numeric
