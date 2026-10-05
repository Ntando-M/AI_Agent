from __future__ import annotations

import json

import pandas as pd
import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from data_analysis.agent import DataAnalysisAgent
from models.response_models import AnalysisResponse
from orchestrator.intent import classify_question
from orchestrator.llm_gateway import LLMGateway
from orchestrator.orchestrator import Orchestrator


DATASET_PATH = "data/sample_sales.xlsx"
DATABASE_PATH = "data/sales.db"


# ========================================================
# STUB GATEWAY
# ========================================================


def make_response(**overrides) -> dict:
    payload = {
        "answer": "stub answer",
        "analysis_type": "general",
        "datasets_used": [],
        "calculations_performed": [],
        "key_findings": [],
        "sources": [],
        "confidence": 0.5,
    }

    payload.update(overrides)

    return payload


class StubGateway:
    """
    A pre-built gateway with no provider behind it.

    Constructing this instead of calling LLMGateway.build is
    what proves the orchestrator does not own provider
    selection: routing tests run with no API key and no
    network.
    """

    def __init__(
        self,
        plan=None,
        response=None,
        raw_text="",
    ):
        self.plan = plan or {
            "steps": [
                {
                    "tool": "aggregate_dataset",
                    "arguments": {
                        "column": "Revenue",
                        "operation": "sum",
                    },
                }
            ]
        }

        self.response = response or make_response()
        self.raw_text = raw_text
        self.raw_calls: list = []
        self.structured_calls: list = []

    def as_gateway(self) -> LLMGateway:
        return LLMGateway(
            provider="stub",
            raw_function=self.raw,
            structured_function=self.structured,
        )

    def raw(self, messages):
        self.raw_calls.append(messages)
        return self.raw_text or json.dumps(
            self.plan
        )

    def structured(self, messages):
        self.structured_calls.append(messages)
        return dict(self.response)

    def last_system_prompt(self) -> str:
        return self.structured_calls[-1][0].content


@pytest.fixture(autouse=True)
def isolated_charts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "data_analysis.charts.DEFAULT_OUTPUT_DIRECTORY",
        tmp_path,
    )


@pytest.fixture
def no_documents(monkeypatch):
    """
    Default: retrieval finds nothing, so a test that does not
    care about documents is not affected by RAG.
    """

    monkeypatch.setattr(
        "orchestrator.orchestrator.retrieve_relevant_chunks",
        lambda question, **kwargs: [],
    )


@pytest.fixture
def one_document(monkeypatch):
    chunks = [
        {
            "content": (
                "The Q3 strategy was to expand "
                "channel partner coverage."
            ),
            "filename": "strategy_2026.pdf",
            "page": 3,
            "source": "strategy_2026.pdf",
        }
    ]

    monkeypatch.setattr(
        "orchestrator.orchestrator.retrieve_relevant_chunks",
        lambda question, **kwargs: chunks,
    )

    return chunks


def build_orchestrator(
    stub,
    dataset_path=DATASET_PATH,
    database_path=None,
) -> Orchestrator:
    return Orchestrator(
        gateway=stub.as_gateway(),
        dataset_path=dataset_path,
        database_path=database_path,
    )


# ========================================================
# INTENT CLASSIFICATION
# ========================================================


def test_document_question_requests_documents():
    plan = classify_question(
        "What does the policy say about refunds?"
    )

    assert plan.documents is True
    assert plan.dataset is False


def test_dataset_question_requests_dataset():
    plan = classify_question(
        "What was the total revenue?"
    )

    assert plan.dataset is True
    assert plan.documents is False


def test_chart_question_requests_dataset_and_chart():
    plan = classify_question(
        "Plot revenue by product"
    )

    assert plan.chart is True
    assert plan.dataset is True


def test_explanatory_dataset_question_is_multi_source():
    """
    The roadmap's worked example: 'Why did revenue
    decline?' needs the numbers AND document context.
    """

    plan = classify_question(
        "Why did revenue decline in Q3?"
    )

    assert plan.dataset is True
    assert plan.documents is True
    assert plan.is_multi_source is True


def test_general_question_requests_nothing():
    plan = classify_question(
        "Hello there"
    )

    assert plan.is_empty is True


def test_plan_reasons_are_recorded():
    plan = classify_question(
        "What was the total revenue?"
    )

    assert plan.reasons


# ========================================================
# ACCEPTANCE 1 - DOCUMENT ONLY
# ========================================================


def test_document_only_question_uses_retrieval(
    one_document,
):
    stub = StubGateway(
        response=make_response(
            analysis_type="document",
            answer="Refunds are handled centrally.",
        )
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What does the policy say about refunds?"
    )

    assert result["plan"]["documents"] is True
    assert (
        result["source_labels"]
        == ["strategy_2026.pdf"]
    )
    assert "strategy_2026.pdf" in result[
        "response"
    ]["sources"]
    assert result["response"]["analysis_type"] == (
        "document"
    )


def test_document_answer_never_claims_a_dataset(
    one_document,
):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What does the policy say about refunds?"
    )

    assert (
        result["response"]["datasets_used"] == []
    )
    assert result["tools_used"] == []


# ========================================================
# ACCEPTANCE 2 - DATASET ONLY
# ========================================================


def test_dataset_only_question_runs_tools(
    no_documents,
):
    stub = StubGateway(
        response=make_response(
            analysis_type="dataset",
            answer="Total revenue was R274,000.",
            calculations_performed=[
                "aggregate_dataset Revenue sum"
            ],
        )
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What was the total revenue?"
    )

    assert result["tools_used"] == [
        "aggregate_dataset"
    ]
    assert (
        result["response"]["analysis_type"]
        == "dataset"
    )
    assert result["visualisations"] == []


def test_dataset_used_is_backfilled_when_model_omits_it(
    no_documents,
):
    """
    The roadmap requires recording which datasets were used.
    A model that forgets must not defeat the record.
    """

    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What was the total revenue?"
    )

    assert result["response"]["datasets_used"] == [
        DATASET_PATH
    ]


def test_dataset_used_is_not_overwritten_when_present(
    no_documents,
):
    stub = StubGateway(
        response=make_response(
            datasets_used=["sample_sales.xlsx"]
        )
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What was the total revenue?"
    )

    assert result["response"]["datasets_used"] == [
        "sample_sales.xlsx"
    ]


# ========================================================
# ACCEPTANCE 3 - SQL ONLY
# ========================================================


def test_sql_question_requires_a_database(no_documents):
    stub = StubGateway(
        plan={
            "steps": [
                {
                    "tool": "list_tables",
                    "arguments": {},
                }
            ]
        }
    )

    orchestrator = build_orchestrator(
        stub,
        database_path=DATABASE_PATH,
    )

    if not orchestrator.has_database:
        pytest.skip(
            "data/sales.db is absent; run "
            "scripts/create_sales_database.py"
        )

    result = orchestrator.handle(
        "Which tables are in the database?"
    )

    assert "list_tables" in result[
        "tools_used"
    ]
    assert result["response"]["analysis_type"] == (
        "database"
    )


def test_sql_tools_unavailable_without_a_database(
    no_documents,
):
    stub = StubGateway(
        plan={
            "steps": [
                {
                    "tool": "list_tables",
                    "arguments": {},
                }
            ]
        }
    )

    orchestrator = build_orchestrator(
        stub,
        database_path=None,
    )

    assert orchestrator.has_database is False

    tool_descriptions = (
        orchestrator.data_agent
        .get_available_tool_descriptions()
    )

    assert "list_tables" not in tool_descriptions


# ========================================================
# ACCEPTANCE 4 - MIXED DOCUMENT + DATASET
# ========================================================


def test_mixed_question_merges_both_sources(
    one_document,
):
    stub = StubGateway(
        response=make_response(
            analysis_type="general",
            answer=(
                "Revenue fell 59.6%; the strategy "
                "document records a channel expansion."
            ),
        )
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "Why did revenue decline in Q3?"
    )

    assert result["plan"]["is_multi_source"] is True
    assert result["tools_used"] == [
        "aggregate_dataset"
    ]
    assert result["source_labels"] == [
        "strategy_2026.pdf"
    ]

    sources = result["response"]["sources"]

    assert "strategy_2026.pdf" in sources


def test_mixed_question_sends_context_to_synthesis(
    one_document,
):
    """
    The document evidence must reach the synthesis prompt,
    not just be recorded in metadata.
    """

    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle("Why did revenue decline?")

    synthesis_prompt = stub.structured_calls[-1][
        0
    ].content

    assert "Retrieved document context" in (
        synthesis_prompt
    )
    assert "channel partner coverage" in (
        synthesis_prompt
    )


def test_context_section_absent_for_dataset_only(
    no_documents,
):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle("What was the total revenue?")

    synthesis_prompt = stub.structured_calls[-1][
        0
    ].content

    assert "Retrieved document context" not in (
        synthesis_prompt
    )


def test_document_and_numbers_are_prompted_apart(
    one_document,
):
    """
    The prompt must tell the model not to let a document
    statement override a calculated figure.
    """

    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle("Why did revenue decline?")

    synthesis_prompt = stub.structured_calls[-1][
        0
    ].content

    assert (
        "do not let it override the numbers"
        in synthesis_prompt
    )


# ========================================================
# ACCEPTANCE 5 - CHART
# ========================================================


def test_chart_request_returns_a_written_chart(
    no_documents,
):
    stub = StubGateway(
        plan={
            "steps": [
                {
                    "tool": "chart_revenue_by_category",
                    "arguments": {
                        "category_column": "Product",
                        "value_column": "Revenue",
                    },
                }
            ]
        },
        response=make_response(
            analysis_type="dataset",
            answer="Chart written.",
        ),
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "Plot revenue by product"
    )

    assert result["visualisations"]

    assert result["response"]["analysis_type"] == (
        "visualisation"
    )


def test_visualisation_type_wins_over_dataset(
    no_documents,
):
    """
    A chart question is a visualisation even though the
    planner also ran a dataframe tool.
    """

    stub = StubGateway(
        plan={
            "steps": [
                {
                    "tool": "chart_revenue_by_category",
                    "arguments": {
                        "category_column": "Product",
                        "value_column": "Revenue",
                    },
                }
            ]
        },
        response=make_response(
            analysis_type="dataset",
        ),
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "Plot revenue by product"
    )

    assert (
        result["response"]["analysis_type"]
        == "visualisation"
    )


def test_tool_name_is_not_reported_as_a_source(
    no_documents,
):
    """
    A model asked for tool names here sometimes answers
    with the tool it ran. A tool is not inspectable
    evidence, so it must not reach the sources list.
    """

    stub = StubGateway(
        response=make_response(
            sources=["aggregate_dataset"],
        )
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What was the total revenue?"
    )

    assert (
        "aggregate_dataset"
        not in result["response"]["sources"]
    )


def test_chart_path_is_not_reported_as_a_source(
    no_documents,
):
    stub = StubGateway(
        plan={
            "steps": [
                {
                    "tool": "chart_revenue_by_category",
                    "arguments": {
                        "category_column": "Product",
                        "value_column": "Revenue",
                    },
                }
            ]
        },
        response=make_response(
            sources=[
                "outputs\\\\charts\\\\revenue_by_product.png"
            ],
        ),
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "Plot revenue by product"
    )

    assert not any(
        ".png" in source
        for source in result["response"]["sources"]
    )


def test_real_document_source_survives_reconciliation(
    one_document,
):
    stub = StubGateway(
        response=make_response(
            sources=[
                "strategy_2026.pdf",
                "aggregate_dataset",
            ],
        )
    )

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "Why did revenue decline?"
    )

    sources = result["response"]["sources"]

    assert "strategy_2026.pdf" in sources
    assert "aggregate_dataset" not in sources


# ========================================================
# ACCEPTANCE 6 - FOLLOW-UP ON A PRIOR RESULT
# ========================================================


def test_follow_up_receives_history(no_documents):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    history = [
        HumanMessage(
            content="What was total revenue?"
        ),
        AIMessage(
            content="Total revenue was R274,000."
        ),
    ]

    orchestrator.handle(
        "What about the top product?",
        history=history,
    )

    messages = stub.structured_calls[-1]

    # History arrives as its own messages, not folded into
    # the prompt, so the model sees a real conversation and
    # a follow-up can refer back to the earlier figure.
    assert len(messages) == 4
    assert messages[1].content == (
        "What was total revenue?"
    )
    assert "R274,000" in messages[2].content
    assert messages[3].content == (
        "What about the top product?"
    )


def test_history_precedes_the_new_question(no_documents):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle(
        "What about the top product?",
        history=[
            HumanMessage(content="earlier_turn"),
            AIMessage(content="earlier_answer"),
        ],
    )

    messages = stub.structured_calls[-1]

    assert messages[1].content == "earlier_turn"
    assert (
        messages[-1].content
        == "What about the top product?"
    )


def test_no_history_means_no_prior_turns(
    no_documents,
):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle(
        "What was total revenue?"
    )

    messages = stub.structured_calls[-1]

    assert len(messages) == 2


def test_planner_receives_history(no_documents):
    """
    "What about the top product?" names no column, so
    without the prior turn the planner cannot produce a
    plan. History must reach the planning call.
    """

    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle(
        "What about the top product?",
        history=[
            HumanMessage(content="earlier_turn"),
            AIMessage(content="earlier_answer"),
        ],
    )

    messages = stub.raw_calls[-1]

    assert messages[1].content == "earlier_turn"
    assert messages[-1].content == (
        "What about the top product?"
    )


def test_no_history_means_planner_sees_two_messages(
    no_documents,
):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    orchestrator.handle("What was total revenue?")

    assert len(stub.raw_calls[-1]) == 2


def test_bare_step_list_is_accepted():
    """
    Small local models commonly return the step list
    directly. That is unambiguous, so it is normalised
    rather than failing the turn.
    """

    agent = DataAnalysisAgent(DATASET_PATH)

    plan = agent.parse_plan(
        json.dumps(
            [
                {
                    "tool": "aggregate_dataset",
                    "arguments": {
                        "column": "Revenue",
                        "operation": "sum",
                    },
                }
            ]
        )
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].tool == "aggregate_dataset"


def test_wrapped_plan_still_accepted():
    agent = DataAnalysisAgent(DATASET_PATH)

    plan = agent.parse_plan(
        json.dumps(
            {
                "steps": [
                    {
                        "tool": "aggregate_dataset",
                        "arguments": {
                            "column": "Revenue",
                            "operation": "sum",
                        },
                    }
                ]
            }
        )
    )

    assert len(plan.steps) == 1


def test_non_json_plan_is_rejected():
    agent = DataAnalysisAgent(DATASET_PATH)

    with pytest.raises(ValueError):
        agent.parse_plan("I think you should sum it")


def test_unknown_tool_is_rejected_at_execution():
    """
    The tool name is not validated at parse time - the plan
    model checks shape, the registry checks legitimacy. An
    invented tool must fail when executed, never run.
    """

    agent = DataAnalysisAgent(DATASET_PATH)

    plan = agent.parse_plan(
        json.dumps(
            {
                "steps": [
                    {
                        "tool": "rm_rf",
                        "arguments": {},
                    }
                ]
            }
        )
    )

    with pytest.raises(ValueError):
        agent.execute_plan(plan)


def test_empty_plan_is_rejected():
    agent = DataAnalysisAgent(DATASET_PATH)

    with pytest.raises(Exception):
        agent.parse_plan(
            json.dumps({"steps": []})
        )


# ========================================================
# ACCEPTANCE 7 - PROVIDER SWITCH
# ========================================================


def test_same_question_same_result_across_providers(
    no_documents,
):
    """
    Routing must not depend on which provider is bound.
    """

    payloads = []

    for provider in ("groq", "ollama"):
        stub = StubGateway(
            response=make_response(
                answer="R274,000"
            )
        )

        gateway = LLMGateway(
            provider=provider,
            raw_function=stub.raw,
            structured_function=stub.structured,
        )

        orchestrator = Orchestrator(
            gateway=gateway,
            dataset_path=DATASET_PATH,
        )

        result = orchestrator.handle(
            "What was the total revenue?"
        )

        payloads.append(result)

    assert (
        payloads[0]["response"]["answer"]
        == payloads[1]["response"]["answer"]
    )
    assert (
        payloads[0]["tools_used"]
        == payloads[1]["tools_used"]
    )
    assert (
        payloads[0]["plan"]
        == payloads[1]["plan"]
    )


def test_gateway_records_its_provider():
    stub = StubGateway()

    gateway = stub.as_gateway()

    assert gateway.provider == "stub"


def test_unsupported_provider_rejected():
    with pytest.raises(ValueError):
        LLMGateway.build("not-a-provider")


# ========================================================
# ACCEPTANCE 8 - SESSION ISOLATION
# ========================================================


def test_sessions_do_not_share_history(no_documents):
    """
    Two sessions answering the same question must produce
    independent prompts with no cross-contamination.
    """

    first_stub = StubGateway()
    first = build_orchestrator(first_stub)

    first.handle(
        "What was total revenue?",
        history=[
            HumanMessage(content="secret_a"),
            AIMessage(content="answer_a"),
        ],
    )

    second_stub = StubGateway()
    second = build_orchestrator(second_stub)

    second.handle(
        "What was total revenue?",
        history=[
            HumanMessage(content="secret_b"),
            AIMessage(content="answer_b"),
        ],
    )

    first_contents = [
        message.content
        for message in first_stub.structured_calls[-1]
    ]

    second_contents = [
        message.content
        for message in second_stub.structured_calls[-1]
    ]

    assert "secret_a" in first_contents
    assert "secret_a" not in second_contents
    assert "secret_b" in second_contents
    assert "secret_b" not in first_contents


# ========================================================
# RESILIENCE
# ========================================================


def test_retrieval_failure_does_not_break_the_answer(
    monkeypatch,
):
    def explode(question, **kwargs):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(
        "orchestrator.orchestrator.retrieve_relevant_chunks",
        explode,
    )

    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    # A multi-source question, so retrieval is actually
    # attempted. The dataset evidence must still answer.
    result = orchestrator.handle(
        "Why did revenue decline?"
    )

    assert result["response"]["answer"]
    assert result["tools_used"] == [
        "aggregate_dataset"
    ]
    assert orchestrator.load_warnings


def test_missing_dataset_still_answers_documents(
    monkeypatch,
    no_documents,
):
    stub = StubGateway(
        response=make_response(
            analysis_type="document",
        )
    )

    orchestrator = Orchestrator(
        gateway=stub.as_gateway(),
        dataset_path="data/does_not_exist.xlsx",
    )

    assert orchestrator.has_dataset is False

    result = orchestrator.handle(
        "What does the policy say about refunds?"
    )

    assert result["response"]["analysis_type"] == (
        "document"
    )


def test_general_question_without_a_dataset():
    stub = StubGateway()

    orchestrator = Orchestrator(
        gateway=stub.as_gateway(),
        dataset_path=None,
    )

    result = orchestrator.handle("Hello there")

    assert result["response"]["answer"]
    assert result["plan"]["documents"] is False


# ========================================================
# OUTPUT CONTRACT
# ========================================================


def test_every_path_returns_the_same_contract(
    one_document,
    no_documents,
):
    for question in (
        "What does the policy say about refunds?",
        "What was the total revenue?",
        "Hello there",
    ):
        stub = StubGateway()

        orchestrator = build_orchestrator(stub)

        result = orchestrator.handle(question)

        assert set(result["response"]) == set(
            AnalysisResponse.model_fields
        )


def test_every_response_validates(no_documents):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "What was the total revenue?"
    )

    validated = AnalysisResponse.model_validate(
        result["response"]
    )

    assert validated.confidence == 0.5


def test_out_of_range_confidence_is_rejected():
    with pytest.raises(Exception):
        AnalysisResponse.model_validate(
            make_response(confidence=1.5)
        )


def test_handle_reports_tools_and_sources(
    one_document,
):
    stub = StubGateway()

    orchestrator = build_orchestrator(stub)

    result = orchestrator.handle(
        "Why did revenue decline?"
    )

    assert set(result) >= {
        "response",
        "visualisations",
        "tools_used",
        "source_labels",
        "plan",
    }