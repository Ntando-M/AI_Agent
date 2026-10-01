from __future__ import annotations

import json

import pandas as pd
import pytest
from pydantic import ValidationError

from data_analysis.agent import DataAnalysisAgent
from data_analysis.tool_models import (
    AnalysisPlan,
    BoxPlotInput,
    ChartByCategoryInput,
    DistributionChartInput,
    RelationshipChartInput,
    TimeSeriesChartInput,
)
from data_analysis.tool_registry import (
    get_dataframe_tool_registry,
    get_tool_data_source,
)
from models.response_models import AnalysisResponse


DATASET_PATH = "data/sample_sales.xlsx"


CHART_TOOLS = [
    "chart_revenue_by_category",
    "chart_revenue_over_time",
    "chart_monthly_revenue",
    "chart_distribution",
    "chart_relationship",
    "chart_box_plot",
]


@pytest.fixture(autouse=True)
def isolated_charts(tmp_path, monkeypatch):
    """
    Keep generated charts out of outputs/ during tests.
    """

    monkeypatch.setattr(
        "data_analysis.charts.DEFAULT_OUTPUT_DIRECTORY",
        tmp_path,
    )


# ========================================================
# CHART INPUT MODELS
# ========================================================


def test_category_chart_requires_both_columns():
    inputs = ChartByCategoryInput(
        category_column="Product",
        value_column="Revenue",
    )

    assert inputs.category_column == "Product"
    assert inputs.value_column == "Revenue"


def test_category_chart_rejects_empty_column():
    with pytest.raises(ValidationError):
        ChartByCategoryInput(
            category_column="",
            value_column="Revenue",
        )


def test_time_series_chart_input():
    inputs = TimeSeriesChartInput(
        date_column="Date",
        value_column="Revenue",
    )

    assert inputs.date_column == "Date"


def test_distribution_chart_bins_default_and_bounds():
    inputs = DistributionChartInput(
        value_column="Revenue",
    )

    assert inputs.bins == 10

    with pytest.raises(ValidationError):
        DistributionChartInput(
            value_column="Revenue",
            bins=1,
        )

    with pytest.raises(ValidationError):
        DistributionChartInput(
            value_column="Revenue",
            bins=500,
        )


def test_relationship_chart_requires_two_columns():
    inputs = RelationshipChartInput(
        x_column="Revenue",
        y_column="Quantity",
    )

    assert inputs.x_column == "Revenue"
    assert inputs.y_column == "Quantity"


def test_box_plot_input():
    inputs = BoxPlotInput(
        category_column="Product",
        value_column="Revenue",
    )

    assert inputs.category_column == "Product"


# ========================================================
# REGISTRATION
# ========================================================


def test_chart_tools_are_registered():
    registry = get_dataframe_tool_registry()

    for name in CHART_TOOLS:
        assert name in registry


def test_chart_tools_are_dataframe_tools():
    for name in CHART_TOOLS:
        assert get_tool_data_source(name) == (
            "dataframe"
        )


def test_every_chart_tool_has_a_description():
    registry = get_dataframe_tool_registry()

    for name in CHART_TOOLS:
        description = registry[name]["description"]

        assert description
        assert len(description) > 20


# ========================================================
# EXECUTION
# ========================================================


def test_chart_tool_writes_a_file():
    agent = DataAnalysisAgent(DATASET_PATH)

    dataframe, result = agent.execute_tool(
        agent.dataframe,
        "chart_revenue_by_category",
        {
            "category_column": "Product",
            "value_column": "Revenue",
        },
    )

    assert result["chart_type"] == "bar"

    path = result["path"]

    assert path.endswith("revenue_by_product.png")
    assert (agent.dataset_path.parent.parent / path).exists()


def test_chart_tool_leaves_working_dataframe_intact():
    agent = DataAnalysisAgent(DATASET_PATH)

    original_rows = len(agent.dataframe)

    dataframe, _ = agent.execute_tool(
        agent.dataframe,
        "chart_distribution",
        {
            "value_column": "Revenue",
            "bins": 5,
        },
    )

    assert len(dataframe) == original_rows
    assert isinstance(
        dataframe, pd.DataFrame
    )


def test_chart_tool_rejects_unknown_column():
    agent = DataAnalysisAgent(DATASET_PATH)

    with pytest.raises(
        ValueError,
        match="Missing required columns",
    ):
        agent.execute_tool(
            agent.dataframe,
            "chart_revenue_by_category",
            {
                "category_column": "NotAColumn",
                "value_column": "Revenue",
            },
        )


def test_chart_tool_rejects_non_numeric_value():
    agent = DataAnalysisAgent(DATASET_PATH)

    with pytest.raises(
        TypeError,
        match="must be numeric",
    ):
        agent.execute_tool(
            agent.dataframe,
            "chart_distribution",
            {
                "value_column": "Product",
            },
        )


def test_multiple_charts_in_one_plan():
    agent = DataAnalysisAgent(DATASET_PATH)

    plan = AnalysisPlan.model_validate(
        {
            "steps": [
                {
                    "tool": "chart_distribution",
                    "arguments": {
                        "value_column": "Revenue",
                        "bins": 5,
                    },
                },
                {
                    "tool": "chart_revenue_over_time",
                    "arguments": {
                        "date_column": "Date",
                        "value_column": "Revenue",
                    },
                },
            ]
        }
    )

    results = agent.execute_plan(plan)

    visualisations = (
        agent.collect_visualisations(results)
    )

    assert len(visualisations) == 2
    assert any(
        "revenue_distribution" in path
        for path in visualisations
    )
    assert any(
        "revenue_trend" in path
        for path in visualisations
    )


def test_visualisations_empty_when_no_chart_ran():
    agent = DataAnalysisAgent(DATASET_PATH)

    plan = AnalysisPlan.model_validate(
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

    results = agent.execute_plan(plan)

    assert (
        agent.collect_visualisations(results)
        == []
    )


def test_analyse_returns_visualisations():
    agent = DataAnalysisAgent(DATASET_PATH)

    def planner(messages):
        return json.dumps(
            {
                "steps": [
                    {
                        "tool": "chart_distribution",
                        "arguments": {
                            "value_column": "Revenue",
                            "bins": 5,
                        },
                    }
                ]
            }
        )

    def final(messages):
        return {
            "answer": "Distribution rendered.",
            "analysis_type": "visualisation",
            "confidence": 0.9,
        }

    result = agent.analyse(
        "plot the revenue distribution",
        planner,
        final,
    )

    assert len(result["visualisations"]) == 1


# ========================================================
# PROMPTS
# ========================================================


def test_planning_prompt_lists_chart_tools():
    agent = DataAnalysisAgent(DATASET_PATH)

    prompt = agent.build_planning_prompt(
        "chart revenue by product"
    )

    for name in CHART_TOOLS:
        assert name in prompt


def test_planning_prompt_warns_against_chart_spam():
    agent = DataAnalysisAgent(DATASET_PATH)

    prompt = agent.build_planning_prompt(
        "what is the total revenue"
    )

    normalised = " ".join(prompt.split())

    assert (
        "Never use a chart tool just to answer "
        "a numeric question." in normalised
    )


def test_results_prompt_forbids_invented_charts():
    agent = DataAnalysisAgent(DATASET_PATH)

    prompt = agent.build_results_prompt(
        "chart revenue",
        [
            {
                "tool": "chart_distribution",
                "result": {
                    "chart_type": "histogram",
                    "path": "outputs/charts/revenue_distribution.png",
                },
            }
        ],
    )

    assert (
        "Do not claim a chart was generated"
        in prompt
    )
    assert "revenue_distribution.png" in prompt


# ========================================================
# ANALYSIS RESPONSE MODEL
# ========================================================


def test_analysis_response_minimal_payload():
    response = AnalysisResponse.model_validate(
        {
            "answer": "Total revenue is R274,000.",
            "analysis_type": "dataset",
            "confidence": 0.95,
        }
    )

    assert response.datasets_used == []
    assert response.calculations_performed == []
    assert response.key_findings == []
    assert response.sources == []


def test_analysis_response_full_payload():
    response = AnalysisResponse.model_validate(
        {
            "answer": "Laptop leads revenue.",
            "analysis_type": "dataset",
            "datasets_used": ["sample_sales.xlsx"],
            "calculations_performed": [
                "group_by_column Product sum Revenue"
            ],
            "key_findings": [
                "Laptop revenue is R210,000"
            ],
            "sources": ["data/sample_sales.xlsx"],
            "confidence": 0.9,
        }
    )

    assert len(response.key_findings) == 1
    assert response.analysis_type == "dataset"


@pytest.mark.parametrize(
    "analysis_type",
    [
        "general",
        "document",
        "dataset",
        "database",
        "visualisation",
    ],
)
def test_analysis_response_accepts_every_type(
    analysis_type,
):
    response = AnalysisResponse.model_validate(
        {
            "answer": "x",
            "analysis_type": analysis_type,
            "confidence": 0.5,
        }
    )

    assert response.analysis_type == analysis_type


def test_analysis_response_rejects_unknown_type():
    with pytest.raises(ValidationError):
        AnalysisResponse.model_validate(
            {
                "answer": "x",
                "analysis_type": "not_a_type",
                "confidence": 0.5,
            }
        )


def test_analysis_response_rejects_out_of_range_confidence():
    for value in [-0.1, 1.1]:
        with pytest.raises(ValidationError):
            AnalysisResponse.model_validate(
                {
                    "answer": "x",
                    "analysis_type": "general",
                    "confidence": value,
                }
            )


def test_analysis_response_has_no_topic_or_difficulty():
    fields = AnalysisResponse.model_fields

    assert "topic" not in fields
    assert "difficulty" not in fields


def test_groq_schema_matches_response_model():
    from llm.groq_provider import (
        ANALYSIS_RESPONSE_SCHEMA,
    )

    assert set(
        ANALYSIS_RESPONSE_SCHEMA["required"]
    ) == set(AnalysisResponse.model_fields)

    assert set(
        ANALYSIS_RESPONSE_SCHEMA["properties"]
    ) == set(AnalysisResponse.model_fields)


def test_ollama_provider_uses_analysis_response():
    from llm import ollama_provider

    source = (
        ollama_provider.__file__
    )

    with open(source, encoding="utf-8") as handle:
        content = handle.read()

    assert "AIResponse" not in content
    assert "AnalysisResponse" in content