from __future__ import annotations

"""
Regression tests for the reasoning-model failure modes.

gpt-oss-20b on Groq produced three distinct failures that
surfaced as one opaque error, and none were covered because
every other test injects a stub gateway. These tests pin the
fixes at the unit level; no network call is made.
"""

import json
from types import SimpleNamespace

import pytest

from data_analysis.agent import (
    DataAnalysisAgent,
    strip_code_fences as agent_strip,
)
from llm.groq_provider import (
    MAX_COMPLETION_TOKENS,
    extract_content,
    strip_code_fences as provider_strip,
)


# ====================================================
# CODE FENCE STRIPPING
# ====================================================


FENCE_CASES = [
    ('```json\n{"steps": []}\n```', "json tag"),
    ("```\n{\"steps\": []}\n```", "bare fence"),
    ('```JSON\n{"steps": []}\n```', "uppercase tag"),
    ('```json\n[{"tool": "x"}]\n```', "fenced list"),
    ('{"steps": []}', "no fence"),
    ('```json\n{"a": 1}', "unclosed fence"),
    ('```json\n{"a": 1}\n```\n', "trailing newline"),
]


@pytest.mark.parametrize(
    "raw, label",
    FENCE_CASES,
)
def test_fenced_json_becomes_parseable(raw, label):
    """
    gpt-oss-20b routinely wraps JSON in a markdown fence even
    when told to return only JSON. json.loads rejects the
    fence outright, which failed the whole analysis turn.
    """

    stripped = provider_strip(raw)

    parsed = json.loads(stripped)

    assert isinstance(parsed, (dict, list))


def test_plain_text_is_untouched():
    assert provider_strip(
        "just some prose"
    ) == "just some prose"


def test_empty_input_is_safe():
    assert provider_strip("") == ""
    assert provider_strip(None) is None


def test_agent_and_provider_strip_agree():
    """
    The helper is duplicated across the module boundary on
    purpose. If the two copies drift, a plan accepted by one
    would be rejected by the other.
    """

    for raw, _ in FENCE_CASES:
        assert agent_strip(raw) == provider_strip(raw)


# ====================================================
# RESPONSE EXTRACTION
# ====================================================


def make_response(
    content=None,
    tool_calls=None,
    finish_reason="stop",
):
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=message,
                finish_reason=finish_reason,
            )
        ]
    )


def test_normal_content_is_returned():
    response = make_response(
        content='{"answer": "ok"}'
    )

    assert (
        extract_content(response)
        == '{"answer": "ok"}'
    )


def test_fenced_content_is_stripped():
    response = make_response(
        content='```json\n{"answer": "ok"}\n```'
    )

    assert (
        extract_content(response)
        == '{"answer": "ok"}'
    )


def test_empty_content_returns_none():
    """
    The reasoning model intermittently spends its whole token
    budget on reasoning and returns no content. The extractor
    must signal that so the caller can retry, rather than
    returning an empty string that would parse as nothing.
    """

    assert extract_content(
        make_response(content=None)
    ) is None


def test_tool_call_arguments_are_recovered():
    """
    This model sometimes emits a tool call even though no
    tools were offered and tool_choice is none, which the API
    rejects with 'Tool choice is none, but model called a
    tool'. The arguments are valid JSON and often the right
    answer, so they are recovered instead of discarded.
    """

    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            arguments='{"steps": [{"tool": "x"}]}'
        )
    )

    response = make_response(
        content=None,
        tool_calls=[tool_call],
    )

    extracted = extract_content(response)

    assert json.loads(extracted)["steps"]


def test_tool_call_is_used_when_content_is_missing():
    tool_call = SimpleNamespace(
        function=SimpleNamespace(arguments='{"a": 1}')
    )

    response = make_response(
        content=None,
        tool_calls=[tool_call],
    )

    assert extract_content(response) == '{"a": 1}'


def test_nothing_usable_returns_none():
    response = make_response(
        content=None,
        tool_calls=None,
        finish_reason="length",
    )

    assert extract_content(response) is None


def test_token_cap_leaves_room_for_the_answer():
    """
    The cap has to cover reasoning tokens plus the answer,
    but not so much that reasoning can consume it all.

    At 4096 the model spent 4094 tokens on reasoning and
    returned nothing, costing 7229 tokens per call - 90% of
    the 8000 TPM free-tier limit. 1536 keeps reasoning plus a
    short JSON answer inside the budget.
    """

    assert MAX_COMPLETION_TOKENS < 2048
    assert MAX_COMPLETION_TOKENS >= 1024


# ====================================================
# PLAN PARSING
# ====================================================


def agent_with_dataset(tmp_path):
    """
    A minimal agent instance for exercising parse_plan, which
    needs no provider and no database.
    """

    import pandas as pd

    path = tmp_path / "sales.csv"
    pd.DataFrame(
        {"Revenue": [1]}
    ).to_csv(path, index=False)

    return DataAnalysisAgent(str(path))


def test_fenced_plan_is_accepted(tmp_path):
    """
    The end-to-end failure: the planner returned a fenced
    block and parse_plan raised "invalid JSON analysis plan",
    failing the turn with no evidence gathered.
    """

    agent = agent_with_dataset(tmp_path)

    plan = agent.parse_plan(
        '```json\n{"steps": [{"tool": "inspect_dataset",'
        ' "arguments": {}}]}\n```'
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].tool == "inspect_dataset"


def test_bare_list_plan_is_still_accepted(tmp_path):
    agent = agent_with_dataset(tmp_path)

    plan = agent.parse_plan(
        '[{"tool": "inspect_dataset", "arguments": {}}]'
    )

    assert len(plan.steps) == 1


def test_wrapped_plan_is_accepted(tmp_path):
    agent = agent_with_dataset(tmp_path)

    plan = agent.parse_plan(
        '{"steps": [{"tool": "inspect_dataset",'
        ' "arguments": {}}]}'
    )

    assert len(plan.steps) == 1


def test_fenced_plan_gains_no_tools_when_invalid(tmp_path):
    """
    A fence around genuinely invalid JSON must still be
    rejected. Stripping the fence must not make the parser
    more permissive about content.
    """

    agent = agent_with_dataset(tmp_path)

    with pytest.raises(ValueError):
        agent.parse_plan(
            '```json\n{"steps": "not a list"}\n```'
        )


def test_unknown_tool_survives_parsing_but_fails_execution(
    tmp_path,
):
    """
    parse_plan validates the SHAPE of a plan, not the tools in
    it. An invented tool name parses fine and is rejected when
    the step runs, which is the existing dispatch contract
    covered by tests/test_v6_tool_dispatch.py.

    Asserting rejection at parse time would have been wrong:
    it would couple the plan model to the registry.
    """

    agent = agent_with_dataset(tmp_path)

    plan = agent.parse_plan(
        '{"steps": [{"tool": "rm_rf", "arguments": {}}]}'
    )

    assert plan.steps[0].tool == "rm_rf"

    with pytest.raises(Exception):
        agent.execute_plan(plan)