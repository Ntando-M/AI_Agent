from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from llm.groq_provider import (
    RateLimitError,
    get_groq_raw_response,
    get_groq_response,
)
from llm.ollama_provider import (
    get_ollama_raw_response,
    get_ollama_response,
)
from models.response_models import AnalysisResponse


class LLMGateway:
    """
    A pre-built provider bound to two call styles.

    The orchestrator never selects a provider and never
    imports a provider module. main.py chooses the provider
    and constructs this gateway, then injects it. That
    keeps routing logic independent of which model is
    running, and makes the orchestrator testable with a
    stub gateway that needs no API key.

    raw()          - free-form text, used for planning
    structured()   - validated AnalysisResponse dict
    """

    def __init__(
        self,
        provider: str,
        raw_function: Callable,
        structured_function: Callable,
    ):
        self.provider = provider.lower().strip()

        self._raw_function = raw_function
        self._structured_function = (
            structured_function
        )

    @classmethod
    def build(
        cls,
        provider: str,
    ) -> "LLMGateway":
        """
        Construct a gateway for a named provider.

        This is the only place provider names are mapped to
        implementations. Call it from the CLI layer.
        """

        normalised = provider.lower().strip()

        if normalised == "groq":
            return cls(
                provider=normalised,
                raw_function=get_groq_raw_response,
                structured_function=(
                    get_groq_response
                ),
            )

        if normalised == "ollama":
            return cls(
                provider=normalised,
                raw_function=get_ollama_raw_response,
                structured_function=(
                    get_ollama_response
                ),
            )

        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            "Choose 'ollama' or 'groq'."
        )

    def raw(
        self,
        messages: list[BaseMessage],
    ) -> str:
        return self._raw_function(messages)

    def structured(
        self,
        messages: list[BaseMessage],
    ) -> dict[str, Any]:
        """
        Produce a validated AnalysisResponse.

        Every path through the orchestrator returns this
        same contract, so a caller never has to branch on
        which engine answered.
        """

        response = self._structured_function(
            messages
        )

        validated = AnalysisResponse.model_validate(
            response
        )

        return validated.model_dump()

    def planning_callable(self) -> Callable:
        return self.raw

    def structured_callable(self) -> Callable:
        return self.structured


def build_messages(
    system_prompt: str,
    question: str,
    history: list[BaseMessage] | None = None,
) -> list[BaseMessage]:
    """
    Assemble the message list for a direct LLM call.

    Conversation history is inserted between the system
    prompt and the question, so a follow-up question can
    refer to an earlier result.
    """

    return [
        SystemMessage(content=system_prompt),
        *(history or []),
        HumanMessage(content=question),
    ]