from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourcePlan:
    """
    Which evidence sources a question requires.

    A plan is a set, not a single destination. V8 requires
    one question to be able to draw on documents and
    quantitative evidence together, so a plan may request
    several sources at once.
    """

    documents: bool = False
    dataset: bool = False
    database: bool = False
    chart: bool = False

    reasons: list[str] = field(
        default_factory=list
    )

    @property
    def is_empty(self) -> bool:
        return not (
            self.documents
            or self.dataset
            or self.database
            or self.chart
        )

    @property
    def is_multi_source(self) -> bool:
        """
        More than one kind of evidence was requested.
        """

        return (
            sum(
                [
                    self.documents,
                    self.dataset,
                    self.database,
                    self.chart,
                ]
            )
            > 1
        )

    def requested_sources(self) -> list[str]:
        names = []

        if self.documents:
            names.append("documents")

        if self.dataset:
            names.append("dataset")

        if self.database:
            names.append("database")

        if self.chart:
            names.append("charts")

        return names


# Signal vocabulary. Each entry is a phrase whose presence
# in a question signals that evidence source.

DOCUMENT_SIGNALS = (
    "document",
    "documents",
    "policy",
    "policies",
    "report",
    "roadmap",
    "strategy",
    "strategic",
    "manual",
    "handbook",
    "guideline",
    "guidelines",
    "according to",
    "summarise",
    "summarize",
    "tell me about",
    "explain what",
    "describe the",
)

# The bare question openers "what is the", "what does the"
# and "what do the" are deliberately NOT document signals.
# They are question forms, not evidence signals: "what is
# the total revenue?" and "what is the refund policy?" share
# the same opener, so treating it as a document signal sent
# ordinary analytical questions through document retrieval
# for nothing. A document question is identified by a
# document noun or by qualitative intent, both of which
# appear below.

# Phrases that name a document as the SUBJECT of the
# question, rather than merely hinting that a document might
# be involved. "What does the strategy document say about
# revenue?" asks for a reading; "revenue" is the document's
# subject matter, not a request to calculate it.
#
# Only the concrete document nouns appear here. The generic
# patterns in DOCUMENT_SIGNALS ("what does the", "summarise")
# are deliberately excluded: they co-occur with real
# analytical questions such as "what is the total revenue?",
# where suppressing the dataset would be wrong.

DOCUMENT_SCOPE_SIGNALS = (
    "document",
    "documents",
    "policy",
    "policies",
    "report",
    "roadmap",
    "strategy",
    "strategic",
    "manual",
    "handbook",
    "guideline",
    "guidelines",
)

# Signals that the answer lives in a document rather than
# being produced by calculation.

EXPLANATORY_SIGNALS = (
    "why",
    "reason",
    "because",
    "cause",
    "caused",
    "driver",
    "drivers",
    "explain the decline",
    "what happened",
    "how did this happen",
)

# Qualitative requests, where the user wants text rather than
# a computed figure. These carry the document intent that the
# bare question openers used to provide, without also firing
# on "what is the total revenue?".
#
# Only the qualitative verbs are here. "How many" and "how
# much" are deliberately excluded: they ask for a count or an
# amount, which is calculation, not reading.

DOCUMENT_INTENT_SIGNALS = (
    "say about",
    "says about",
    "say regarding",
    "mention",
    "mentions",
    "state about",
    "states about",
    "recommend",
    "recommends",
    "recommendation",
    "recommendations",
    "according to",
    "set out",
    "outline",
    "summarise",
    "summarize",
)

DATASET_SIGNALS = (
    "dataset",
    "data",
    "rows",
    "columns",
    "revenue",
    "sales",
    "units",
    "average",
    "mean",
    "median",
    "total",
    "maximum",
    "minimum",
    "highest",
    "lowest",
    "top",
    "region",
    "product",
    "monthly",
    "month",
    "missing",
    "percentage",
    "statistics",
    "statistic",
    "group",
    "sort",
    "filter",
    "how many",
    "how much",
    "count",
    "satisfaction",
)

CHART_SIGNALS = (
    "chart",
    "charts",
    "plot",
    "graph",
    "visualise",
    "visualize",
    "visualisation",
    "visualization",
    "bar chart",
    "line chart",
    "scatter",
    "histogram",
    "trend",
    "picture",
)

DATABASE_SIGNALS = (
    "database",
    "sql",
    "table",
    "tables",
    "record",
    "records",
    "schema",
    "query",
)


def _contains_any(
    question: str,
    signals: tuple[str, ...],
) -> list[str]:
    lowered = question.lower()

    return [
        signal
        for signal in signals
        if signal in lowered
    ]


def classify_question(
    question: str,
) -> SourcePlan:
    """
    Decide which evidence sources a question requires.

    This replaces the old exclusive keyword branch, which
    sent a question down exactly one path. A plan is a set,
    so a question can request documents and a dataset at
    the same time and be answered from both.

    Classification is deterministic and runs before any LLM
    call, so a routing decision is cheap, testable, and
    never consumes a model turn.
    """

    reasons: list[str] = []

    document_hits = _contains_any(
        question,
        DOCUMENT_SIGNALS,
    )

    explanatory_hits = _contains_any(
        question,
        EXPLANATORY_SIGNALS,
    )

    dataset_hits = _contains_any(
        question,
        DATASET_SIGNALS,
    )

    chart_hits = _contains_any(
        question,
        CHART_SIGNALS,
    )

    database_hits = _contains_any(
        question,
        DATABASE_SIGNALS,
    )

    document_scope_hits = _contains_any(
        question,
        DOCUMENT_SCOPE_SIGNALS,
    )

    document_intent_hits = _contains_any(
        question,
        DOCUMENT_INTENT_SIGNALS,
    )

    wants_documents = bool(
        document_hits
        or explanatory_hits
        or document_intent_hits
    )

    wants_database = bool(database_hits)

    wants_chart = bool(chart_hits)

    # A question whose subject is a named document is asking
    # for a reading of that document. Quantitative words in
    # its subject matter ("...say about revenue") describe
    # what the document is about, not a request to compute
    # them, so they must not also route it to the dataset.
    #
    # The exception is an explanatory question: "why did
    # revenue decline, according to the strategy document?"
    # genuinely needs the numbers and the document, and that
    # multi-source case is what V8 exists to support. An
    # explicit database signal counts the same way, since
    # that is an unambiguous request to query.
    document_scoped = (
        bool(document_scope_hits)
        and not explanatory_hits
        and not database_hits
    )

    if document_scoped:
        wants_dataset = bool(chart_hits)
    else:
        wants_dataset = bool(
            dataset_hits or chart_hits
        )

    if document_hits:
        reasons.append(
            "document signal: "
            + ", ".join(document_hits)
        )

    if document_scoped:
        reasons.append(
            "document is the subject; quantitative terms "
            "treated as its subject matter, not a "
            "calculation request"
        )

    if explanatory_hits:
        reasons.append(
            "explanatory signal: "
            + ", ".join(explanatory_hits)
        )

    if dataset_hits:
        reasons.append(
            "dataset signal: "
            + ", ".join(dataset_hits)
        )

    if chart_hits:
        reasons.append(
            "chart signal: "
            + ", ".join(chart_hits)
        )

    if database_hits:
        reasons.append(
            "database signal: "
            + ", ".join(database_hits)
        )

    return SourcePlan(
        documents=wants_documents,
        dataset=wants_dataset,
        database=wants_database,
        chart=wants_chart,
        reasons=reasons,
    )


def describe_plan(plan: SourcePlan) -> str:
    """
    Human-readable summary of a routing decision, used in
    prompts and diagnostics.
    """

    if plan.is_empty:
        return "No specific source requested."

    return " + ".join(
        plan.requested_sources()
    )


def plan_as_dict(
    plan: SourcePlan,
) -> dict[str, Any]:
    return {
        "documents": plan.documents,
        "dataset": plan.dataset,
        "database": plan.database,
        "chart": plan.chart,
        "is_multi_source": (
            plan.is_multi_source
        ),
        "requested_sources": (
            plan.requested_sources()
        ),
        "reasons": list(plan.reasons),
    }