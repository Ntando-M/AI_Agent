from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage

from data_analysis.agent import DataAnalysisAgent
from models.response_models import AnalysisResponse
from orchestrator.intent import (
    SourcePlan,
    classify_question,
    plan_as_dict,
)
from orchestrator.llm_gateway import (
    LLMGateway,
    build_messages,
)
from rag.retriever import (
    format_context_for_prompt,
    retrieve_relevant_chunks,
)


ORCHESTRATOR_SYSTEM_PROMPT = """
You are the integrated response component of an AI Data
Analyst.

Answer the user's question accurately and clearly.

When retrieved document context is provided, use it when
relevant, and cite the document it came from. Distinguish
what a document states from what a calculation produced.

Do not invent information that is not supported by the
provided context, tool results or conversation.

Your response must contain:
- answer
- analysis_type
- datasets_used
- calculations_performed
- key_findings
- sources
- confidence

Analysis type must be one of:
- general
- document
- dataset
- database
- visualisation

Datasets used, calculations performed, key findings and
sources are lists. Use an empty list when nothing applies.

Sources must name the documents or tables that provided the
evidence.

Confidence must be a value between 0 and 1. Lower it when the
available evidence is incomplete, and lower it when a tool
failed or the retrieved context did not actually address the
question.
""".strip()


GENERATED_ARTEFACT_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
)


def _is_generated_artefact(
    source: str,
    generated_paths: list[str] | None = None,
) -> bool:
    """
    Whether a claimed "source" is a file this run produced.

    A chart path is an output, not evidence. Reporting it as
    a source tells the reader nothing they can verify, and
    it duplicates the visualisations list that already
    carries the path.

    Only paths the run actually wrote, plus generated
    output directories, count. ".pdf" is deliberately not
    treated as generated: a retrieved document is a
    legitimate source.
    """

    if generated_paths:
        normalised_outputs = {
            path.replace("\\", "/").lower()
            for path in generated_paths
        }

        if (
            source.replace("\\", "/").lower()
            in normalised_outputs
        ):
            return True

    lowered = source.lower().strip()

    if any(
        lowered.endswith(suffix)
        for suffix in GENERATED_ARTEFACT_SUFFIXES
    ):
        return True

    return (
        lowered.startswith("outputs")
        or lowered.startswith("reports")
    )


class Orchestrator:
    """
    Routes a question to every evidence source it needs and
    returns one validated AnalysisResponse.

    Design decisions:

    * Provider selection is NOT owned here. An LLMGateway is
      injected, already bound to a provider. The orchestrator
      imports no provider module, so routing is independent of
      which model is running and a stub gateway makes the whole
      class testable without an API key.

    * A question is answered from a SET of sources, not one.
      Retrieval and analysis run independently and their
      evidence is merged, so "why did revenue decline?" can be
      answered from both the dataset and a strategy document.

    * Every path returns the same AnalysisResponse contract.
      A caller never branches on which engine answered.
    """

    def __init__(
        self,
        gateway: LLMGateway,
        dataset_path: str | Path | None = None,
        database_path: str | Path | None = None,
        vector_store: Any | None = None,
        retrieval_k: int = 4,
    ):
        self.gateway = gateway

        self.dataset_label = (
            str(dataset_path)
            if dataset_path is not None
            else None
        )

        self.dataset_path = (
            Path(dataset_path)
            if dataset_path
            else None
        )

        self.vector_store = vector_store
        self.retrieval_k = retrieval_k

        self.data_agent: DataAnalysisAgent | None = (
            None
        )

        self.load_warnings: list[str] = []

        if self.dataset_path is not None:
            try:
                self.data_agent = DataAnalysisAgent(
                    self.dataset_path,
                    database_path=(
                        database_path
                    ),
                )
            except Exception as exc:
                self.load_warnings.append(
                    "Data-analysis agent could not "
                    f"load the dataset: {exc}"
                )

    @property
    def has_dataset(self) -> bool:
        return self.data_agent is not None

    @property
    def has_database(self) -> bool:
        return bool(
            self.data_agent
            and self.data_agent.has_database
        )

    # ====================================================
    # RETRIEVAL
    # ====================================================

    def retrieve(
        self,
        question: str,
    ) -> list[dict[str, Any]]:
        """
        Retrieve document chunks. A retrieval failure is
        recorded, never fatal - a question that needs
        documents can still be answered from the dataset.
        """

        try:
            return retrieve_relevant_chunks(
                question,
                vector_store=self.vector_store,
                k=self.retrieval_k,
            )
        except Exception as exc:
            self.load_warnings.append(
                f"RAG retrieval warning: {exc}"
            )

            return []

    def collect_source_labels(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[str]:
        """
        Distinct document filenames, sorted, so the same
        document retrieved twice is listed once.
        """

        return sorted(
            {
                chunk["filename"]
                for chunk in chunks
                if chunk.get("filename")
            }
        )

    # ====================================================
    # EVIDENCE MERGING
    # ====================================================

    def apply_evidence(
        self,
        response: dict[str, Any],
        source_labels: list[str],
        used_analysis: bool,
        tools_used: list[str] | None = None,
        generated_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Reconcile what the model claimed against what was
        actually retrieved or executed.

        The roadmap requires that sources and datasets are
        recorded so a finding can be traced. A model may
        under-report, so deterministic evidence fills the gap
        rather than trusting the model to remember.
        """

        executed_tools = tools_used or []

        if source_labels or executed_tools:
            # A model asked for tool names here sometimes
            # answers with the tool it ran, or with the path
            # of a file it just wrote. Neither is inspectable
            # evidence a reader could follow, so both are
            # stripped. Reconciliation is deterministic
            # rather than trusting the model to classify
            # its own evidence.
            model_sources = [
                source
                for source in response.get(
                    "sources", []
                )
                if source not in executed_tools
                and not _is_generated_artefact(
                    source,
                    generated_paths,
                )
            ]

            response["sources"] = list(
                dict.fromkeys(
                    [
                        *model_sources,
                        *source_labels,
                    ]
                )
            )

        if (
            used_analysis
            and not response.get("datasets_used")
            and self.dataset_label is not None
        ):
            response["datasets_used"] = [
                self.dataset_label
            ]

        return response

    def resolve_analysis_type(
        self,
        response: dict[str, Any],
        plan: SourcePlan,
        visualisations: list[str],
    ) -> str:
        """
        Determine the analysis type from evidence actually
        produced, not from the question's wording.
        """

        if visualisations:
            return "visualisation"

        if plan.database and self.has_database:
            return "database"

        if plan.dataset and not plan.documents:
            return "dataset"

        if plan.documents and not plan.dataset:
            return "document"

        return response.get(
            "analysis_type", "general"
        )

    # ====================================================
    # PATHS
    # ====================================================

    def answer_from_documents(
        self,
        question: str,
        chunks: list[dict[str, Any]],
        history: list[BaseMessage],
    ) -> dict[str, Any]:
        context = format_context_for_prompt(
            chunks
        )

        augmented_question = f"""
Use the following retrieved document context when relevant.

Retrieved context:
{context}

User question:
{question}
""".strip()

        messages = build_messages(
            ORCHESTRATOR_SYSTEM_PROMPT,
            augmented_question,
            history,
        )

        return self.gateway.structured(messages)

    def answer_from_analysis(
        self,
        question: str,
        chunks: list[dict[str, Any]],
        history: list[BaseMessage] | None = None,
    ) -> dict[str, Any]:
        """
        Run the deterministic engine, optionally enriched
        with retrieved document evidence.
        """

        if self.data_agent is None:
            raise RuntimeError(
                "No dataset is configured, so "
                "analytical tools cannot run."
            )

        document_context = ""

        if chunks:
            document_context = (
                format_context_for_prompt(chunks)
            )

        # The deterministic engine builds its own message
        # list. Wrapping the structured call is what lets a
        # follow-up question such as "what about the top
        # product?" see the prior turn: the history is
        # inserted between the synthesis prompt and the
        # question, so the model can refer back to the
        # earlier result instead of re-deriving it.

        conversation = history or []

        base_structured = self.gateway.structured

        def structured_with_history(messages):
            system_messages = messages[:-1]
            question_message = messages[-1]

            return base_structured(
                [
                    *system_messages,
                    *conversation,
                    question_message,
                ]
            )

        result = self.data_agent.analyse(
            question,
            self.gateway.raw,
            structured_with_history,
            document_context=document_context,
            history=conversation,
        )

        return {
            "response": result["response"],
            "visualisations": result.get(
                "visualisations", []
            ),
            "tools_used": [
                step["tool"]
                for step in result.get("plan", {}).get(
                    "steps", []
                )
            ],
            "results": result.get("results", []),
        }

    # ====================================================
    # ENTRY POINT
    # ====================================================

    def handle(
        self,
        question: str,
        history: list[BaseMessage] | None = None,
    ) -> dict[str, Any]:
        """
        Answer one question.

        Returns:
            response         - validated AnalysisResponse dict
            visualisations   - chart paths actually written
            tools_used       - deterministic tools executed
            plan             - the routing decision
            source_labels    - documents actually retrieved
        """

        history = history or []

        plan = classify_question(question)

        wants_documents = plan.documents
        wants_analysis = (
            plan.dataset
            or plan.database
            or plan.chart
        )

        chunks: list[dict[str, Any]] = []

        if wants_documents:
            chunks = self.retrieve(question)

        visualisations: list[str] = []
        tools_used: list[str] = []
        results: list[dict[str, Any]] = []
        used_analysis = False

        if (
            wants_analysis
            and self.data_agent is not None
        ):
            analysis = self.answer_from_analysis(
                question,
                chunks,
                history,
            )

            response = analysis["response"]
            visualisations = analysis["visualisations"]
            tools_used = analysis["tools_used"]
            results = analysis["results"]
            used_analysis = True

        elif wants_documents:
            response = self.answer_from_documents(
                question,
                chunks,
                history,
            )

        elif self.data_agent is not None:
            # No signal matched, but a dataset is configured.
            # Fall back to retrieval when documents exist,
            # otherwise treat it as general chat.

            try:
                chunks = self.retrieve(question)
            except Exception:
                chunks = []

            if chunks:
                response = self.answer_from_documents(
                    question,
                    chunks,
                    history,
                )
            else:
                response = self.gateway.structured(
                    build_messages(
                        ORCHESTRATOR_SYSTEM_PROMPT,
                        question,
                        history,
                    )
                )

        else:
            response = self.gateway.structured(
                build_messages(
                    ORCHESTRATOR_SYSTEM_PROMPT,
                    question,
                    history,
                )
            )

        source_labels = self.collect_source_labels(
            chunks
        )

        response = self.apply_evidence(
            response,
            source_labels,
            used_analysis,
            tools_used,
            visualisations,
        )

        response["analysis_type"] = (
            self.resolve_analysis_type(
                response,
                plan,
                visualisations,
            )
        )

        validated = AnalysisResponse.model_validate(
            response
        )

        return {
            "response": validated.model_dump(),
            "visualisations": visualisations,
            "tools_used": tools_used,
            "source_labels": source_labels,
            "plan": plan_as_dict(plan),
            "results": results,
        }