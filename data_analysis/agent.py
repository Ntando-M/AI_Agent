from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from data_analysis import load_dataset
from data_analysis.sql_agent import SQLAnalysisAgent
from data_analysis.tool_models import AnalysisPlan
from data_analysis.tool_registry import (
    get_dataframe_tool_registry,
    get_sql_tool_registry,
    get_tool_registry,
    get_tool_data_source,
)


class DataAnalysisAgent:
    def __init__(
        self,
        dataset_path: str | Path,
        database_path: str | Path | None = None,
    ):
        self.dataset_path = Path(dataset_path)

        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {self.dataset_path}"
            )

        self.dataframe = load_dataset(self.dataset_path)
        self.tool_registry = get_tool_registry()
        self.dataframe_tool_registry = (
            get_dataframe_tool_registry()
        )
        self.sql_tool_registry = get_sql_tool_registry()

        self.sql_agent: SQLAnalysisAgent | None = None

        if database_path is not None:
            self.sql_agent = SQLAnalysisAgent(
                database_path
            )

    @property
    def has_database(self) -> bool:
        """
        Whether SQL tools can be executed by this agent.
        """

        return self.sql_agent is not None

    def get_available_tool_descriptions(self) -> str:
        """
        Describe only the tools this agent can actually run.

        A database tool is omitted when no analytical database
        is configured, so the planner cannot select a tool that
        would fail at execution time.
        """

        registries = [self.dataframe_tool_registry]

        if self.has_database:
            registries.append(
                self.sql_tool_registry
            )

        descriptions = []

        for registry in registries:
            for name, definition in registry.items():
                descriptions.append(
                    {
                        "name": name,
                        "description": definition[
                            "description"
                        ],
                        "input_schema": definition[
                            "input_model"
                        ].model_json_schema(),
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
        """
        Execute one planned step against the correct data source.

        Dataframe tools receive the current working DataFrame.
        SQL tools receive the analytical database engine.

        Returns:
            The new working DataFrame and the tool result.
        """

        data_source = get_tool_data_source(tool_name)

        if data_source == "database":
            definition = self.sql_tool_registry[tool_name]

            if not self.has_database:
                raise ValueError(
                    f"Tool '{tool_name}' requires an "
                    f"analytical database, but none is configured."
                )

            validated_inputs = definition[
                "input_model"
            ].model_validate(arguments)

            result = definition["function"](
                self.sql_agent.engine,
                validated_inputs,
            )

            if isinstance(result, list):
                dataframe = pd.DataFrame(result)

            return dataframe, result

        definition = self.dataframe_tool_registry[tool_name]

        validated_inputs = definition[
            "input_model"
        ].model_validate(arguments)

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

An analytical database is{' available' if self.has_database else ' NOT available'}.
Database tools are listed below only when a database is available.

Available tools:

{self.get_available_tool_descriptions()}

Dataframe tools operate on the current dataset. The output of a
dataset-transforming tool becomes the current dataset for the
next dataset-transforming tool. Database tools operate on the
analytical database and are independent of the current dataset.

Chart tools return the path of a generated image. Include a
chart tool only when the user asks to see, plot, chart,
visualise or graph something, or explicitly asks for a
trend, comparison or distribution picture. Never use a chart
tool just to answer a numeric question.

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
tool results below.

Do not invent calculations.

Do not claim that a calculation was performed if it is not
present in the results.

Do not claim a chart was generated unless the results contain
a chart entry with a path. Reference generated charts by their
path exactly as given.

State any limitation where the evidence is insufficient.

User question:

{question}

Tool results:

{json.dumps(results, indent=2, default=str)}

Respond with the required structured fields.
""".strip()

    def collect_visualisations(
        self,
        results: list[dict[str, Any]],
    ) -> list[str]:
        """
        Return the chart paths produced by the executed plan.

        Collected from the tool results rather than from the
        LLM, so the reported visualisations are always the
        charts that were actually written.
        """

        paths = []

        for step_result in results:
            payload = step_result.get("result")

            if not isinstance(payload, dict):
                continue

            if "path" not in payload:
                continue

            paths.append(payload["path"])

        return paths

    def plan_with_llm(
        self,
        question: str,
        planning_llm_function: Callable,
    ) -> AnalysisPlan:
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
            "visualisations": (
                self.collect_visualisations(results)
            ),
            "response": final_response,
        }