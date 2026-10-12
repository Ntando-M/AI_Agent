from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from pydantic import ValidationError

from data_analysis import load_dataset
from data_analysis.sql_agent import SQLAnalysisAgent
from data_analysis.tool_models import (
    AnalysisPlan,
    PlanNotProducedError,
)
from data_analysis.tool_registry import (
    get_dataframe_tool_registry,
    get_sql_tool_registry,
    get_tool_registry,
    get_tool_data_source,
)


def strip_code_fences(text):
    """
    Remove a markdown code fence wrapping a JSON payload.

    Models often answer with a fenced block even when told to
    return only JSON, producing:

        ```json
        {"steps": [...]}
        ```

    This is duplicated from llm/groq_provider.py on purpose.
    The engine must not import a provider module - that
    separation is what keeps routing independent of which model
    is running - so the shared behaviour is restated here
    rather than imported across the boundary. The provider
    strips fences for its own callers; the agent strips them
    again because a plan may arrive from any provider.
    """

    if not text:
        return text

    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    remainder = stripped[3:]

    if "\n" in remainder:
        first_line, remainder = remainder.split(
            "\n", 1
        )

        if first_line.strip() == "":
            stripped = remainder
        elif first_line.strip().lower() in {
            "json",
            "javascript",
            "js",
            "python",
        }:
            stripped = remainder

    if stripped.rstrip().endswith("```"):
        stripped = stripped.rstrip()[:-3]

    return stripped.strip()


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

            # A filter that matches nothing empties the frame.
            # That is a legitimate "no data" answer, not an error,
            # so stop here and let the empty result speak for itself
            # rather than passing an empty frame to the next step.
            if (
                step.tool == "filter_dataset"
                and working_dataframe.empty
            ):
                break

        return results

    def parse_plan(
        self,
        raw_plan: str,
    ) -> AnalysisPlan:
        """
        Validate a planner response into an AnalysisPlan.

        Three shapes are accepted, because models differ in
        how literally they follow "return only JSON":

        * {"steps": [...]} - the requested shape
        * [...]             - the bare list, unambiguous
        * ```json fenced``` - markdown wrapping the above

        Anything genuinely ambiguous is rejected rather than
        guessed at, because a wrong plan executes the wrong
        tools against the user's data.
        """

        if isinstance(raw_plan, str):
            candidate = strip_code_fences(raw_plan)

            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "The LLM returned an invalid JSON "
                    "analysis plan."
                ) from exc
        else:
            parsed = raw_plan

        if isinstance(parsed, list):
            parsed = {"steps": parsed}

        # A model that cannot plan sometimes answers with a
        # conversational payload instead - observed in
        # practice: {"error": "I'm sorry, but I couldn't
        # understand which dataset you're referring to."}.
        # Passing that to model_validate produced a cryptic
        # "steps: Field required" 500. A named error tells the
        # reader what actually happened and what to do.
        if not isinstance(parsed, dict) or "steps" not in parsed:
            raise PlanNotProducedError(
                "The model did not return an analysis plan "
                "for this question. Try rephrasing it, or ask "
                "something that can be answered from the "
                "dataset, the database or the documents."
            )

        return AnalysisPlan.model_validate(parsed)

    def _column_value_summary(self) -> str:
        """
        Describe the values present in each column.

        The planner needs the actual labels, not just the column
        names: without them it invents filter values that match
        nothing. Categorical columns list their unique values;
        numeric columns list their range, since enumerating every
        distinct number would bury the prompt.
        """

        lines = []

        for column in self.dataframe.columns:
            series = self.dataframe[column]

            if pd.api.types.is_numeric_dtype(series):
                lines.append(
                    f"- {column} (numeric): "
                    f"min {series.min()}, max {series.max()}"
                )
                continue

            values = series.dropna().unique().tolist()

            if len(values) > 20:
                shown = ", ".join(
                    str(value) for value in values[:20]
                )
                lines.append(
                    f"- {column} ({len(values)} distinct): "
                    f"{shown}, ..."
                )
                continue

            lines.append(
                f"- {column}: "
                f"{', '.join(str(value) for value in values)}"
            )

        return "\n".join(lines)

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

The values actually present in each column are:

{self._column_value_summary()}

Filter values must be chosen from these lists. Never invent a
value: asking about "laptops" when the column holds "Laptop"
matches nothing, and asking for "max" as a product name is not
a value at all. When a question asks for a superlative such as
"the best" or "the most", rank the real values with
group_by_column or sort_dataset rather than filtering on the
word itself.

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
Prefer the fewest steps that answer the question. A ranking or
comparison is usually one group_by_column plus one sort_dataset,
not a filter per category.

User question:

{question}
""".strip()

    def build_results_prompt(
        self,
        question: str,
        results: list[dict[str, Any]],
        document_context: str = "",
    ) -> str:
        """
        Build the synthesis prompt.

        When document context is supplied it is presented
        as a separate section, explicitly distinguished from
        the tool results. That separation is what keeps a
        document statement from being reported as a
        calculated figure.
        """

        context_section = ""

        if document_context.strip():
            context_section = f"""
Retrieved document context is provided below. Use it
to explain, contextualise or qualify the tool results.
Do not treat a document statement as a calculated
result, and do not let it override the numbers the
tools returned.

Retrieved document context:

{document_context.strip()}

"""

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

{context_section}User question:

{question}

Tool results:

{json.dumps(results, indent=2, default=str)}

Return ONLY valid JSON matching this structure:

{{
  "answer": "The complete answer to the user's question, written in clear natural language",
  "analysis_type": "general | document | dataset | database | visualisation",
  "datasets_used": ["name of dataset or database table used"],
  "calculations_performed": ["description of each deterministic calculation or query that was actually executed"],
  "key_findings": ["the most important findings, each stated as a concrete result supported by the evidence"],
  "sources": ["documents, filenames or database tables that provided the evidence"],
  "confidence": 0.0 to 1.0
}}

Every field is required. Do not add extra fields. Do not wrap the JSON in markdown fences.
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
        history: list[BaseMessage] | None = None,
    ) -> AnalysisPlan:
        """
        Ask the planner for a tool sequence.

        history is the conversation so far. A follow-up such
        as "what about the top product?" names no column and
        no metric, so without the prior turn the planner has
        nothing to plan from. Including history lets it
        resolve the reference instead of failing on an
        unplannable question.

        A planner that returns nothing usable is retried once.
        An empty plan is an intermittent property of this
        reasoning model rather than a broken question - the
        same question plans correctly on a second attempt -
        so one retry rescues the turn instead of failing it.
        A question that genuinely cannot be planned still
        raises, because inventing a plan would execute the
        wrong tools against the user's data.
        """

        planning_prompt = self.build_planning_prompt(
            question
        )

        messages = [
            SystemMessage(
                content=planning_prompt
            ),
            *(history or []),
            HumanMessage(
                content=question
            ),
        ]

        last_error: Exception | None = None

        for attempt in range(2):
            response = planning_llm_function(messages)

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

            try:
                return self.parse_plan(raw_plan)
            except (ValueError, ValidationError) as exc:
                last_error = exc

                print(
                    f"[planner] unusable plan on attempt "
                    f"{attempt + 1}, retrying: {exc}"
                )

        raise PlanNotProducedError(
            "The model did not return a usable analysis plan "
            "for this question. Try rephrasing it, or ask "
            "something that can be answered from the dataset, "
            "the database or the documents."
        ) from last_error

    def analyse(
        self,
        question: str,
        planning_llm_function: Callable,
        final_llm_function: Callable | None = None,
        document_context: str = "",
        history: list[BaseMessage] | None = None,
    ) -> dict[str, Any]:
        """
        Plan, execute and synthesise.

        document_context is optional retrieved evidence.
        When present it is merged into the synthesis prompt
        so a single answer can rest on both documents and
        deterministic calculations.

        history is passed to BOTH the planner and the
        synthesiser. The planner needs it to resolve a
        follow-up that references an earlier result; the
        synthesiser needs it to phrase the answer in context.
        """

        if final_llm_function is None:
            final_llm_function = planning_llm_function

        plan = self.plan_with_llm(
            question,
            planning_llm_function,
            history,
        )

        results = self.execute_plan(plan)

        final_prompt = self.build_results_prompt(
            question,
            results,
            document_context,
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