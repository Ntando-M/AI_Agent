from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from data_analysis import load_dataset
from data_analysis.tool_models import AnalysisPlan
from data_analysis.tool_registry import get_tool_registry


class DataAnalysisAgent:
    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)

        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {self.dataset_path}"
            )

        self.dataframe = load_dataset(self.dataset_path)
        self.tool_registry = get_tool_registry()

    def get_tool_descriptions(self) -> str:
        descriptions = []

        for name, definition in self.tool_registry.items():
            input_model = definition["input_model"]
            schema = input_model.model_json_schema()

            descriptions.append(
                {
                    "name": name,
                    "description": definition["description"],
                    "input_schema": schema,
                }
            )

        return json.dumps(
            descriptions,
            indent=2,
            default=str,
        )

    def execute_tool(
        self,
        dataframe: pd.DataFrame,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[pd.DataFrame, Any]:
        if tool_name not in self.tool_registry:
            raise ValueError(
                f"Unknown analysis tool: {tool_name}"
            )

        definition = self.tool_registry[tool_name]
        input_model = definition["input_model"]

        validated_inputs = input_model.model_validate(
            arguments
        )

        result = definition["function"](
            dataframe,
            validated_inputs,
        )

        if isinstance(result, pd.DataFrame):
            return result, result

        return dataframe, result

    def execute_plan(
        self,
        plan: AnalysisPlan,
    ) -> list[dict[str, Any]]:
        working_dataframe = self.dataframe.copy()
        results = []

        for step in plan.steps:
            working_dataframe, result = self.execute_tool(
                working_dataframe,
                step.tool,
                step.arguments,
            )

            if isinstance(result, pd.DataFrame):
                serialised_result = result.to_dict(
                    orient="records"
                )
            else:
                serialised_result = result

            results.append(
                {
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "result": serialised_result,
                }
            )

        return results

    def parse_plan(
        self,
        raw_plan: str,
    ) -> AnalysisPlan:
        try:
            parsed = json.loads(raw_plan)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "The LLM returned an invalid JSON analysis plan."
            ) from exc

        return AnalysisPlan.model_validate(parsed)

    def build_planning_prompt(
        self,
        question: str,
    ) -> str:
        return f"""
You are the planning component of an AI Data Analyst.

Your job is to convert the user's analytical question into a
controlled sequence of available Python/Pandas tools.

You MUST only use tools from the supplied tool registry.

You MUST NOT:
- write Python code
- use eval
- use exec
- invent tools
- invent columns
- calculate numerical results yourself
- return the final natural-language answer

The Python tools perform the actual calculations.

The dataset columns are:

{list(self.dataframe.columns)}

Available tools:

{self.get_tool_descriptions()}

Return ONLY valid JSON matching this structure:

{{
  "steps": [
    {{
      "tool": "tool_name",
      "arguments": {{}}
    }}
  ]
}}

For multi-step questions, use multiple tools in the correct order.

The output of one tool becomes the current dataset for
the next dataset-transforming tool.

User question:

{question}
""".strip()

    def build_results_prompt(
        self,
        question: str,
        results: list[dict[str, Any]],
    ) -> str:
        return f"""
You are the final response component of an AI Data Analyst.

Answer the user's question using ONLY the deterministic
Python/Pandas tool results below.

Do not invent calculations.

Do not claim that a calculation was performed if it is not
present in the results.

Explain the result clearly and concisely.

User question:

{question}

Tool results:

{json.dumps(results, indent=2, default=str)}

Provide the final answer in normal natural language.
""".strip()

    def plan_with_llm(
        self,
        question: str,
        planning_llm_function: Callable,
    ) -> AnalysisPlan:
        from langchain_core.messages import (
            HumanMessage,
            SystemMessage,
        )

        planning_prompt = self.build_planning_prompt(
            question
        )

        response = planning_llm_function(
            [
                SystemMessage(
                    content=planning_prompt
                ),
                HumanMessage(
                    content=question
                ),
            ]
        )

        if isinstance(response, str):
            raw_plan = response
        elif isinstance(response, dict):
            if "answer" in response:
                raw_plan = response["answer"]
            elif "content" in response:
                raw_plan = response["content"]
            else:
                raw_plan = json.dumps(response)
        else:
            raw_plan = str(response)

        return self.parse_plan(raw_plan)

    def analyse(
        self,
        question: str,
        planning_llm_function: Callable,
        final_llm_function: Callable | None = None,
    ) -> dict[str, Any]:
        if final_llm_function is None:
            final_llm_function = planning_llm_function

        plan = self.plan_with_llm(
            question,
            planning_llm_function,
        )

        results = self.execute_plan(plan)

        final_prompt = self.build_results_prompt(
            question,
            results,
        )

        from langchain_core.messages import (
            HumanMessage,
            SystemMessage,
        )

        final_response = final_llm_function(
            [
                SystemMessage(
                    content=final_prompt
                ),
                HumanMessage(
                    content=question
                ),
            ]
        )

        return {
            "plan": plan.model_dump(),
            "results": results,
            "response": final_response,
        }